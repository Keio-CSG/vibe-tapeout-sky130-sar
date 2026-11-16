import os
"""Minimal magic .mag writer. Units: um in API, 1 internal unit = 0.005 um (magscale 1 2 in sky130A)."""
import os, collections
U = 200
REG = {}          # cell name -> bbox (internal units)
SEARCH = []       # directories holding .mag files
def iu(x): return int(round(x * U))
def file_bbox(name):
    import re
    for d in SEARCH:
        p = os.path.join(d, name + ".mag")
        if os.path.exists(p):
            t = open(p).read()
            m = re.search(r"string FIXED_BBOX (-?\d+) (-?\d+) (-?\d+) (-?\d+)", t)
            if m: return tuple(int(v) for v in m.groups())
            xs = []; ys = []
            for l in t.split("\n"):
                if l.startswith("rect "):
                    a = l.split(); xs += [int(a[1]), int(a[3])]; ys += [int(a[2]), int(a[4])]
            return (min(xs), min(ys), max(xs), max(ys)) if xs else (0, 0, 1, 1)
    raise FileNotFoundError(name)
class Cell:
    def __init__(self, name):
        self.name = name; self.layers = collections.defaultdict(list); self.labels = []; self.uses = []; self.ports = 0
    def rect(self, layer, x1, y1, x2, y2):
        a, b, c, d = iu(x1), iu(y1), iu(x2), iu(y2)
        if a > c: a, c = c, a
        if b > d: b, d = d, b
        assert c > a and d > b, (layer, x1, y1, x2, y2)
        self.layers[layer].append((a, b, c, d))
    def label(self, text, layer, x1, y1, x2, y2, port=True, kind="signal bidirectional"):
        a, b, c, d = iu(x1), iu(y1), iu(x2), iu(y2)
        self.labels.append((text, layer, a, b, c, d, port, kind))
    def use(self, cell, inst, x, y, orient="R0", bbox=None):
        self.uses.append((cell, inst, iu(x), iu(y), orient, bbox))
    def bbox(self):
        xs = []; ys = []
        for rs in self.layers.values():
            for r in rs: xs += [r[0], r[2]]; ys += [r[1], r[3]]
        for cell, inst, x, y, o, bb in self.uses:
            b = bb or REG.get(cell) or file_bbox(cell)
            sx = -1 if o in ("MY", "R180") else 1; sy = -1 if o in ("MX", "R180") else 1
            x1, x2 = sorted((x + sx * b[0], x + sx * b[2])); y1, y2 = sorted((y + sy * b[1], y + sy * b[3]))
            xs += [x1, x2]; ys += [y1, y2]
        return (min(xs), min(ys), max(xs), max(ys)) if xs else (0, 0, 1, 1)
    def write(self, d):
        if d not in SEARCH: SEARCH.append(d)
        REG[self.name] = self.bbox()
        L = ["magic", "tech sky130A", "magscale 1 2", "timestamp 0"]
        for lay, rs in self.layers.items():
            L.append(f"<< {lay} >>")
            seen = set()
            for r in rs:
                if r in seen: continue
                seen.add(r); L.append("rect %d %d %d %d" % r)
        for cell, inst, x, y, o, bb in self.uses:
            tr = {"R0": (1, 0, 0, 1), "MX": (1, 0, 0, -1), "MY": (-1, 0, 0, 1), "R180": (-1, 0, 0, -1)}[o]
            L += [f"use {cell} {inst}", "timestamp 0", f"transform {tr[0]} {tr[1]} {x} {tr[2]} {tr[3]} {y}"]
            L.append("box %d %d %d %d" % (bb or REG.get(cell) or file_bbox(cell)))
        if self.labels:
            L.append("<< labels >>")
            n = 1
            for text, layer, a, b, c, dd, port, kind in self.labels:
                L.append(f"flabel {layer} {a} {b} {c} {dd} 0 FreeSans 80 0 0 0 {text}")
                if port: L.append(f"port {n} nsew {kind}"); n += 1
        L.append("<< end >>")
        open(os.path.join(d, self.name + ".mag"), "w").write("\n".join(L) + "\n")
