#!/usr/bin/env python3
"""Add functional block groups to the receiver-module KiCad 10 board.

Usage: pcb_group_blocks.py BOARD.kicad_pcb [--cluster] [--dry-run]

Creates one top-level group per schematic sheet (POWER, FRONT_END, SLICER,
MONITOR, CONNECTOR, CONTROLLER) holding one sub-group per functional block, so
the layout can be placed block by block. The reference -> block table below is
derived from docs/schematic/rev-a-sheet-specs.md (revision 4) and the as-built
notes docs/schematic/*.md; the PROPOSED decoupling assignments follow the
schematic placement. Footprints not in the table go to a per-sheet MISC block
(sheet inferred from the reference-designator ranges) and are reported.

--cluster  also moves each block's footprints into a compact grid cluster to the
           right of the existing placement, with a Cmts.User label per block.
--dry-run  report only, write nothing.
The board is rewritten in place after copying it to BOARD.kicad_pcb.bak.
Re-running replaces earlier groups and block labels made by this script.
"""
import argparse, math, re, shutil, sys, uuid

def rng(p, a, b):
    return [f"{p}{i}" for i in range(a, b + 1)]

# sheet group -> ordered list of (block, [refs]); block names carry the sheet prefix
SHEETS = {
 "POWER": [
  ("PWR_EFUSE",   ["U5", "R35", "R36", "R37", "R38", "R39", "C32", "C33", "C1", "C2", "TP3", "TP4"]),
  ("PWR_3V3",     ["U1", "R1", "R2", "C9", "C10", "C11", "C12"]),
  ("PWR_3V3D",    ["U4", "C29", "C30", "C31"]),
  ("PWR_HV_BOOST",["U3", "L1", "L2", "D1", "D2", "D3", "D4", "C5", "C6", "C7", "C18", "C19", "C20",
                   "C21", "C22", "C23", "C24", "R7", "R22", "R23", "R24", "R25", "R26", "R27",
                   "R28", "R29", "TP2"]),
  ("PWR_HV_FB",   ["R8", "R9", "R10", "R11", "R12", "R13", "R14", "R15", "C26", "C27", "RV1", "TH1"]),
  ("PWR_HV_OUT",  ["Q1", "Q2", "R16", "R17", "R18", "R19", "R30", "C8", "C25"]),
  ("PWR_HV_MON",  ["R20", "R21", "R32", "C28"]),
  ("PWR_HV_DIS",  ["Q3", "J1", "R33", "R34"]),
 ],
 "FRONT_END": [
  ("FE_APD",      ["D10", "R50", "C50"]),
  ("FE_TIA",      ["U10", "C56", "C57", "C59", "R57", "JP10", "R58", "TP12"]),
  ("FE_POSTAMP",  ["C51", "R51", "U11", "R53", "R54", "R60", "C53", "C52", "C58", "TP10"]),
  ("FE_LPF_COUPLE", ["R56", "C54", "C55", "R59", "TP11"]),
 ],
 "SLICER": [
  ("SLC_COMP",    ["U20", "C80", "C81", "C82", "C83", "R80", "R81", "R82", "R83"]),
  ("SLC_THRESH",  ["R84", "R85", "R86", "C84", "TP20"]),
  ("SLC_HYST",    ["R87", "C87", "TP21"]),
 ],
 "MONITOR": [
  ("MON_VCM",     ["U30", "R100", "R101", "R102", "C100", "C101", "C103", "TP30"]),
  ("MON_RSSI",    ["D30", "C102", "R103", "TP31", "TP32"]),
 ],
 "CONNECTOR": [
  ("CONN_RECEPT", ["J50", "U51", "U52", "R170", "C181", "R186"]),
  ("CONN_CC",     ["R181", "R184", "R185", "R187", "R188", "R189", "C182", "C183"]),
  ("CONN_CAN_TERM", ["R182", "R183", "C180"]),
  ("CONN_FANOUT", ["U50", "R180", "C184", "C185"]),
  ("CONN_DEBUG",  ["J51", "R177"]),
  ("CONN_TP",     rng("TP", 50, 55)),
 ],
 "CONTROLLER": [
  ("CTRL_MCU",    ["U60", "C191", "C192", "R192", "R204", "R205"]),
  ("CTRL_RESET_BOOT", ["R190", "C190", "R191", "SW60", "SW61", "TP60", "TP61"]),
  ("CTRL_USB",    ["U61", "R193", "R194", "C206", "C207"]),
  ("CTRL_CAN",    ["U64", "R199", "C196", "TP66", "TP67"]),
  ("CTRL_DAC",    ["U62", "C194", "R210", "R211", "R212", "R213", "C201", "C202", "C203", "C204",
                   "R195", "R196", "R197", "R198", "TP64", "TP65", "TP68", "TP69"]),
  ("CTRL_ADC",    ["U63", "C195", "R206", "R207", "R208", "R209", "C197", "C198", "C199", "C200"]),
  ("CTRL_STATUS_UART", ["D60", "R203", "TP62", "TP63"]),
 ],
}
SHEET_ORDER = list(SHEETS)

