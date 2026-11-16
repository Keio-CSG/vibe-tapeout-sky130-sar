import os
"""sky130_fd_sc_hd cell info from the PDK .mag files (size, pins on li1)."""
import os, re, json
SC = os.path.join(os.environ["PDKPATH"], "libs.ref/sky130_fd_sc_hd/mag")
_cache = {}
def info(cell):
    """cell given without prefix (e.g. 'dfrtp_1'). returns dict(w,h, pins{name:[(x1,y1,x2,y2) um on locali]}, path)"""
    if cell in _cache: return _cache[cell]
    p = os.path.join(SC, f"sky130_fd_sc_hd__{cell}.mag")
    t = open(p).read()
    bb = re.search(r"string FIXED_BBOX (-?\d+) (-?\d+) (-?\d+) (-?\d+)", t); x1, y1, x2, y2 = map(int, bb.groups())
    pins = {}
    for m in re.finditer(r"flabel (\w+) \w+ (-?\d+) (-?\d+) (-?\d+) (-?\d+) \d+ \S+ \d+ \d+ \d+ \d+ (\S+)\nport", t):
        layer, a, b, c, d, name = m.groups(); a, b, c, d = map(int, (a, b, c, d))
        if layer == "locali": pins.setdefault(name, []).append((a / 200, b / 200, c / 200, d / 200))
    r = dict(w=(x2 - x1) / 200, h=(y2 - y1) / 200, x0=x1 / 200, y0=y1 / 200, pins=pins, path=p)
    _cache[cell] = r; return r
if __name__ == "__main__":
    for c in ["dfrtp_1","dfrtn_1","and3b_1","nor3_1","or2_1","buf_2","buf_4","clkbuf_16","inv_1","inv_2","inv_16","dlygate4sd3_1","dlygate4sd1_1","tapvpwrvgnd_1","inv_4","inv_8"]:
        i = info(c); print(c, i["w"], i["h"], {k: v[0] for k, v in i["pins"].items() if k not in ("VPB","VNB")})
