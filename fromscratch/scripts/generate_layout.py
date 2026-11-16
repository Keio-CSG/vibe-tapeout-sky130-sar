#!/usr/bin/env python3
"""Rebuild C20G blocks within the frozen top routing and placement frame.

The top route is a frozen artifact, as in the original locked build. Reference
leaf MAG files cache the exact PDK device geometry. This is a seeded rebuild.
"""
from pathlib import Path
import argparse
import shutil
import sys

HERE=Path(__file__).resolve().parent
ARM=HERE.parent
ap=argparse.ArgumentParser()
ap.add_argument('--output',type=Path,default=ARM/'runs/layout')
a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
gen=out/'generator';shutil.copytree(HERE/'layout',gen,dirs_exist_ok=True)
shutil.copy(HERE/'p_M3.json',out/'p_M3.json')
cells=gen/'cells';cells.mkdir(exist_ok=True)
for p in (ARM/'layout').glob('*.mag'):shutil.copy(p,cells/p.name)
sys.path.insert(0,str(gen));sys.path.insert(0,str(gen/'lib'))
import top
top.NETL=str(ARM/'schematic/sar_adc_m3.spice')
top.digital.NETL=top.NETL
top.build()
for p in cells.glob('*.mag'):shutil.copy(p,out/p.name)
sys.path.insert(0,str(ARM.parent/'flow'))
from export_gds import export
export(out,'sar_adc_top')
