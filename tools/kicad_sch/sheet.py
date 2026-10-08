"""Generate a KiCad 10 .kicad_sch sheet: symbols, wires, labels."""
import math
import os
import uuid as _uuid

from .library import Library
from .sexpr import Str, dumps, esc, find, find_all, num, parse

GRID = 1.27
_JUSTIFY = {0: "left bottom", 90: "left bottom", 180: "right bottom", 270: "right bottom"}
_LABEL_JUSTIFY = {0: "left", 90: "left", 180: "right", 270: "right"}
_DIRS = {"r": (1, 0, 0), "l": (-1, 0, 180), "u": (0, -1, 90), "d": (0, 1, 270)}  # dx, dy (sch), label rot


def _uid():
    return Str(str(_uuid.uuid4()))


def _r(v):
    return round(v + 0.0, 4)


def _pt(p):
    return (_r(p[0]), _r(p[1]))


def _fx(size=1.27, justify=None, hide=False):
    e = ["effects", ["font", ["size", float(size), float(size)]]]
    if justify:
        e.append(["justify"] + justify.split())
    return e


def transform(px, py, at, rot=0, mirror=None):
    """Symbol-coordinate point (Y up) -> schematic coordinate (Y down).
    Rotation CCW as seen on screen is applied first, then the mirror (x: flip Y, y: flip X);
    verified against kicad-cli netlists (selftest) for all 12 rotation/mirror combinations."""
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    px, py = px * c - py * s, px * s + py * c
    if mirror == "x":
        py = -py
    elif mirror == "y":
        px = -px
    return _pt((at[0] + px, at[1] - py))


class Instance:
    def __init__(self, sheet, lib_id, ref, at, rot, mirror, unit):
        self.sheet, self.lib_id, self.ref = sheet, lib_id, ref
        self.at, self.rot, self.mirror, self.unit = at, rot, mirror, unit
        self.pins = sheet.lib.pins(lib_id, unit)

    def pin(self, key):
        """Absolute (x, y) of a pin given its number or name."""
        hits = [p for p in self.pins if p["number"] == str(key)] or \
               [p for p in self.pins if p["name"] == str(key)]
        if len(hits) != 1:
            raise KeyError("%s (%s) unit %d: pin %r matches %d pins; available: %s" % (
                self.ref, self.lib_id, self.unit, key, len(hits),
                ", ".join("%s=%s" % (p["number"], p["name"]) for p in self.pins)))
        p = hits[0]
        return transform(p["x"], p["y"], self.at, self.rot, self.mirror)


