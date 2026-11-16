import os
"""Std-cell row placement designs (sky130_fd_sc_hd). Units um."""
import os, shutil, re
from maglib import Cell, iu
import stdlib
CELLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cells")
VARIANTS = {"dig": {"VPWR": "VDDD", "VPB": "VDDD", "VGND": "VSS", "VNB": "VSS"}, "drv": {"VPWR": "VREFP", "VPB": "VREFP", "VGND": "VSS", "VNB": "VSS"}, "ana": {"VPWR": "VDDA", "VPB": "VDDA", "VGND": "VSS", "VNB": "VSS"}}
def ensure(cell, variant=None):
    base = f"sky130_fd_sc_hd__{cell}"; name = base if variant is None else f"{base}__{variant}"
    dst = os.path.join(CELLS, name + ".mag")
    if not os.path.exists(dst):
        if variant is None: shutil.copy(stdlib.info(cell)["path"], dst)
        else:
            mp = VARIANTS[variant]; out = []
            for l in open(stdlib.info(cell)["path"]):
                if l.startswith(("flabel", "rlabel")):
                    t = l.rstrip("\n").split(" ")
                    if t[-1] in mp: t[-1] = mp[t[-1]]
                    l = " ".join(t) + "\n"
                out.append(l)
            open(dst, "w").writelines(out)
    return name
class Placed:
    def __init__(self, cell, inst, x, y, flip, net_of):
        self.cell, self.inst, self.x, self.y, self.flip = cell, inst, x, y, flip; self.net_of = net_of; self.info = stdlib.info(cell)
    def pin(self, name):
        """list of global pin rects (x1,y1,x2,y2)"""
        out = []
        for (a, b, c, d) in self.info["pins"][name]:
            if self.flip: b, d = self.info["h"] - d, self.info["h"] - b
            out.append((self.x + a, self.y + b, self.x + c, self.y + d))
        return out
def place(c, cell, inst, x, y, flip=False, variant=None):
    n = ensure(cell, variant); i = stdlib.info(cell)
    if flip: c.use(n, inst, x, y + i["h"], "MX")
    else: c.use(n, inst, x, y, "R0")
    return Placed(cell, inst, x, y, flip, None)
def pin_stack(c, x, y, nx=None):
    """mcon + met1 pad + via1 + met2 pad at (x,y); if nx is given and differs, the via1/met2 stack moves to nx via a short met1 jog."""
    c.rect("viali", x - 0.085, y - 0.085, x + 0.085, y + 0.085)
    if nx is None or abs(nx - x) < 0.03:
        c.rect("metal1", x - 0.16, y - 0.13, x + 0.16, y + 0.13); c.rect("via1", x - 0.13, y - 0.13, x + 0.13, y + 0.13); c.rect("metal2", x - 0.13, y - 0.16, x + 0.13, y + 0.16)
    else:
        c.rect("metal1", min(x, nx) - 0.16, y - 0.13, max(x, nx) + 0.16, y + 0.13)
        c.rect("via1", nx - 0.13, y - 0.13, nx + 0.13, y + 0.13); c.rect("metal2", nx - 0.13, y - 0.16, nx + 0.13, y + 0.16)
