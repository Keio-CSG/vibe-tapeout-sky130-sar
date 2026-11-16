"""Digital SAR logic block: std-cell rows + routing. Builds cell 'dig' and returns placement info."""
import sys, os, re, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from maglib import Cell
import stdlib, netlist, stdplace
from router import Router
HERE = os.path.dirname(os.path.abspath(__file__))
NETL = os.path.join(HERE, "..", "..", "schematic", "sar_adc_m3.spice")
ROWH = 2.72
def order(insts, which):
    """sort instances into placement order"""
    def key(i):
        n = i["name"]
        m = re.match(r"X(fq|g|tken|tkcg|fn|fp|i1p|i1n|ob|drp|drn)(\d+)", n)
        if m:
            idx = int(m.group(2)); typ = {"g": 0, "tken": 0.7, "tkcg": 0.8, "fq": 1, "fn": 2, "fp": 3, "i1p": 4, "i1n": 5, "ob": 6}[m.group(1)] if m.group(1) in ("g","tken","tkcg","fq","fn","fp","i1p","i1n","ob") else 9
            return (1, idx, typ, n)
        LOOP = ["Xnda", "Xndb", "Xorv", "Xdly_cap0", "Xdly_cap1", "Xbuf_vcap", "Xdly_vd0", "Xdly_vd1", "Xdly_vd2", "Xnor_ck", "Xbuf_ck"]
        if n in LOOP: return (0, 0, LOOP.index(n), n)
        return (0, 1, 0, n)
    return sorted(insts, key=key)
def build_rows(c, cells, rowwidth, tap_pitch=12.0, x0=0.0, y0=0.0, vnames=("VSS", "VDDD"), gap=0.0, variant=None):
    """place cells in alternating rows. returns list of Placed with .net conn"""
    placed = []; x = x0; r = 0; xs_since_tap = 0.0
    def new_row(): return y0 + r * ROWH
    flip = (lambda r: (r % 2 == 1)) if gap == 0 else (lambda r: False)
    rows = [[]]
    for inst in cells:
        w = stdlib.info(inst["cell"])["w"]
        cur = rows[-1]; wsum = sum(stdlib.info(i["cell"])["w"] for i in cur) + 0.46 * (len(cur) // 3 + 2)
        if cur and wsum + w > rowwidth: rows.append([])
        rows[-1].append(inst)
    for r, row in enumerate(rows):
        y = y0 + r * (ROWH + gap); fl = flip(r); x = x0; since = 0.0
        stdplace.place(c, "tapvpwrvgnd_1", f"tap{r}_0", x, y, fl, variant); x += stdlib.info("tapvpwrvgnd_1")["w"]; since = 0
        for k, inst in enumerate(row):
            w = stdlib.info(inst["cell"])["w"]
            if since + w > tap_pitch:
                stdplace.place(c, "tapvpwrvgnd_1", f"tap{r}_{k}", x, y, fl, variant); x += 0.46; since = 0
            p = stdplace.place(c, inst["cell"], inst["name"], x, y, fl, variant); p.conn = inst["conn"]; placed.append(p)
            x += w; since += w
        stdplace.place(c, "tapvpwrvgnd_1", f"tap{r}_e", x, y, fl, variant); x += 0.46
        rows[r] = (x - x0)
    return placed, rows
if __name__ == "__main__":
    ports, insts, other = netlist.parse_top(NETL)
    dig = [i for i in insts if not re.match(r"Xdr[pn]\d+_\d+", i["name"])]
    drv = [i for i in insts if re.match(r"Xdr[pn]\d+_\d+", i["name"])]
    c = Cell("dig")
    placed, rows = build_rows(c, order(dig, "dig"), 80.0)
    print(len(placed), "cells; row widths", [round(r, 1) for r in rows], "height", len(rows) * ROWH)
    c.write(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cells"))
