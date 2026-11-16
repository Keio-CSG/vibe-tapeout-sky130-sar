"""Optional CP-B physical fixes. The top generator enables each independently.
Grounded output-clock shields and metal5 power trunks with metal4 overpasses.
"""
def via23(T,x,y):
    T.rect('via2',x-.14,y-.14,x+.14,y+.14)
    T.rect('metal2',x-.25,y-.25,x+.25,y+.25)
    T.rect('metal3',x-.2,y-.3,x+.2,y+.3)

def via34_narrow(T,x,y):
    T.rect('via3',x-.16,y-.16,x+.16,y+.16)
    T.rect('metal3',x-.2,y-.3,x+.2,y+.3)
    T.rect('metal4',x-.17,y-.2,x+.17,y+.2)

def via45(T,x,y):
    T.rect('via4',x-.59,y-.59,x+.59,y+.59)
    for layer in ['metal4','metal5']:T.rect(layer,x-.8,y-.8,x+.8,y+.8)

def stack5(T,x,y,lower=1):
    for k in range(lower,6):T.rect('metal%d'%k,x-.8,y-.8,x+.8,y+.8)
    for layer,size,start in [('via1',.26,1),('via2',.28,2),('via3',.32,3)]:
        if lower>start:continue
        for dx in [-.44,0,.44]:
            for dy in [-.44,0,.44]:
                T.rect(layer,x+dx-size/2,y+dy-size/2,x+dx+size/2,y+dy+size/2)
    via45(T,x,y)

def shields(T,lg,cmp_):
    # Above the jogs, the logic pins have 1.38 um pitch; a .34 um via pad
    # permits >=.30 um clearance from the adjacent .40 um signal wires.
    upper=[(lg.pin('clkc')[1]+lg.pin('coN')[1])/2,
           (lg.pin('coP')[1]+lg.pin('trkA_b')[1])/2]
    ytop=lg.pin('coN')[2]-1.5
    ybottom=lg.pin('coN')[2]-23.0
    T.seg('metal2',105.86,ytop,upper[-1],ytop,.4)
    for x in upper:
        T.seg('metal4',x,ybottom,x,ytop,.3)
        via23(T,x,ytop);via34_narrow(T,x,ytop)
    lower=[(cmp_.pin('CLK')[1]+cmp_.pin('OUTN')[1])/2,
           (cmp_.pin('OUTP')[1]+cmp_.pin('TRKAB')[1])/2]
    y0=cmp_.macro_bbox()[3]+2.0
    # Stay below every signal's horizontal jog.
    y1=123.0
    T.seg('metal2',105.86,y0,107.8,y0,.4)
    via23(T,107.8,y0)
    T.seg('metal3',107.8,y0,lower[-1],y0,.4)
    for x in lower:
        T.seg('metal4',x,y0,x,y1,.3);T.via34(x,y0)

def power(T,lg,cmp_,bank_y,ym):
    import fp
    width=2*fp.XC
    outside_left=lg.macro_bbox()[0]-3.11
    outside_right=lg.macro_bbox()[2]+3.11
    yss=bank_y+1.935;ya=bank_y+19.515
    gs=yss+2;va=ya-2
    # Offset edge stacks away from the metal3 reference buses.
    for y,ypin in [(gs,yss),(va,ya)]:
        T.seg('metal5',1.0,y,width-1.0,y,2.0)
        for x in [.8,width-.8]:
            T.seg('metal1',x,ypin,x,y,1.6);stack5(T,x,y)
    for mirror in [False,True]:
        f=(lambda x:width-x) if mirror else (lambda x:x)
        xg=f(105.86);xa=f(109.2)
        yc=cmp_.pin('VSS')[2];yv=cmp_.pin('VDD')[2]
        # Ground's lower stack sits beyond the CDAC MIM keepout.
        T.seg('metal2',xg,yc,xa,yc,.4);stack5(T,xa,yc,lower=2)
        T.seg('metal5',xg,yc,xa,yc,1.6)
        stack5(T,xa,yv,lower=2)
        # VDDA passes over the ground bar on metal4.
        T.seg('metal5',xa,yv,xa,gs-4,1.6);via45(T,xa,gs-4)
        T.seg('metal4',xa,gs-4,xa,gs+4,1.6);via45(T,xa,gs+4)
        T.seg('metal5',xa,gs+4,xa,va,1.6)
        # Ground passes over the VDDA bar on metal4.
        if __import__('os').environ.get('CPB_TOPSHUNT')=='1':
            # Let the TOP M5 escape cross this spine; the existing M2 VSS
            # backbone still connects the two grounded portions.
            source_y=cmp_.pin('INN')[2]-1.72
            T.seg('metal5',xg,yc,xg,source_y-4,1.6)
            T.seg('metal5',xg,source_y+4,xg,va-4,1.6)
        else:T.seg('metal5',xg,yc,xg,va-4,1.6)
        via45(T,xg,va-4)
        T.seg('metal4',xg,va-4,xg,va+4,1.6);via45(T,xg,va+4)
        yg=lg.pin('coN')[2]+.5
        T.seg('metal5',xg,va+4,xg,yg,1.6)
        xo=outside_right if mirror else outside_left
        T.seg('metal5',xg,yg,xo,yg,1.6);stack5(T,xo,yg,lower=2)
        xs=lg.tx(lg.bbox[2]-1.4) if mirror else lg.tx(-1.2)
        # The actual right VSS strap is W+1.2; bbox max=W+2.6.
        T.seg('metal2',xs,yg,xo,yg,.5)
        T.seg('metal2',xs,yg,xs,lg.ty(-.3)+.1,.5)
    # Feed both digital supply straps through an outside metal5 spine.
    yv=lg.ty(2.72)
    T.seg('metal5',outside_left,ym,outside_right,ym,1.6)
    stack5(T,lg.tx(-2),ym,lower=2)
    for xo,xs in [(outside_left,lg.tx(-2)),(outside_right,lg.tx(lg.bbox[2]-.6))]:
        T.seg('metal5',xo,yv,xo,ym,1.6);stack5(T,xo,yv,lower=2)
        T.seg('metal2',xo,yv,xs,yv,.5)
