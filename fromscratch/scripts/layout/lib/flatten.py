import os
"""Flatten a hierarchical SPICE netlist (subckts incl. sky130 std cells) into device-level netlist for netgen."""
import os, re, sys
STD = os.path.join(os.environ["PDKPATH"], "libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice")
def read_subckts(path, subs):
    cur = None; body = []
    cont = ""
    for raw in open(path):
        l = raw.rstrip("\n")
        if l.startswith("+"): cont += " " + l[1:].strip(); continue
        if cont: yield_line(cont, subs, state); cont = ""
        yield_line(l, subs, state) if False else None
def load(path, subs):
    lines = []; buf = None
    for raw in open(path):
        l = raw.rstrip("\n")
        if l.startswith("+") and buf is not None: buf += " " + l[1:].strip(); continue
        if buf is not None: lines.append(buf)
        buf = l
    if buf is not None: lines.append(buf)
    cur = None
    for l in lines:
        if l.startswith(".subckt"):
            t = l.split(); cur = (t[1], t[2:], []); subs[t[1]] = cur
        elif l.startswith(".ends"): cur = None
        elif cur is not None and l.strip() and not l.startswith("*"): cur[2].append(l)
def flatten(top, subs, prefix="", netmap=None, out=None, keepcells=()):
    name, ports, body = subs[top]
    for l in body:
        t = l.split()
        if not t: continue
        inst = t[0]
        if inst[0] in "XxMmCcRr":
            # find model/subckt name: last non-param token
            toks = [x for x in t[1:] if "=" not in x]
            mname = toks[-1]; nets = toks[:-1]
            params = [x for x in t[1:] if "=" in x]
            if mname in subs and mname not in keepcells:
                _, sports, _ = subs[mname]
                nm = {}
                for p, n in zip(sports, nets): nm[p] = netmap.get(n, n) if netmap else n
                # internal nets get prefixed
                sub = subs[mname]
                internal = set()
                for bl in sub[2]:
                    bt = bl.split(); bt2 = [x for x in bt[1:] if "=" not in x][:-1]
                    for n in bt2:
                        if n not in nm and not n.replace(".", "").isdigit(): internal.add(n)
                for n in internal: nm[n] = prefix + inst + "." + n
                flatten(mname, subs, prefix + inst + ".", nm, out, keepcells)
            else:
                mn = [netmap.get(n, prefix + n if False else n) if netmap else n for n in nets]
                out.append(prefix + inst + " " + " ".join(mn) + " " + mname + " " + " ".join(params))
        else:
            out.append(l)
def main(src, top, dst):
    subs = {}; load(STD, subs); load(src, subs)
    nm = {p: p for p in subs[top][1]}
    out = []
    flatten(top, subs, "", nm, out)
    # internal nets in top body keep their names (no prefix) ; std/comp internals were prefixed
    hdr = f".subckt {top} " + " ".join(subs[top][1])
    open(dst, "w").write(hdr + "\n" + "\n".join(out) + "\n.ends\n")
if __name__ == "__main__":
    main(*sys.argv[1:4])
