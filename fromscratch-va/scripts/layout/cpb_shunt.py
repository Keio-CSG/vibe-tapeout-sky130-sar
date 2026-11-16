"""Optional supported-size linear TOP MIM banks in the unused logic flanks."""
import fp,devgen,cpb_routes

def add(T,cdP,cdN):
    m=devgen.get_mim(27,18.92);width=2*fp.XC;places={}
    for side,cd,mirror in [('P',cdP,False),('N',cdN,True)]:
        f=(lambda x:width-x) if mirror else (lambda x:x)
        tops=[];grounds=[]
        for row in range(2):
            for col in range(3):
                x=5+30*col;y=156+21.8*row;dx=x-m.bbox[0];dy=y-m.bbox[1]
                T.c.use(m.cell,'shunt%s_%d_%d'%(side,row,col),width-dx if mirror else dx,dy,'MY' if mirror else 'R0')
                top=(f(dx+(m.top[0]+m.top[2])/2),dy+(m.top[1]+m.top[3])/2)
                ground=(f(dx+(m.bot[0]+m.bot[2])/2),dy+(m.bot[1]+m.bot[3])/2)
                # via4 cannot overlap a MIM contact tile. Exit on M4 below it.
                contact=(top[0],y-1.2)
                T.seg('metal4',top[0],contact[1],top[0],y+.8,.8)
                cpb_routes.via45(T,*contact);cpb_routes.via45(T,*ground)
                tops.append(contact);grounds.append(ground)
        ytop=149.0;yground=199.5
        for x,y in tops:T.seg('metal5',x,ytop,x,y,1.6)
        for x,y in grounds:T.seg('metal5',x,y,x,yground,1.6)
        xroute=f(102.46);a=cd.pin('TOP');ysource=a[2]-1.72
        T.seg('metal4',a[1],a[2],a[1],ysource,.8);cpb_routes.via45(T,a[1],ysource)
        T.seg('metal5',a[1],ysource,xroute,ysource,1.6)
        # Overpass both full-width supply bars on M4.
        gs=115.455;va=129.035
        for low,high in [(ysource,gs-4),(gs+4,va-4),(va+4,ytop)]:
            T.seg('metal5',xroute,low,xroute,high,1.6)
        for crossing in [gs,va]:
            cpb_routes.via45(T,xroute,crossing-4);cpb_routes.via45(T,xroute,crossing+4)
            T.seg('metal4',xroute,crossing-4,xroute,crossing+4,1.6)
        T.seg('metal5',min(xroute,min(x for x,_ in tops)),ytop,max(xroute,max(x for x,_ in tops)),ytop,1.6)
        # Ground each flank at its analog edge boundary. Cross VDDA on M4.
        edge=f(.8);cross=f(5.)
        T.seg('metal5',edge,gs,edge,va-4,1.6)
        for y in [va-4,va+4]:T.seg('metal5',edge,y,cross,y,1.6);cpb_routes.via45(T,cross,y)
        T.seg('metal4',cross,va-4,cross,va+4,1.6)
        T.seg('metal5',edge,va+4,edge,yground,1.6)
        T.seg('metal5',min(edge,min(x for x,_ in grounds)),yground,max(edge,max(x for x,_ in grounds)),yground,1.6)
        places['shunt'+side]=dict(bbox=[f(5+88.86) if mirror else 5,156,f(5) if mirror else 93.86,197.12])
    return places
