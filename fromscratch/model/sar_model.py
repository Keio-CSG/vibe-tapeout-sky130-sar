#!/usr/bin/env python3
"""M1 behavioural model: 11-bit differential monotonic-switching SAR, top-plate sampling, MIM unit caps.
Non-idealities: unit-cap mismatch, top-plate parasitic Cp (gain), parasitic nonlinearity (quadratic Cp(V)),
kT/C, comparator offset+noise, incomplete DAC settling. 512-pt coherent FFT, rectangular window."""
import numpy as np, sys, json
def fft_metrics(code, nbin, N=512):
    x = code - code.mean()
    X = np.abs(np.fft.rfft(x))**2
    X[0] = 0
    sig = X[nbin]
    noise = X[1:].sum() - sig
    sndr = 10*np.log10(sig/noise)
    sp = X.copy(); sp[nbin] = 0
    sfdr = 10*np.log10(sig/sp.max())
    return sndr, sfdr
def run(nbin=7, N=512, FS=1.6, amp_dbfs=-1.0, Cu=8e-15, sig_u=0.003, Cp=100e-15, cubic=0.0,
        vos=5e-3, vn=0.3e-3, ktc=True, settle_err=0.0, vref=1.8, vcm=0.9, seed=0):
    rng = np.random.default_rng(seed)
    nunit = [512,256,128,64,32,16,8,4,2,1]
    mk = lambda: np.array([(Cu*(1+sig_u*rng.standard_normal(n))).sum() for n in nunit])
    wP, wN = mk(), mk()
    wd = Cu*(1+sig_u*rng.standard_normal())
    CtP, CtN = wP.sum()+wd+Cp, wN.sum()+wd+Cp
    A = FS*10**(amp_dbfs/20)
    t = np.arange(N); vd = A*np.sin(2*np.pi*nbin*t/N + 0.3)
    vip = vcm + vd/2; vin = vcm - vd/2
    codes = np.zeros(N, int)
    kt = np.sqrt(1.380649e-23*300/CtP) if ktc else 0.0
    for k in range(N):
        vp = vip[k] + kt*rng.standard_normal()
        vn_ = vin[k] + kt*rng.standard_normal()
        c = 0
        for i in range(10):
            d = (vp - vn_) - vos + vn*rng.standard_normal() > 0
            c = (c<<1) | int(d)
            fp = 1+cubic*(vp-vcm)**2; fn = 1+cubic*(vn_-vcm)**2
            if d: vn_ += vref*wN[i]/(CtN*fn)*(1-settle_err)
            else: vp  += vref*wP[i]/(CtP*fp)*(1-settle_err)
        d = (vp - vn_) - vos + vn*rng.standard_normal() > 0
        codes[k] = (c<<1) | int(d)
    return fft_metrics(codes.astype(float), nbin, N), codes
if __name__ == "__main__":
    res = {}
    cases = {
      "ideal": dict(sig_u=0, Cp=0, vos=0, vn=0, ktc=False),
      "nominal(sig_u=0.3%,Cp=100fF,vos=5mV,vn=0.3mV)": dict(),
      "pessimistic(sig_u=0.6%,Cp=300fF,cubic=0.05,vn=0.5mV)": dict(sig_u=0.006, Cp=300e-15, cubic=0.05, vn=0.5e-3),
      "near-Nyquist bin 255 nominal": dict(nbin=255),
      "settling error 0.05% of step": dict(settle_err=5e-4),
    }
    for name, kw in cases.items():
        sn = np.array([run(seed=s, **kw)[0] for s in range(20)])
        res[name] = dict(SNDR_mean=float(sn[:,0].mean()), SNDR_min=float(sn[:,0].min()), SFDR_mean=float(sn[:,1].mean()), SFDR_min=float(sn[:,1].min()))
        print(f"{name:58s} SNDR {sn[:,0].mean():.2f} (min {sn[:,0].min():.2f}) dB  SFDR {sn[:,1].mean():.1f} (min {sn[:,1].min():.1f}) dB  ENOB {(sn[:,0].mean()-1.76)/6.02:.2f}")
    for FS in (1.4,1.5,1.6,1.7):
        s = np.mean([run(seed=q, FS=FS)[0][0] for q in range(10)])
        print(f"FS={FS} V peak diff: SNDR {s:.2f} dB at -1 dBFS (nominal)")
        res[f"FS{FS}"] = float(s)
    json.dump(res, open("model/m1_results.json","w"), indent=1)
