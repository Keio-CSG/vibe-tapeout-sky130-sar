"""Small designs to emit sky130 ngspice device lines with junction geometry in um/um^2, scaled by the SKY130 PDK."""
def _par(w, nf=1):
    w = float(w)
    ad = int((nf+1)/2)*w/nf*0.29; as_ = int((nf+2)/2)*w/nf*0.29
    pd = 2*int((nf+1)/2)*(w/nf+0.29); ps = 2*int((nf+2)/2)*(w/nf+0.29)
    return f"ad={ad:.4g} as={as_:.4g} pd={pd:.4g} ps={ps:.4g}"
def fet(name, kind, d, g, s, b, w, l=0.15, nf=1, mult=1):
    """kind 'n' or 'p' (core 1.8 V devices); w in um (total per finger*nf handled by nf)"""
    model = {"n":"sky130_fd_pr__nfet_01v8","p":"sky130_fd_pr__pfet_01v8","nl":"sky130_fd_pr__nfet_01v8_lvt","pl":"sky130_fd_pr__pfet_01v8_lvt"}[kind]
    wf = w/nf
    return (f"X{name} {d} {g} {s} {b} {model} W={wf:g} L={l:g} nf={nf} mult={mult} "
            f"ad={int((nf+1)/2)*wf*0.29:.5g} as={int((nf+2)/2)*wf*0.29:.5g} "
            f"pd={2*int((nf+1)/2)*(wf+0.29):.5g} ps={2*int((nf+2)/2)*(wf+0.29):.5g}")