# reference-number ranges per sheet (spec section 0) for the MISC fallback
RANGES = {  # prefix -> list of (lo, hi, sheet)
 "default": [(1, 49, "POWER"), (50, 79, "FRONT_END"), (80, 99, "SLICER"),
             (100, 149, "MONITOR"), (170, 189, "CONNECTOR"), (190, 219, "CONTROLLER")],
}
def sheet_by_range(ref):
    n = int(re.search(r"\d+", ref).group())
    for lo, hi, sh in RANGES["default"]:
        if lo <= n <= hi:
            return sh
    # U10-U19 / D10-D19 / JP10-19 / TP10-19 etc. use the same tens ranges
    for lo, hi, sh in [(10, 19, "FRONT_END"), (20, 29, "SLICER"), (30, 39, "MONITOR"),
                       (50, 59, "CONNECTOR"), (60, 69, "CONTROLLER")]:
        if lo <= n <= hi:
            return sh
    return "POWER"
MISC_NAME = {"POWER": "PWR_MISC", "FRONT_END": "FE_MISC", "SLICER": "SLC_MISC",
             "MONITOR": "MON_MISC", "CONNECTOR": "CONN_MISC", "CONTROLLER": "CTRL_MISC"}

# ---------------------------------------------------------------- s-expr helpers
def match_end(s, i):
    """index just past the parenthesised expression starting at s[i]=='('."""
    depth, j, n = 0, i, len(s)
    while j < n:
        c = s[j]
        if c == '"':
            j += 1
            while s[j] != '"':
                j += 2 if s[j] == '\\' else 1
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    raise ValueError("unbalanced")

def top_blocks(s, kind):
    """(start, end) of top-level '\n\t(kind' blocks (start points at the '(')."""
    out, pos, key = [], 0, f"\n\t({kind}"
    while True:
        i = s.find(key, pos)
        if i < 0:
            return out
        i += 2
        if s[i + len(kind) + 1] not in ' \n"':
            pos = i; continue
        e = match_end(s, i)
        out.append((i, e)); pos = e

def parse_footprints(s):
    fps = []
    for a, e in top_blocks(s, "footprint"):
        b = s[a:e]
        ref = re.search(r'\(property "Reference" "([^"]*)"', b).group(1)
        uid = re.search(r'\n\t\t\(uuid "([^"]+)"\)', b).group(1)
        layer = re.search(r'\n\t\t\(layer "([^"]+)"\)', b).group(1)
        m = re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)', b)
        fps.append(dict(a=a, e=e, ref=ref, uuid=uid, layer=layer, x=float(m.group(1)),
                        y=float(m.group(2)), rot=float(m.group(3) or 0), at_span=(a + m.start(), a + m.end()),
                        body=b))
    return fps

def local_bbox(body):
    """bounding box (x0,y0,x1,y1) in footprint-local coordinates: union of the
    courtyard graphics and the pad extents."""
    xs, ys = [], []
    for m in re.finditer(r'\n\t\t\((fp_rect|fp_line|fp_poly|fp_circle|fp_arc)\b', body):
        a = m.start() + 3
        el = body[a:match_end(body, a)]
        if not re.search(r'\(layer "[FB]\.CrtYd"\)', el):
            continue
        pts = [(float(x), float(y)) for x, y in
               re.findall(r'\((?:start|end|mid|xy|center) ([-\d.]+) ([-\d.]+)\)', el)]
        if m.group(1) == "fp_circle" and len(pts) == 2:
            (cx, cy), (ex, ey) = pts; r = math.hypot(ex - cx, ey - cy)
            pts = [(cx - r, cy - r), (cx + r, cy + r)]
        for x, y in pts:
            xs.append(x); ys.append(y)
    for m in re.finditer(r'\(pad "[^"]*" \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)\s*\(size ([-\d.]+) ([-\d.]+)\)', body):
        x, y, rot, w, h = float(m.group(1)), float(m.group(2)), float(m.group(3) or 0), float(m.group(4)), float(m.group(5))
        if round(rot) % 180 == 90:
            w, h = h, w
        xs += [x - w / 2, x + w / 2]; ys += [y - h / 2, y + h / 2]
    if not xs:
        return (-1.0, -1.0, 1.0, 1.0)
    return (min(xs), min(ys), max(xs), max(ys))

