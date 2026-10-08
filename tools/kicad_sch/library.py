"""Lazy reader for the Aharoni lab symbol library."""
import copy
import os

from .sexpr import Str, find, find_all, parse


def default_root():
    return os.path.expanduser(os.environ.get("AHARONI_LAB_KICAD_LIB", "~/Projects/kicad-lab-library"))


class Library:
    def __init__(self, root=None):
        self.root = root or default_root()
        self._files = {}   # lib nickname -> {symbol name: raw definition}
        self._flat = {}    # lib_id -> flattened, embeddable definition

    def _load(self, nick):
        if nick not in self._files:
            path = os.path.join(self.root, "symbols", nick + ".kicad_sym")
            with open(path) as f:
                tree = parse(f.read())
            self._files[nick] = {s[1]: s for s in find_all(tree, "symbol")}
        return self._files[nick]

    def _flatten(self, nick, name):
        defs = self._load(nick)
        if name not in defs:
            raise KeyError("symbol %s:%s not found in %s" % (nick, name, self.root))
        sym = copy.deepcopy(defs[name])
        ext = find(sym, "extends")
        if ext is None:
            return sym
        # Derived symbol: parent graphics/pins + child properties (KiCad embeds it flattened).
        parent = self._flatten(nick, ext[1])
        parent[1] = Str(name)
        for sub in find_all(parent, "symbol"):   # "Parent_1_1" -> "Child_1_1"
            sub[1] = Str(name + sub[1][len(ext[1]):])
        for prop in find_all(sym, "property"):
            old = [p for p in find_all(parent, "property") if p[1] == prop[1]]
            if old:
                parent[parent.index(old[0])] = prop
            else:
                parent.insert(parent.index(find_all(parent, "property")[-1]) + 1, prop)
        return parent

    def symbol(self, lib_id):
        """Embeddable definition, named with the full 'Lib:Name' form."""
        if lib_id not in self._flat:
            nick, name = lib_id.split(":", 1)
            sym = self._flatten(nick, name)
            sym[1] = Str(lib_id)
            self._flat[lib_id] = sym
        return copy.deepcopy(self._flat[lib_id])

    def pins(self, lib_id, unit=None):
        """List of dicts: unit, number, name, type, x, y, angle, length.
        x, y are symbol coordinates (Y up); unit 0 pins are common to all units."""
        out = []
        for sub in find_all(self.symbol(lib_id), "symbol"):
            u, style = (int(v) for v in sub[1].rsplit("_", 2)[1:])
            if style == 2:   # alternate (De Morgan) body: not used here
                continue
            for p in find_all(sub, "pin"):
                at = find(p, "at")
                out.append(dict(unit=u, number=str(find(p, "number")[1]), name=str(find(p, "name")[1]),
                                type=p[1], x=float(at[1]), y=float(at[2]), angle=float(at[3]),
                                length=float(find(p, "length")[1])))
        return [p for p in out if unit is None or p["unit"] in (0, unit)]
