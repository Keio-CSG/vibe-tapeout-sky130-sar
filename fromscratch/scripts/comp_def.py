from spicegen import fet
def comparator(p):
    """StrongARM latch, NMOS input. ports: CK inp inn oa ob VDD VSS ; oa falls when inp>inn"""
    L=[".subckt comp CK inp inn oa ob VDD VSS"]
    L.append(fet("tail","n","t","CK","VSS","VSS",p["wtail"],p["ltail"]))
    L.append(fet("ina","n","xa","inp","t","VSS",p["win"],p["lin"]))
    L.append(fet("inb","n","xb","inn","t","VSS",p["win"],p["lin"]))
    L.append(fet("lna","n","oa","ob","xa","VSS",p["wln"],p["lln"]))
    L.append(fet("lnb","n","ob","oa","xb","VSS",p["wln"],p["lln"]))
    L.append(fet("lpa","p","oa","ob","VDD","VDD",p["wlp"],p["llp"]))
    L.append(fet("lpb","p","ob","oa","VDD","VDD",p["wlp"],p["llp"]))
    for n,d in (("ra","oa"),("rb","ob"),("rxa","xa"),("rxb","xb")):
        L.append(fet(n,"p",d,"CK","VDD","VDD",p["wr"],0.15))
    if p.get("treset"):   # reset the tail node to VDD during the reset phase (removes common-mode memory)
        L.append(fet("rt","p","t","CK","VDD","VDD",p["treset"],0.15))
    L.append(".ends comp")
    return "\n".join(L)
DEF=dict(wtail=4,ltail=0.15,win=5,lin=0.15,wln=2,lln=0.15,wlp=4,llp=0.15,wr=2)