def to_world(fp, lx, ly):
    if fp["layer"].startswith("B."):
        lx = -lx
    t = math.radians(fp["rot"])
    return (lx * math.cos(t) + ly * math.sin(t), -lx * math.sin(t) + ly * math.cos(t))

def world_bbox(fp):
    x0, y0, x1, y1 = local_bbox(fp["body"])
    pts = [to_world(fp, a, b) for a in (x0, x1) for b in (y0, y1)]
    wx = [p[0] for p in pts]; wy = [p[1] for p in pts]
    return min(wx), min(wy), max(wx), max(wy)   # relative to fp origin

# ---------------------------------------------------------------- clustering
def pack_block(items, margin=1.0):
    """shelf-pack items [(fp,w,h)] -> dict uuid->(cx,cy) cell centres rel. to block origin, (W,H)."""
    items = sorted(items, key=lambda t: -t[2] * t[1])
    area = sum((w + margin) * (h + margin) for _, w, h in items)
    target = max(math.sqrt(area) * 1.25, max(w + margin for _, w, _ in items))
    pos, x, y, rowh, W = {}, 0.0, 0.0, 0.0, 0.0
    for fp, w, h in items:
        cw, ch = w + margin, h + margin
        if x > 0 and x + cw > target:
            x, y, rowh = 0.0, y + rowh, 0.0
        pos[fp["uuid"]] = (x + cw / 2, y + ch / 2)
        x += cw; rowh = max(rowh, ch); W = max(W, x)
    return pos, (W, y + rowh)

def fmt(v):
    return f"{v:.4f}".rstrip("0").rstrip(".")

