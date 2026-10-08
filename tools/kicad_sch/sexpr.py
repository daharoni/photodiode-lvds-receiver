"""Minimal S-expression parser/printer in KiCad style (tabs).

Quoted strings are parsed to `Str` (raw text between quotes, escapes kept), so
they are re-emitted unchanged. Bare atoms are plain `str`.
"""


class Str(str):
    """A quoted string. Holds the raw (still escaped) text."""


def esc(s):
    return Str(str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n"))


def parse(text):
    """Parse one top-level S-expression into nested lists."""
    stack, cur, i, n = [], [], 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c == "(":
            stack.append(cur)
            cur = []
            i += 1
        elif c == ")":
            done, cur = cur, stack.pop()
            cur.append(done)
            i += 1
        elif c == '"':
            j = i + 1
            while text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            cur.append(Str(text[i + 1:j]))
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in " \t\r\n()":
                j += 1
            cur.append(text[i:j])
            i = j
    return cur[0]


def num(v):
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _atom(a):
    if isinstance(a, Str):
        return '"%s"' % a
    if isinstance(a, float):
        return num(a)
    return str(a)


def dumps(node, depth=0):
    tab = "\t" * depth
    if not isinstance(node, list):
        return tab + _atom(node)
    subs = [x for x in node if isinstance(x, list)]
    if not subs:
        return tab + "(" + " ".join(_atom(a) for a in node) + ")"
    if node[0] == "pts":
        return tab + "(pts\n" + "\t" * (depth + 1) + " ".join(dumps(x) for x in subs) + "\n" + tab + ")"
    k = 0
    while k < len(node) and not isinstance(node[k], list):
        k += 1
    out = [tab + "(" + " ".join(_atom(a) for a in node[:k])]
    for x in node[k:]:
        out.append(dumps(x, depth + 1))
    out.append(tab + ")")
    return "\n".join(out)


def find(node, key):
    """First child list whose head is `key`, else None."""
    for x in node:
        if isinstance(x, list) and x and x[0] == key:
            return x
    return None


def find_all(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]
