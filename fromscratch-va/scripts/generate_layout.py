#!/usr/bin/env python3
"""Rebuild the selected physical design from the original generators.

The routed logic MAG is a frozen seed. Other blocks and top assembly regenerate.
Cached PDK leaves are copied from the reference hierarchy.
"""
from pathlib import Path
import argparse
import os
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ARM=HERE.parent
ap=argparse.ArgumentParser()
ap.add_argument('--output',type=Path,default=ARM/'runs/layout')
a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
gen=out/'generator';shutil.copytree(HERE/'layout',gen,dirs_exist_ok=True)
(gen/'devs').mkdir(exist_ok=True)
for p in (ARM/'layout').glob('dev_*.mag'):shutil.copy(p,gen/'devs'/p.name)
for d in ['cdac','logic','bank','bank_antenna','comp_reset_center']:(gen/d).mkdir(exist_ok=True)
shutil.copy(ARM/'layout/sar_logic_core.mag',gen/'logic/sar_logic_core.mag')
# The CDAC generator reads the reference bank pin coordinates.
shutil.copy(gen/'bank_antenna/meta.json',gen/'bank/meta.json')
for p in (ARM/'layout').glob('sky130_fd_sc_hd__*.mag'):shutil.copy(p,gen/'logic'/p.name)
env=dict(os.environ,FP_XC='138',BANK_DIR='bank_antenna',COMP_DIR='comp_reset_center',BANK_GAP='4',
         CPB_SHIELD='1',CPB_POWER='1',CPB_TOPSHUNT='1',CPB_INPUT_FILTER='0',
         CPB_LOGIC_MESH='0',CPB_CLOCK_WINDOW='0',RMAXIT='300000',COMP_BRIDGE='1',
         COMP_RESET_WIDTH='127.92',COMP_RESET_BUFFER='1',COMP_CENTER_N='1',
         BANK_ANTENNA='1',MINW='5.5',BANK_TRIES='4',
         COMP_OUTDIR=str(gen/'comp_reset_center'),BANK_OUTDIR=str(gen/'bank_antenna'),TOP_OUTDIR=str(out))
sys.path.insert(0,str(ARM.parent/'flow'))
from export_gds import export
with (out/'generation.log').open('w') as log:
    for name in ['gen_comp_layout.py','gen_bank.py','bank_lvs_ref.py','gen_cdac.py']:
        subprocess.run([sys.executable,str(gen/name)],env=env,cwd=gen,stdout=log,stderr=subprocess.STDOUT,check=True)
    for d,c in [('cdac','cdac_core'),('bank_antenna','bank_side'),('comp_reset_center','comparator_core'),('logic','sar_logic_core')]:
        export(gen/d,c)
    subprocess.run([sys.executable,str(gen/'gen_top.py')],env=env,cwd=gen,stdout=log,stderr=subprocess.STDOUT,check=True)
export(out,'sar_adc_macro')