def new_uuid():
    return str(uuid.uuid4())

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("board"); ap.add_argument("--cluster", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    s = open(args.board).read()
    fps = parse_footprints(s)
    byref = {f["ref"]: f for f in fps}
    if len(byref) != len(fps):
        sys.exit("duplicate references on board")

    # strip groups and labels from an earlier run (our names only)
    names = set(SHEETS) | {b for bl in SHEETS.values() for b, _ in bl} | set(MISC_NAME.values())
    for a, e in reversed(top_blocks(s, "group")):
        m = re.match(r'\(group "([^"]*)"', s[a:e])
        if m and m.group(1) in names:
            s = s[:a].rstrip("\t") + s[e:]
            s = s.replace("\n\t\n", "\n")
    for a, e in reversed(top_blocks(s, "gr_text")):
        m = re.match(r'\(gr_text "([^"]*)"', s[a:e])
        if m and m.group(1) in names and 'Cmts.User' in s[a:e]:
            s = s[:a] + s[e:]
    fps = parse_footprints(s); byref = {f["ref"]: f for f in fps}
    if re.search(r'\(group "(?!(?:%s)")' % "|".join(map(re.escape, names)), s):
        print("note: board has other groups; members of those groups cannot join ours", file=sys.stderr)

    # build assignment
    blocks = {sh: [(b, [r for r in refs]) for b, refs in bl] for sh, bl in SHEETS.items()}
    assigned = {}
    problems = []
    for sh, bl in blocks.items():
        for b, refs in bl:
            for r in refs:
                if r in assigned:
                    problems.append(f"{r} listed in {assigned[r]} and {b}")
                assigned[r] = b
    missing = sorted(r for sh in blocks.values() for b, refs in sh for r in refs if r not in byref)
    leftovers = sorted((r for r in byref if r not in assigned),
                       key=lambda r: (re.match(r"[A-Z#]+", r).group(), int(re.search(r"\d+", r).group())))
    for r in leftovers:
        sh = sheet_by_range(r)
        mb = MISC_NAME[sh]
        for b, refs in blocks[sh]:
            if b == mb:
                refs.append(r); break
        else:
            blocks[sh].append((mb, [r]))
        assigned[r] = mb
    blocks = {sh: [(b, [r for r in refs if r in byref]) for b, refs in bl] for sh, bl in blocks.items()}
    blocks = {sh: [(b, refs) for b, refs in bl if refs] for sh, bl in blocks.items()}

    print("Blocks:")
    for sh in SHEET_ORDER:
        print(f" {sh}")
        for b, refs in blocks[sh]:
            print(f"   {b:18s} ({len(refs):3d}) {' '.join(refs)}")
    n_assigned = sum(len(refs) for bl in blocks.values() for _, refs in bl)
    print(f"footprints on board: {len(fps)}; assigned: {n_assigned}; "
          f"not in table (sent to MISC): {len(leftovers)} {leftovers}; "
          f"table refs absent from board: {len(missing)} {missing}")
    for p in problems:
        print("ERROR:", p)
    if problems:
        sys.exit(1)

    # clustering (modifies s at footprint 'at' spans; do from the end backwards)
    labels = []
    if args.cluster:
        maxx = max(f["x"] + world_bbox(f)[2] for f in fps)
        miny = min(f["y"] + world_bbox(f)[1] for f in fps)
        x_start = maxx + 20.0
        y = miny + 4.0
        GAP_X, GAP_Y, LBL = 6.0, 6.0, 3.0
        moves = {}
        for sh in SHEET_ORDER:
            x, rowh = x_start, 0.0
            for b, refs in blocks[sh]:
                items = []
                for r in refs:
                    f = byref[r]; x0, y0, x1, y1 = world_bbox(f)
                    items.append((f, x1 - x0, y1 - y0))
                pos, (W, H) = pack_block(items)
                for f, w, h in items:
                    cx, cy = pos[f["uuid"]]
                    x0, y0, x1, y1 = world_bbox(f)
                    # centre bbox in its cell
                    moves[f["uuid"]] = (x + cx - (x0 + x1) / 2, y + LBL + cy - (y0 + y1) / 2)
                labels.append((b, x, y + LBL - 0.8))
                W = max(W, len(b) * 1.1)   # keep neighbouring labels apart
                x += W + GAP_X; rowh = max(rowh, H + LBL)
            y += rowh + GAP_Y
        for f in sorted(fps, key=lambda f: -f["a"]):
            nx, ny = moves[f["uuid"]]
            a, e = f["at_span"]
            rot = f"{fmt(f['rot'])}" if f["rot"] else None
            at = f"\n\t\t(at {fmt(nx)} {fmt(ny)}" + (f" {rot}" if rot else "") + ")"
            s = s[:a] + at + s[e:]
        print(f"cluster: origin x={fmt(x_start)} y={fmt(miny + 4)} (existing max x {fmt(maxx)}), "
              f"extent to y={fmt(y)}")

    # groups
    fps = parse_footprints(s)
    byref = {f["ref"]: f for f in fps}
    out = []
    for sh in SHEET_ORDER:
        sub = []
        for b, refs in blocks[sh]:
            gid = new_uuid(); sub.append(gid)
            mem = " ".join(f'"{byref[r]["uuid"]}"' for r in refs)
            out.append(f'\t(group "{b}"\n\t\t(uuid "{gid}")\n\t\t(members {mem})\n\t)\n')
        out.append(f'\t(group "{sh}"\n\t\t(uuid "{new_uuid()}")\n\t\t(members {" ".join(chr(34)+g+chr(34) for g in sub)})\n\t)\n')
    txt = "".join(
        f'\t(gr_text "{b}"\n\t\t(at {fmt(x)} {fmt(y)} 0)\n\t\t(layer "Cmts.User")\n\t\t(uuid "{new_uuid()}")\n'
        f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.5 1.5)\n\t\t\t\t(thickness 0.2)\n\t\t\t)\n'
        f'\t\t\t(justify left bottom)\n\t\t)\n\t)\n' for b, x, y in labels)
    end = s.rstrip().rfind("\n)")
    s2 = s[:end + 1] + txt + "".join(out) + s[end + 1:]
    # sanity: every footprint in exactly one sub-group
    seen = []
    for o in out:
        if o.split('"')[1] not in SHEETS:
            seen += re.findall(r'"([0-9a-f-]{36})"', o.split("(members")[1])
    assert len(seen) == len(set(seen)) == len(fps), (len(seen), len(set(seen)), len(fps))
    if args.dry_run:
        print("dry run: nothing written"); return
    shutil.copy2(args.board, args.board + ".bak")
    open(args.board, "w").write(s2)
    print(f"wrote {args.board} (backup {args.board}.bak)")

if __name__ == "__main__":
    main()
