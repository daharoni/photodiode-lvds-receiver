#!/usr/bin/env python3
"""Rule-based PCB placement for the receiver module (run with KiCad's python).

Usage: pcb_place.py BOARD SPEC [--out BOARD] [--report report.json] [--dry-run]

Reads placement-spec.json (see hardware/pcb/receiver-module/placement/),
applies fixed placements, then greedily places each block's parts near their
connection targets on a grid, using courtyard bounding boxes. Block
membership comes from SHEETS in tools/pcb_group_blocks.py.
"""
import argparse, json, math, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from pcb_group_blocks import SHEETS

MM = pcbnew.FromMM
def mm(v): return pcbnew.ToMM(v)

class Part:
    pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board"); ap.add_argument("spec")
    ap.add_argument("--out"); ap.add_argument("--report"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    spec = json.load(open(a.spec))
    board = pcbnew.LoadBoard(a.board)
    ox, oy = spec["origin"]; W, H = spec["size"]
    grid = spec["grid"]; edge = spec["edge_margin"]
    dm, hvm, hlm = spec["default_margin"], spec["hv_margin"], spec["hv_ladder_margin"]

    fps = {f.GetReference(): f for f in board.GetFootprints()}
    members = {}  # block -> refs
    block_of = {}
    for sheet, blist in SHEETS.items():
        for name, refs in blist:
            members[name] = list(refs)
            for r in refs: block_of[r] = name
    top_fixed = spec.get("fixed", {})
    errs = []
    for r in fps:
        if r not in block_of and r not in top_fixed:
            errs.append(f"footprint {r} is in no block and not in fixed")
    for r in top_fixed:
        if r not in fps: errs.append(f"spec fixed ref {r} not on board")
    for bn, b in spec["blocks"].items():
        if bn not in members: errs.append(f"spec block {bn} not in BLOCKS")
        for r in list(b.get("fixed", {})) + b.get("order", []):
            if r not in fps: errs.append(f"spec ref {r} (block {bn}) not on board")
            elif block_of.get(r) != bn: errs.append(f"spec ref {r} listed in {bn} but belongs to {block_of.get(r)}")
    for bn in members:
        if bn not in spec["blocks"]:
            errs.append(f"block {bn} has no spec entry")
    if errs:
        print("ERRORS:"); [print("  " + e) for e in errs]; sys.exit(2)

    # part info
    def is_th(fp): return any(p.GetDrillSizeX() > 0 and p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) for p in fp.Pads())
    def margin_of(fp):
        cls = set()
        for p in fp.Pads():
            try: cls.add(p.GetNet().GetNetClassName())
            except Exception: pass
        return hvm if "HV" in cls else hlm if "HV_LADDER" in cls else dm
    def bbox(fp):
        side = pcbnew.F_CrtYd if not fp.IsFlipped() else pcbnew.B_CrtYd
        ch = fp.GetCourtyard(side)
        bb = ch.BBox() if ch.OutlineCount() else fp.GetBoundingBox(False)
        return (mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom()))
    parts = {}
    for r, fp in fps.items():
        p = Part(); p.fp = fp; p.ref = r; p.th = is_th(fp); p.margin = margin_of(fp)
        p.npads = len(list(fp.Pads())); p.side = None; p.placed = False
        parts[r] = p

    ctr = pcbnew.VECTOR2I(0, 0)
    def set_pose(fp, x, y, rot, side):
        want_flip = (side == "bottom")
        if fp.IsFlipped() != want_flip:
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetPosition(pcbnew.VECTOR2I(MM(ox + x), MM(oy + y)))
        fp.SetOrientationDegrees(rot)
    def rel_bbox(p, rot, side):
        set_pose(p.fp, 0, 0, rot, side)
        # place at origin-of-board offset 0: position = (ox,oy)... compute relative to fp position
        bx = bbox(p.fp); px, py = mm(p.fp.GetPosition().x), mm(p.fp.GetPosition().y)
        return (bx[0] - px, bx[1] - py, bx[2] - px, bx[3] - py)

    placed = []  # (ref, side, th, (x0,y0,x1,y1) expanded absolute-relative coords)
    status, rec = {}, {}
    def pose_record(p, x, y, rot, side, block, st):
        set_pose(p.fp, x, y, rot, side)
        p.side = side; p.placed = True
        bx = bbox(p.fp); m = p.margin
        ex = (bx[0] - ox - m, bx[1] - oy - m, bx[2] - ox + m, bx[3] - oy + m)
        placed.append((p.ref, side, p.th, ex))
        rec[p.ref] = dict(side=side, x=x, y=y, rot=rot, block=block, status=st)
        p.bx = bx
        return bx

    def sides_of(p, side): return ("top", "bottom") if p.th else (side,)
    def collide(p, side, ex):
        for ref, s, th, e in placed:
            if not (p.th or th or s == side): continue
            if ex[0] < e[2] and ex[2] > e[0] and ex[1] < e[3] and ex[3] > e[1]: return True
        for k in spec.get("keepouts", []):
            if p.ref in k.get("except", []): continue
            if not (set(k["sides"]) & set(sides_of(p, side))): continue
            r = k["region"]
            if ex[0] < r[2] and ex[2] > r[0] and ex[1] < r[3] and ex[3] > r[1]: return True
        return False

    warnings = []
    def apply_fixed(ref, x, y, rot, side, block):
        p = parts[ref]; bx = pose_record(p, x, y, rot, side, block, "fixed")
        lo = (bx[0] - ox, bx[1] - oy, bx[2] - ox, bx[3] - oy)
        if lo[0] < edge or lo[1] < edge or lo[2] > W - edge or lo[3] > H - edge:
            warnings.append(f"fixed {ref} courtyard ({lo[0]:.2f},{lo[1]:.2f})-({lo[2]:.2f},{lo[3]:.2f}) outside edge margin")
    for r, (x, y, rot, side) in top_fixed.items(): apply_fixed(r, x, y, rot, side, "(top-level)")
    for bn, b in spec["blocks"].items():
        for r, (x, y, rot) in b.get("fixed", {}).items(): apply_fixed(r, x, y, rot, b["side"], bn)

    # connectivity
    netpads = {}
    for r, p in parts.items():
        for pad in p.fp.Pads():
            n = pad.GetNetname()
            if n: netpads.setdefault(n, []).append(pad)
    def pad_global(ref, num):
        for pad in parts[ref].fp.Pads():
            if pad.GetNumber() == str(num): return mm(pad.GetPosition().x) - ox, mm(pad.GetPosition().y) - oy
        return None
    def target_for(p, b):
        near = b.get("near", {}).get(p.ref)
        if near:
            r, n = near.split(".", 1)
            if r in parts and parts[r].placed:
                g = pad_global(r, n)
                if g: return g
        xs, ys = [], []
        for pad in p.fp.Pads():
            n = pad.GetNetname()
            if not n or len(netpads.get(n, [])) > 6: continue
            for q in netpads[n]:
                owner = q.GetParentFootprint()
                if owner.GetReference() != p.ref and parts[owner.GetReference()].placed:
                    xs.append(mm(q.GetPosition().x) - ox); ys.append(mm(q.GetPosition().y) - oy)
        if xs: return sum(xs) / len(xs), sum(ys) / len(ys)
        r = b["region"]; return (r[0] + r[2]) / 2, (r[1] + r[3]) / 2

    t0 = time.time()
    for bn, b in spec["blocks"].items():
        side = b["side"]; R = b["region"]
        order = [r for r in b.get("order", []) if r in members[bn]]
        order += [r for r in members[bn] if r not in order and not parts[r].placed]
        order = [r for r in order if not parts[r].placed]
        for ref in order:
            p = parts[ref]
            rots = [0, 90] if p.npads <= 2 else [0, 90, 180, 270]
            rb = {rot: rel_bbox(p, rot, side) for rot in rots}
            tx, ty = target_for(p, b)
            best = None; status = "auto"
            m = p.margin
            # try the block region first, then the region grown by 3, 6 and 10 mm (clipped to the board)
            for grow in (0, 3, 6, 10):
                RR = (max(edge, R[0] - grow), max(edge, R[1] - grow), min(W - edge, R[2] + grow), min(H - edge, R[3] + grow))
                cands = []
                gx0 = math.ceil(RR[0] / grid); gx1 = math.floor(RR[2] / grid)
                gy0 = math.ceil(RR[1] / grid); gy1 = math.floor(RR[3] / grid)
                for ix in range(gx0, gx1 + 1):
                    for iy in range(gy0, gy1 + 1):
                        cands.append(((ix * grid - tx) ** 2 + (iy * grid - ty) ** 2, ix * grid, iy * grid))
                cands.sort()
                for d2, x, y in cands:
                    for ri, rot in enumerate(rots):
                        q = rb[rot]
                        c = (x + q[0], y + q[1], x + q[2], y + q[3])  # courtyard in rel coords
                        if c[0] < RR[0] or c[1] < RR[1] or c[2] > RR[2] or c[3] > RR[3]: continue
                        ex = (c[0] - m, c[1] - m, c[2] + m, c[3] + m)
                        if ex[0] < edge or ex[1] < edge or ex[2] > W - edge or ex[3] > H - edge: continue
                        if collide(p, side, ex): continue
                        best = (x, y, rot); break
                    if best: break
                if best:
                    if grow: status = f"auto-grown{grow}"
                    break
            if best:
                pose_record(p, best[0], best[1], best[2], side, bn, status)
            else:
                pose_record(p, (R[0] + R[2]) / 2, (R[1] + R[3]) / 2, 0, side, bn, "UNPLACED-OVERLAP")
                placed.pop()  # a failed part must not block later candidates
    # any not placed (shouldn't be)
    for r, p in parts.items():
        if not p.placed: warnings.append(f"{r} never placed")

    # summaries
    print(f"placement time {time.time()-t0:.1f}s")
    tot_fail = []
    for bn in spec["blocks"]:
        refs = [r for r in rec if rec[r]["block"] == bn]
        fail = [r for r in refs if rec[r]["status"] == "UNPLACED-OVERLAP"]
        tot_fail += fail
        print(f"{bn:18s} placed {len(refs)-len(fail):3d}  failed {len(fail)} {fail if fail else ''}")
    for w in warnings: print("WARN", w)
    for ref, pads in [("J50", "A1 A12 B1 S1"), ("U60", "1 24 36"), ("U10", "15 8"), ("U20", "4 12"), ("U50", "6 16"),
                      ("U3", "1 9 16"), ("U64", "1 7"), ("U5", "4 5"), ("U61", "1 5"), ("D10", "1 3"), ("J51", "1 6")]:
        p = parts[ref]; bx = p.bx
        s = f"{ref} side={rec[ref]['side']} rot={rec[ref]['rot']} bbox=({bx[0]:.2f},{bx[1]:.2f})-({bx[2]:.2f},{bx[3]:.2f}) "
        for n in pads.split():
            g = None
            for pad in p.fp.Pads():
                if pad.GetNumber() == n:
                    g = (mm(pad.GetPosition().x), mm(pad.GetPosition().y)); break
            s += f"pad{n}=" + (f"({g[0]:.2f},{g[1]:.2f}) " if g else "NA ")
        print(s)
    # outline & labels
    for d in list(board.GetDrawings()):
        if d.GetLayer() == pcbnew.Edge_Cuts and d.GetShape() == pcbnew.SHAPE_T_RECT:
            d.SetStart(pcbnew.VECTOR2I(MM(ox), MM(oy))); d.SetEnd(pcbnew.VECTOR2I(MM(ox + W), MM(oy + H)))
    for d in list(board.GetDrawings()):
        if d.GetClass() in ("PCB_TEXT",) and d.GetLayer() == pcbnew.Cmts_User:
            t = d.GetText()
            if t.startswith("No footprints placed") or t.startswith("Board outline:"):
                board.Remove(d); continue
            if t in spec["blocks"] or (t.endswith(" (B)") and t[:-4] in spec["blocks"]):
                bn = t[:-4] if t.endswith(" (B)") else t
                b = spec["blocks"][bn]; R = b["region"]
                if b["side"] == "bottom" and not t.endswith(" (B)"): d.SetText(t + " (B)")
                sz = mm(d.GetTextHeight())
                dy = sz if d.GetVertJustify() == pcbnew.GR_TEXT_V_ALIGN_BOTTOM else 0
                d.SetPosition(pcbnew.VECTOR2I(MM(ox + R[0] + 0.5), MM(oy + R[1] + 0.5 + dy)))

    if a.report:
        json.dump({"unplaced": tot_fail, "warnings": warnings, "parts": rec}, open(a.report, "w"), indent=1)
    if a.dry_run: print("dry run: nothing written"); return
    out = a.out or a.board
    pcbnew.SaveBoard(out, board)
    # verify
    print(f'saved {out}; verify by reloading in a fresh process (in-process reload is unreliable in pcbnew SWIG)')
    return
    b2 = pcbnew.LoadBoard(out)
    f2 = {f.GetReference(): f for f in b2.GetFootprints()}
    bad = [r for r, v in rec.items() if f2[r].IsFlipped() != (v["side"] == "bottom")]
    print(f"saved {out}: {len(f2)} footprints, layer mismatches: {bad}")

if __name__ == "__main__":
    main()
