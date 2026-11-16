#!/usr/bin/env python3
"""Plot a completed code record; refuse invalid or partial spectra."""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('result',type=Path);ap.add_argument('codes',type=Path);ap.add_argument('output',type=Path)
a=ap.parse_args();r=json.loads(a.result.read_text())
if not r.get('FFT_valid'):raise SystemExit('A valid, complete 256-point FFT is required')
code=np.loadtxt(a.codes,delimiter=',',skiprows=1)[:,1]
if r['arm']=='fromscratch' and r['model']=='pex':
    cfg=json.loads((ROOT/r['arm']/'schematic/C20G_RECONSTRUCTION.json').read_text())
    code=np.array([1023.5+cfg['normalization']*sum((2*((int(q)>>i)&1)-1)*w for i,w in enumerate(cfg['bit_weights_D0_to_D10'])) for q in code])
x=code-code.mean();mag=np.abs(np.fft.rfft(x));mag/=mag[7]
fig,(ax,ab)=plt.subplots(1,2,figsize=(10,3.4),dpi=160)
ax.plot(np.arange(len(code)),code,lw=1)
ax.set(xlabel='Sample',ylabel='Reconstructed code' if r['model']=='pex' and r['arm']=='fromscratch' else 'Binary code')
ab.plot(np.fft.rfftfreq(len(code),1/r['fs_Hz'])/1e3,20*np.log10(np.maximum(mag,1e-8)),lw=1)
ab.set(xlabel='Frequency (kHz)',ylabel='dBc',ylim=(-120,3),xlim=(0,r['fs_Hz']/2e3))
m=r['metrics'];fig.suptitle(f'{r["arm"]} {r["model"]} {r["corner"]}: SNDR {m["sndr_dB"]:.2f} / SFDR {m["sfdr_dB"]:.2f} dB')
fig.tight_layout();fig.savefig(a.output);plt.close(fig)
