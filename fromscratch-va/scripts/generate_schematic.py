#!/usr/bin/env python3
"""Regenerate the locked reset-buffer schematic and matched top-plate MIM loads."""
from pathlib import Path
import subprocess
import sys
import argparse

HERE=Path(__file__).resolve().parent
ARM=HERE.parent
ap=argparse.ArgumentParser()
ap.add_argument('--output',type=Path,default=ARM/'runs/schematic')
a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
subprocess.run([sys.executable,str(HERE/'gen_adc.py'),'w_top=127.92','reset_buffer=1',
                'antenna_gate=1','layout_fingers=1','outdir='+str(out)],check=True)
for name in ['sar_adc.spice']:
    t=(out/name).read_text()
    devices='\n'.join(f'xtopshunt_{s}{i} top_{s} vss sky130_fd_pr__cap_mim_m3_1 w=27 l=18.92'
                      for s in ['p','n'] for i in range(6))
    (out/name).write_text(t.replace('.ends sar_adc\n',devices+'\n.ends sar_adc\n'))
(out/'sar_adc_all.spice').write_text('\n'.join((out/(n+'.spice')).read_text() for n in
                                             ['cdac','comparator','sar_logic','sar_adc']))
