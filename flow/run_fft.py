#!/usr/bin/env python3
"""Generate and run stock-PDK ngspice decks; collect coherent SAR FFT metrics.

Use --prepare and --collect to execute chunk decks on a compute system of choice.
Every chunk contains independent warm-up cycles. Partial runs never claim FFT metrics.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FS = 5.12e6
PERIOD = 1 / FS
NFFT = 256
BIN = 7

def spectrum(codes):
    x = np.asarray(codes, float)
    p = np.abs(np.fft.rfft(x - x.mean())) ** 2
    p[0] = 0
    signal = p[BIN]
    spur = p.copy()
    spur[BIN] = 0
    if signal <= 0 or spur.sum() <= 0:
        return dict(sndr_dB=None, sfdr_dB=None, enob=None)
    sndr = float(10 * np.log10(signal / spur.sum()))
    return dict(sndr_dB=sndr, sfdr_dB=float(10*np.log10(signal / spur.max())),
                enob=(sndr-1.76)/6.02, largest_spur_bin=int(spur.argmax()))

def prepare(a, out):
    arm = ROOT / a.arm
    va = a.arm.endswith('-va')
    net = arm / ('verify/pex_c.spice' if a.model == 'pex' else
                 'schematic/sar_adc_all.spice' if va else 'schematic/sar_adc_m3.spice')
    nt = re.sub(r'\n\+', ' ', net.read_text())
    subs = re.findall(r'^\.subckt\s+(\S+)\s+(.+)$', nt, re.M | re.I)
    top, ports = subs[0] if a.model == 'pex' else next(x for x in subs if x[0] == 'sar_adc')
    pdk = Path(os.environ['PDK_ROOT']) / os.environ.get('PDK', 'sky130A')
    amp, cm = (1.60434, .95) if va else (1.426, .9)
    warm = 3 if va else 1
    chunklen = a.chunk
    plan = dict(arm=a.arm, model=a.model, corner=a.corner, samples=a.samples,
                nfft=NFFT, bin=BIN, fs_Hz=FS, fin_Hz=BIN*FS/NFFT,
                input_diff_peak_V=amp, common_mode_V=cm, warm_cycles=warm,
                window='rectangular', temperature_C=27, tmax_ps=a.tmax_ps,
                solver=a.solver, integration_method=a.method, reltol=a.reltol,
                stimulus_sources='independent voltage sources with 1mOhm series resistance' if va else 'direct independent voltage sources',
                netlist_sha256=hashlib.sha256(net.read_bytes()).hexdigest(), chunks=[])
    pinmap = {p.lower():p.lower() for p in ports.split()}
    pinmap['vss'] = '0'
    for p in ports.split():
        if p.lower().endswith(('/vss', '.vss')):pinmap[p.lower()] = '0'
    probes = [f'v(d{i})' for i in range(11)] + ['v(dv)', 'v(clk)']
    currents = ['i(vdda)', 'i(vddd)', 'i(vrefp)', 'i(vrefn)']
    vectors = probes + currents
    for name in ['result.json','codes.csv']:
        (out/name).unlink(missing_ok=True)
    for start in range(0, a.samples, chunklen):
        count = min(chunklen, a.samples-start)
        d = out / f'c{start:03d}'
        d.mkdir(parents=True, exist_ok=True)
        for name in ['wave.dat','execution.json','ngspice.log']:
            (d/name).unlink(missing_ok=True)
        # Preserve the original arm's starting phase for retained samples.
        phase = 360*BIN*(start if va else start-warm)/NFFT
        clock = (f'pulse(0 1.8 0 100p 100p {PERIOD/2-100e-12:.15g} {PERIOD:.15g})' if va else
                 f'pulse(1.8 0 {PERIOD/2:.15g} 100p 100p {PERIOD/2-100e-12:.15g} {PERIOD:.15g})')
        lines = ['* SAR ADC coherent transient',
                 '* CLK high tracks; falling phase samples; DV marks conversion completion.',
                 f'* {a.arm}, {a.model}, corner {a.corner}; 256-point bin-7 stimulus, 5.12 MS/s.',
                 f'* Differential peak {amp} V; common mode {cm} V; skip {warm} warm cycles.',
                 f'.lib "{pdk}/libs.tech/ngspice/sky130.lib.spice" {a.corner}',
                 f'.include "{pdk}/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice"',
                 f'.include "{net}"', '.temp 27',
                 'Vdda vdda 0 1.8', 'Vddd vddd 0 1.8', 'Vrefp vrefp_e 0 1.8', 'Vrefn vrefn_e 0 0',
                 f'Vinp vinp_s 0 sin({cm} {amp/2} {BIN*FS/NFFT} 0 0 {phase:.15g})',
                 f'Vinn vinn_s 0 sin({cm} {-amp/2} {BIN*FS/NFFT} 0 0 {phase:.15g})',
                 f'Vclk clk 0 {clock}']
        if va:
            lines += ['Rinp vinp_s vinp 1m', 'Rinn vinn_s vinn 1m',
                      'Rrefp vrefp_e vrefp 1m', 'Rrefn vrefn_e vrefn 1m']
        else:
            # Preserve the original ideal independent sources directly at the pins.
            # Redundant unity-gain controlled sources add avoidable MNA constraints.
            lines=[l.replace('Vinp vinp_s ', 'Vinp vinp ').replace('Vinn vinn_s ', 'Vinn vinn ')
                   .replace('Vrefp vrefp_e ', 'Vrefp vrefp ').replace('Vrefn vrefn_e ', 'Vrefn vrefn ')
                   for l in lines]
        lines += ['Xdut ' + ' '.join(pinmap[p.lower()] for p in ports.split())+' '+top,
                  f'.options {a.solver} method={a.method} maxord=2 reltol={a.reltol} abstol=1e-13 vntol=1e-6 gmin=1e-14',
                  '.save '+' '.join(vectors),
                  '.control', 'set wr_singlescale', 'set wr_vecnames', 'set numdgt=15',
                  f'tran 50p {(count+warm)*PERIOD:.15g} 0 {a.tmax_ps}p',
                  'wrdata wave.dat '+' '.join(vectors), 'quit', '.endc', '.end']
        (d/'tb.spice').write_text('\n'.join(lines)+'\n')
        (d/'.spiceinit').write_text('set ngbehavior=hsa\nset skywaterpdk\nset num_threads=1\n')
        plan['chunks'].append(dict(directory=d.name, start=start, count=count))
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    return plan

def run(out, plan):
    for c in plan['chunks']:
        d = out/c['directory']
        started_epoch=time.time()
        start=time.monotonic()
        with (d/'stdout.txt').open('w') as f:
            r=subprocess.run([os.environ.get('NGSPICE','ngspice'),'-b','-o','ngspice.log','tb.spice'],
                             cwd=d,stdout=f,stderr=subprocess.STDOUT)
        wall=time.monotonic()-start
        (d/'execution.json').write_text(json.dumps(dict(wall_s=wall,returncode=r.returncode,
                                                       started_epoch_s=started_epoch,finished_epoch_s=time.time()))+'\n')
        if r.returncode or not (d/'wave.dat').exists():
            raise RuntimeError(f'Failed chunk {d.name}; inspect ngspice.log')
        print(f'{c["directory"]}: {wall:.1f} s', flush=True)

def collect(out):
    p=json.loads((out/'plan.json').read_text())
    va=p['arm'].endswith('-va')
    raw=[]; times=[]; bad=[]; unstable=[]; power=[]; walls=[]; intervals=[]
    for c in p['chunks']:
        d=out/c['directory']
        log=d/'ngspice.log'
        if log.exists() and re.search(r'timestep too small|simulation\(s\) aborted|fatal error',log.read_text(),re.I):
            raise RuntimeError(f'Numerical failure in {d.name}; no spectrum accepted')
        if (d/'execution.json').exists() and json.loads((d/'execution.json').read_text()).get('returncode',0):
            raise RuntimeError(f'Simulator failed in {d.name}')
        w=np.loadtxt(d/'wave.dat',skiprows=1)
        w=w[np.r_[True,np.diff(w[:,0])>0]]
        t=w[:,0]; dv=w[:,12]
        if t[-1] < (p['warm_cycles']+c['count'])*PERIOD*(1-1e-9):
            raise RuntimeError(f'Transient ended early in {d.name}')
        edges=np.where((dv[:-1]<.9)&(dv[1:]>=.9))[0]
        crosses=t[edges]+(.9-dv[edges])/(dv[edges+1]-dv[edges])*(t[edges+1]-t[edges])
        for j in range(p['warm_cycles'], p['warm_cycles']+c['count']):
            ts=(j+1)*PERIOD-(1e-9 if p['model']=='pex' or va else PERIOD-190e-9)
            bits=np.array([np.interp(ts,t,w[:,i+1]) for i in range(11)])
            code=sum(int(v>.9)<<i for i,v in enumerate(bits));raw.append(code)
            tc=crosses[(crosses>(j+.5)*PERIOD)&(crosses<(j+1)*PERIOD)]
            k=c['start']+j-p['warm_cycles']
            if len(tc)!=1 or tc[0]>ts or np.interp(ts,t,dv)<.9:
                bad.append(k)
            else:times.append(float((tc[0]-(j+.5)*PERIOD)*1e9))
            prev=np.array([np.interp(ts-100e-12,t,w[:,i+1])>.9 for i in range(11)])
            after=np.array([np.interp(ts+100e-12,t,w[:,i+1])>.9 for i in range(11)])
            if np.any(prev!=after) or np.any((bits>.36)&(bits<1.44)):unstable.append(k)
        lo=p['warm_cycles']*PERIOD;hi=(p['warm_cycles']+c['count'])*PERIOD
        tt=np.r_[lo,t[(t>lo)&(t<hi)],hi]
        integrate=getattr(np,'trapezoid',np.trapz if hasattr(np,'trapz') else None)
        power.append([-float(integrate(np.interp(tt,t,w[:,14+i]),tt))/(hi-lo)*v*1e6
                      for i,v in enumerate([1.8,1.8,1.8,0])])
        if (d/'execution.json').exists():
            e=json.loads((d/'execution.json').read_text());walls.append(e['wall_s'])
            finish=e.get('finished_epoch_s',(d/'execution.json').stat().st_mtime)
            intervals.append((e.get('started_epoch_s',finish-e['wall_s']),finish))
    powers=np.average(power,axis=0,weights=[x['count'] for x in p['chunks']])
    result=dict(p, completed_conversions=len(raw)-len(bad), invalid_samples=bad,
                unstable_samples=unstable, valid_codes=not bad and not unstable,
                code_min=min(raw),code_max=max(raw),
                power_uW=dict(zip(['vdda','vddd','vrefp','vrefn'],map(float,powers))),
                total_power_uW=float(powers.sum()),
                conversion_ns_mean=float(np.mean(times)) if times else None,
                conversion_ns_max=max(times) if times else None,
                sum_chunk_wall_s=sum(walls),
                wall_s=max(i[1] for i in intervals)-min(i[0] for i in intervals) if intervals else None,
                wall_time_scope='first chunk start to last finish; excludes initial queue wait and deck generation')
    full=len(raw)==NFFT
    result['FFT_valid']=full and result['valid_codes']
    if full:
        result['binary_metrics']=spectrum(raw)
        decoded=np.asarray(raw,float)
        if not va and p['model']=='pex':
            cfg=json.loads((ROOT/p['arm']/'schematic/C20G_RECONSTRUCTION.json').read_text())
            result['decoder_coefficients_sha256']=hashlib.sha256(json.dumps(
                dict(weights=cfg['bit_weights_D0_to_D10'],normalization=cfg['normalization']),
                sort_keys=True).encode()).hexdigest()
            decoded=np.array([1023.5+cfg['normalization']*sum((2*((q>>i)&1)-1)*v for i,v in enumerate(cfg['bit_weights_D0_to_D10'])) for q in raw])
        result['metrics']=spectrum(decoded)
        enob=result['metrics']['enob']
        if enob is None:result['FFT_valid']=False
        if enob is not None:result['fom_fJ']=result['total_power_uW']*1e9/(2**enob*FS)
        if not result['FFT_valid']:result['spectral_status']='INVALID: incomplete or unstable conversions'
    else:result['spectral_status']='smoke only; fewer than 256 samples'
    (out/'codes.csv').write_text('index,raw_code\n'+''.join(f'{i},{q}\n' for i,q in enumerate(raw)))
    result.pop('chunks')
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['completed_conversions','valid_codes','total_power_uW','conversion_ns_max','wall_s','spectral_status'] if k in result}))

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('arm',choices=['fromscratch','fromscratch-va'])
    ap.add_argument('model',choices=['schematic','pex'])
    ap.add_argument('corner',choices=['tt','ss','ff'])
    ap.add_argument('--samples',type=int,default=256)
    ap.add_argument('--chunk',type=int,default=32)
    ap.add_argument('--tmax-ps',type=float,default=None,
                    help='Maximum integration step in ps (schematic: 25, PEX: 50); output request stays 50 ps')
    ap.add_argument('--solver',choices=['klu','sparse'],default='klu')
    ap.add_argument('--method',choices=['trap','gear'],default='trap')
    ap.add_argument('--reltol',type=float,default=1e-3)
    ap.add_argument('--output',type=Path)
    ap.add_argument('--prepare',action='store_true')
    ap.add_argument('--collect',action='store_true')
    a=ap.parse_args()
    if a.tmax_ps is None:a.tmax_ps=25 if a.model=='schematic' else 50
    if a.tmax_ps<=0:ap.error('Maximum integration step must be positive')
    if not 1<=a.samples<=256 or a.chunk<1:ap.error('Require 1..256 samples and positive chunk length')
    out=(a.output or ROOT/a.arm/'runs'/f'{a.model}_{a.corner}').resolve()
    out.mkdir(parents=True,exist_ok=True)
    if a.collect:collect(out);return
    plan=prepare(a,out)
    if a.prepare:return
    run(out,plan);collect(out)

if __name__=='__main__':main()
