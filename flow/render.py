#!/usr/bin/env python3
"""Render GDS polygons and block outlines to a PNG using open Python packages."""
from pathlib import Path
import argparse
from collections import defaultdict
import gdstk
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.patches import Rectangle

def render(path,cell,png):
    lib=gdstk.read_gds(str(path))
    c=next(c for c in lib.cells if c.name==cell)
    bb=c.bounding_box();center_x=(bb[0][0]+bb[1][0])/2
    layers=defaultdict(list)
    for p in c.get_polygons():
        if p.layer in range(64,73) and p.datatype==20 or (p.layer,p.datatype)==(89,44):
            layers[p.layer].append(p.points)
    colors={64:'#57a773',65:'#8bbf83',66:'#d7ae4c',67:'#9eb8c6',68:'#7283b9',69:'#cf7e91',70:'#8e85bb',71:'#76c3bf',72:'#a4d0c8',81:'#b7b7b7'}
    fig,ax=plt.subplots(figsize=(13,7),dpi=180)
    for layer,poly in sorted(layers.items()):
        ax.add_collection(PolyCollection(poly,facecolors=colors.get(layer,'#cccccc'),edgecolors='none',alpha=.65,rasterized=True))
    for r in c.references:
        if r.cell_name.startswith(('sky130','dev_','m_','g_')):continue
        (x0,y0),(x1,y1)=r.bounding_box()
        ax.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,fill=False,edgecolor='#182b45',lw=.85))
        name={'cdacp':'CDAC P','cdacn':'CDAC N','dig':'Control','analog':'Comparator + sampling',
              'drvp':'Reference drivers P','drvn':'Reference drivers N','cdacP':'CDAC P','cdacN':'CDAC N',
              'bankP':'Sampling + drivers P','bankN':'Sampling + drivers N','comp':'Comparator','logic':'Control'}.get(r.name if hasattr(r,'name') else '',r.cell_name)
        # GDS references do not carry the MAG instance name.
        name={'cdac_p':'CDAC P','cdac_n':'CDAC N','analog':'Comparator + sampling','dig':'Control',
              'drv_p':'Drivers P','drv_n':'Drivers N','sar_logic_core':'Control',
              'comparator_core':'Comparator','cdac_core':'CDAC','bank_side':'Sampling + drivers'}.get(r.cell_name,name)
        if r.cell_name=='cdac_core':name+=' P' if (x0+x1)/2<center_x else ' N'
        ax.text((x0+x1)/2,(y0+y1)/2,name,ha='center',va='center',fontsize=8,
                bbox=dict(facecolor='white',alpha=.88,edgecolor='none',pad=1.7))
    (x0,y0),(x1,y1)=c.bounding_box()
    if cell=='sar_adc_macro':
        for x in [49.43,226.57]:
            ax.text(x,176.56,'TOP shunts\n6.221 pF',ha='center',va='center',fontsize=8,
                    bbox=dict(facecolor='white',alpha=.88,edgecolor='none',pad=1.7))
    ax.set_xlim(x0-8,x1+8);ax.set_ylim(y0-8,y1+8);ax.set_aspect('equal')
    ax.set(xlabel='x (µm)',ylabel='y (µm)',title=f'{cell}   {x1-x0:.2f} × {y1-y0:.2f} µm')
    fig.tight_layout();fig.savefig(png);plt.close(fig)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('gds',type=Path);ap.add_argument('cell');ap.add_argument('png',type=Path)
    a=ap.parse_args();render(a.gds,a.cell,a.png)