class Sheet:
    def __init__(self, uuid, paper="A3", title_block=None, root_uuid=None, sheet_uuid=None,
                 project="receiver-module", lib=None):
        self.uuid, self.paper, self.title_block = uuid, paper, title_block
        self.root_uuid, self.sheet_uuid, self.project = root_uuid, sheet_uuid, project
        self.lib = lib or Library()
        self.wires, self.items, self.junctions, self.ncs = [], [], [], []
        self.symbols, self.lib_syms, self.instances = [], {}, []
        self.sheets = []

    @classmethod
    def load(cls, path, root_uuid=None, sheet_uuid=None, project="receiver-module", lib=None):
        """Keep uuid/paper/title_block of `path`. If root_uuid/sheet_uuid are not given they are
        looked up in `<dir>/<project>.kicad_sch` (the (sheet ...) block whose Sheetfile matches)."""
        tree = parse(open(path).read())
        if root_uuid is None:
            rootf = os.path.join(os.path.dirname(os.path.abspath(path)), project + ".kicad_sch")
            if os.path.exists(rootf):
                root = parse(open(rootf).read())
                root_uuid = str(find(root, "uuid")[1])
                for sh in find_all(root, "sheet"):
                    props = {p[1]: p[2] for p in find_all(sh, "property")}
                    if props.get("Sheetfile") == os.path.basename(path):
                        sheet_uuid = sheet_uuid or str(find(sh, "uuid")[1])
        return cls(find(tree, "uuid")[1], find(tree, "paper")[1] if find(tree, "paper") else "A3",
                   find(tree, "title_block"), root_uuid, sheet_uuid, project, lib)

    # ---- symbols -------------------------------------------------------
    def place(self, lib_id, ref, value, at, rot=0, mirror=None, unit=1, footprint=None,
              fields=None, dnp=False, in_bom=True):
        assert rot in (0, 90, 180, 270) and mirror in (None, "x", "y"), "bad rot/mirror"
        at = _pt(at)
        inst = Instance(self, lib_id, ref, at, rot, mirror, unit)
        if not inst.pins:
            raise ValueError("%s has no pins for unit %d" % (lib_id, unit))
        for p in inst.pins:
            x, y = transform(p["x"], p["y"], at, rot, mirror)
            if any(abs(v / GRID - round(v / GRID)) > 1e-6 / GRID for v in (x, y)):
                raise ValueError("%s %s pin %s (%s) lands at (%s, %s): off the 1.27 mm grid"
                                 % (ref, lib_id, p["number"], p["name"], x, y))
        if lib_id not in self.lib_syms:
            self.lib_syms[lib_id] = self.lib.symbol(lib_id)
        sym = ["symbol", ["lib_id", Str(lib_id)], ["at", at[0], at[1], rot]]
        if mirror:
            sym.append(["mirror", mirror])
        sym += [["unit", unit], ["body_style", 1], ["exclude_from_sim", "no"],
                ["in_bom", "yes" if in_bom else "no"], ["on_board", "yes"], ["in_pos_files", "yes"],
                ["dnp", "yes" if dnp else "no"], ["uuid", _uid()]]
        sym += self._properties(lib_id, ref, value, at, rot, mirror, footprint, fields or {})
        for p in inst.pins:
            sym.append(["pin", Str(p["number"]), ["uuid", _uid()]])
        path = "/" + "/".join(x for x in (self.root_uuid, self.sheet_uuid) if x)
        sym.append(["instances", ["project", Str(self.project),
                                  ["path", Str(path), ["reference", Str(ref)], ["unit", unit]]]])
        self.symbols.append(sym)
        self.instances.append(inst)
        return inst

    def _properties(self, lib_id, ref, value, at, rot, mirror, footprint, fields):
        libprops = {p[1]: p for p in find_all(self.lib_syms[lib_id], "property")}
        vals = {"Reference": ref, "Value": value}
        order = ["Reference", "Value", "Footprint", "Datasheet", "Description"]
        order += [k for k in libprops if k not in order] + [k for k in fields if k not in libprops and k not in order]
        angle = 90 if rot in (90, 270) else 0
        flip = (rot in (180, 270)) ^ (mirror == "y" and rot in (0, 180)) ^ (mirror == "x" and rot in (90, 270))
        out = []
        for name in order:
            lp = libprops.get(name)
            v = fields.get(name, vals.get(name))
            if name == "Footprint" and footprint is not None:
                v = footprint
            v = esc(v) if v is not None else (lp[2] if lp else Str(""))
            lat = find(lp, "at") if lp else None
            pos = transform(float(lat[1]), float(lat[2]), at, rot, mirror) if lat else at
            if name in ("Reference", "Value"):
                jl = find(find(lp, "effects"), "justify") if lp and find(lp, "effects") else None
                just = None
                if jl and ("left" in jl or "right" in jl):
                    left = ("left" in jl) != flip
                    just = "left" if left else "right"
                out.append(["property", Str(name), v, ["at", pos[0], pos[1], angle], ["show_name", "no"],
                            ["do_not_autoplace", "no"], _fx(1.27, just)])
            else:
                out.append(["property", Str(name), v, ["at", at[0], at[1], angle], ["hide", "yes"],
                            ["show_name", "no"], ["do_not_autoplace", "no"], _fx()])
        return out

    # ---- primitives ----------------------------------------------------
    def wire(self, points):
        pts = [_pt(p) for p in points]
        for a, b in zip(pts, pts[1:]):
            if a != b:
                self.wires.append(["wire", ["pts", ["xy", a[0], a[1]], ["xy", b[0], b[1]]],
                                   ["stroke", ["width", 0], ["type", "default"]], ["uuid", _uid()]])

    def junction(self, at):
        at = _pt(at)
        if at not in self.junctions:
            self.junctions.append(at)

    def no_connect(self, at):
        self.ncs.append(["no_connect", ["at", *_pt(at)], ["uuid", _uid()]])

    def label(self, name, at, rot=0):
        self.items.append(["label", esc(name), ["at", *_pt(at), rot],
                           _fx(1.27, _JUSTIFY[rot]), ["uuid", _uid()]])

    def _shaped(self, kind, name, at, rot, shape):
        item = [kind, esc(name), ["shape", shape], ["at", *_pt(at), rot]]
        if kind == "global_label":
            item.append(["fields_autoplaced", "yes"])
        item += [_fx(1.27, _LABEL_JUSTIFY[rot]), ["uuid", _uid()]]
        if kind == "global_label":
            p = _pt(at)
            item.append(["property", Str("Intersheetrefs"), Str("${INTERSHEET_REFS}"), ["at", p[0], p[1], 0],
                         ["hide", "yes"], ["show_name", "no"], ["do_not_autoplace", "no"], _fx()])
        self.items.append(item)

    def global_label(self, name, at, rot=0, shape="passive"):
        self._shaped("global_label", name, at, rot, shape)

    def hier_label(self, name, at, rot=0, shape="passive"):
        self._shaped("hierarchical_label", name, at, rot, shape)

    def text(self, text, at, size=1.5):
        self.items.append(["text", esc(text), ["exclude_from_sim", "yes"], ["at", *_pt(at), 0],
                           _fx(size, "left top"), ["uuid", _uid()]])

    def sheet_symbol(self, name, file, at, size, pins, uuid, page):
        """Hierarchical sheet symbol on this (root) sheet. pins: [(name, shape, side, y_offset)] with side
        'l' (pin on the left edge, text to the right) or 'r'; y_offset in mm from the top edge.
        `uuid` and `page` are kept from the existing sheet so sub-sheet instance paths stay valid."""
        x, y = _pt(at)
        w, h = size
        fx = lambda j: _fx(1.27, j)
        sh = ["sheet", ["at", x, y], ["size", w, h], ["exclude_from_sim", "no"], ["in_bom", "yes"],
              ["on_board", "yes"], ["dnp", "no"], ["fields_autoplaced", "yes"],
              ["stroke", ["width", 0.1524], ["type", "solid"]], ["fill", ["color", 0, 0, 0, 0]],
              ["uuid", Str(uuid)],
              ["property", Str("Sheetname"), Str(name), ["at", x, _r(y - 0.7116), 0], ["show_name", "no"],
               ["do_not_autoplace", "no"], fx("left bottom")],
              ["property", Str("Sheetfile"), Str(file), ["at", x, _r(y + h + 0.7116), 0], ["show_name", "no"],
               ["do_not_autoplace", "no"], fx("left top")]]
        pos = {}
        for pname, shape, side, dy in pins:
            px = x if side == "l" else _r(x + w)
            py = _r(y + dy)
            sh.append(["pin", Str(pname), shape, ["at", px, py, 180 if side == "l" else 0],
                       ["uuid", _uid()], fx("left" if side == "l" else "right")])
            pos[pname] = (px, py)
        sh.append(["instances", ["project", Str(self.project), ["path", Str("/" + str(self.uuid)), ["page", Str(str(page))]]]])
        self.sheets.append(sh)
        return pos

    # ---- conveniences --------------------------------------------------
    def connect(self, p1, p2, via="h"):
        """Orthogonal route p1 -> p2: via 'h' goes horizontal first, 'v' vertical first."""
        p1, p2 = _pt(p1), _pt(p2)
        if p1[0] == p2[0] or p1[1] == p2[1]:
            self.wire([p1, p2])
        else:
            corner = (p2[0], p1[1]) if via == "h" else (p1[0], p2[1])
            self.wire([p1, corner, p2])

    def stub(self, pin_xy, direction, length=2.54, label=None, kind="local", shape="passive"):
        """Wire from a pin outward ('r','l','u','d' or right/left/up/down); optional label at the end,
        oriented so its text points away from the pin. Returns the end point."""
        dx, dy, rot = _DIRS[direction[0].lower()]
        end = _pt((pin_xy[0] + dx * length, pin_xy[1] + dy * length))
        self.wire([pin_xy, end])
        if label:
            if kind == "local":
                self.label(label, end, rot)
            elif kind == "global":
                self.global_label(label, end, rot, shape)
            else:
                self.hier_label(label, end, rot, shape)
        return end

    def auto_junctions(self):
        """Junction wherever 3+ connections meet (wire ends count 1, a wire passing through counts 2, pins 1)."""
        segs = [tuple(_pt(tuple(float(v) for v in xy[1:])) for xy in w[1][1:]) for w in self.wires]
        pins = [transform(p["x"], p["y"], i.at, i.rot, i.mirror) for i in self.instances for p in i.pins]
        cands = {pt for s in segs for pt in s} | set(pins)
        for c in cands:
            n = sum(s.count(c) for s in segs) + pins.count(c)
            for a, b in segs:
                if c not in (a, b) and abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) < 1e-6 \
                        and min(a[0], b[0]) - 1e-6 <= c[0] <= max(a[0], b[0]) + 1e-6 \
                        and min(a[1], b[1]) - 1e-6 <= c[1] <= max(a[1], b[1]) + 1e-6:
                    n += 2
            if n >= 3:
                self.junction(c)

    # ---- output --------------------------------------------------------
    def save(self, path):
        self.auto_junctions()
        tree = ["kicad_sch", ["version", "20260306"], ["generator", Str("eeschema")],
                ["generator_version", Str("10.0")], ["uuid", Str(self.uuid)], ["paper", Str(self.paper)]]
        if self.title_block:
            tree.append(self.title_block)
        tree.append(["lib_symbols"] + list(self.lib_syms.values()))
        tree += [["junction", ["at", *j], ["diameter", 0], ["color", 0, 0, 0, 0], ["uuid", _uid()]]
                 for j in self.junctions]
        tree += self.ncs + self.wires + self.items + self.symbols + self.sheets
        tree.append(["sheet_instances", ["path", Str("/"), ["page", Str("1")]]])
        tree.append(["embedded_fonts", "no"])
        with open(path, "w") as f:
            f.write(dumps(tree) + "\n")
