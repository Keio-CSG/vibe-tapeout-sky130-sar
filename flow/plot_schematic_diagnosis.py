#!/usr/bin/env python3
"""Plot the frozen ngspice-only short-window diagnosis CSV; no simulation needed."""
from pathlib import Path
import csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parents[1]
d=root/'fromscratch/results'
rows=list(csv.DictReader((d/'schematic_tt_diagnosis.csv').open()))
def case(name):
 r=[x for x in rows if x['case']==name]
 return {k:np.array([float(x[k]) for x in r]) for k in r[0] if k!='case'}
s=case('schematic_000');p=case('pex_000');fine=case('step25ps');load=case('output5fF')
fig,ax=plt.subplots(2,2,figsize=(10,6.3),layout='constrained')
colors=['#b33b36','#226b99','#22835b','#9b6aa4']
for v,label,c in [(s,'Schematic, wrong D6=0',colors[0]),(p,'C-only PEX, D6=1',colors[1])]:
 x=v['relative_ns'];ax[0,0].plot(x,v['ob_V']-v['oa_V'],label=label,color=c)
 # Actual gated capture threshold, relative to each trace's evaluation threshold.
 z=v['capture_V'];i=np.where((z[:-1]<.9)&(z[1:]>=.9))[0][0]
 cap=x[i]+(.9-z[i])/(z[i+1]-z[i])*(x[i+1]-x[i])
 ax[0,0].axvline(cap,color=c,linestyle=':',alpha=.8)
 ax[0,1].plot(x,v['residual_mV'],color=c,label=label.split(',')[0])
 ax[1,1].plot(x,v['ia_V'],color=c,label=label.split(',')[0])
ax[0,0].set(title='Sample 0, D6: polarity is wrong before capture',ylabel='Comparator ob − oa (V)',xlim=(-.35,2.9))
ax[0,0].legend(fontsize=8,loc='lower right');ax[0,0].text(.04,.93,'Dotted lines: gated capture',transform=ax[0,0].transAxes,fontsize=8)
ax[0,1].set(title='Positive DAC residual in both cases',ylabel='topp − topn (mV)',xlim=(-.35,2.9),ylim=(0,16))
for v,label,c in [(s,'50 ps baseline',colors[0]),(fine,'25 ps diagnostic',colors[2]),(load,'5 fF diagnostic',colors[3])]:
 x=v['relative_ns'];mask=(x>=-1.2)&(x<=-.1)
 ax[1,0].plot(x[mask],(v['oa_V'][mask]-v['ob_V'][mask])*1e6,'.-',ms=3,lw=.8,label=label,color=c)
ax[1,0].set(title='Reset: oscillation follows integration steps',ylabel='oa − ob (µV)',xlim=(-1.22,-.08));ax[1,0].legend(fontsize=8)
ax[1,1].plot(s['relative_ns'],s['capture_V'],'--',color='#888888',label='Schematic capture')
ax[1,1].plot(s['relative_ns'],s['decision_V'],':',color=colors[0],label='Schematic stored D6')
ax[1,1].set(title='Capture stores the resolved comparator data',ylabel='Data / gated clock (V)',xlim=(-.35,2.9));ax[1,1].legend(fontsize=8,loc='center right')
for a in ax.flat:
 a.grid(alpha=.2);a.set_xlabel('Time from each case’s D6 evaluation edge (ns)')
fig.suptitle('FromScratch schematic TT discrepancy — ngspice diagnostics only',fontsize=12)
fig.savefig(d/'schematic_tt_diagnosis.png',dpi=145,metadata={'Software':'Python plotting'})
