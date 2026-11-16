import os
import re, collections
STD = os.path.join(os.environ["PDKPATH"], "libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice")
_pins = None
def stdpins():
    global _pins
    if _pins is None:
        _pins = {}
        for l in open(STD):
            if l.startswith(".subckt sky130_fd_sc_hd__"):
                t = l.split(); _pins[t[1][len("sky130_fd_sc_hd__"):]] = t[2:]
    return _pins
def parse_top(path, top="sar_adc"):
    """returns (pins, insts) ; insts: list of dict(name,cell,conn{pin:net}) for std cells, plus 'other' lines"""
    lines = []; cur = None; out = []
    for l in open(path):
        l = l.rstrip("\n")
        if l.startswith(".subckt "):
            t = l.split(); cur = t[1]; 
            if cur == top: ports = t[2:]
            continue
        if l.startswith(".ends"): cur = None; continue
        if cur == top and l and not l.startswith("*"): out.append(l)
    insts = []; other = []
    for l in out:
        t = l.split()
        if t[-1].startswith("sky130_fd_sc_hd__"):
            cell = t[-1][len("sky130_fd_sc_hd__"):]; pn = stdpins()[cell]; nets = t[1:-1]
            insts.append(dict(name=t[0], cell=cell, conn=dict(zip(pn, nets))))
        else: other.append(l)
    return ports, insts, other
if __name__ == "__main__":
    ports, insts, other = parse_top(os.path.join(HERE, "..", "..", "schematic", "sar_adc_m3.spice"))
    import stdlib
    print(ports); cnt = collections.Counter(i["cell"] for i in insts); tot = 0
    for c, n in sorted(cnt.items()):
        w = stdlib.info(c)["w"]; tot += w * n * 2.72; print(f"{c:18s} {n:3d} x {w:5.2f}")
    print("total cell area", tot, "um2;", len(insts), "cells")
    print([o.split()[0] for o in other][:20], len(other))
