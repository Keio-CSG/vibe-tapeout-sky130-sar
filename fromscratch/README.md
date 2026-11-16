# FromScratch

The locked C20G design is published here. **Signoff was not reached.**
The main artifacts are the locked layout and schematic, with their final verification
reports. Later trial designs are excluded.

See [DESIGN.md](DESIGN.md) for the architecture, fixed output decoder and remaining
issues. From the repository root, after setting up the environment:

```sh
make ARM=fromscratch model schematic layout drc lvs pex compare
make ARM=fromscratch MODEL=schematic CORNER=tt fft
make ARM=fromscratch MODEL=pex CORNER=tt smoke
make ARM=fromscratch MODEL=pex CORNER=tt fft
```

`CORNER=ss` and `CORNER=ff` select the other stock model corners. Every output is
written under `fromscratch/runs/`. The layout rebuild retains the frozen top routing
and cached PDK leaf geometry, just as the selected build did; it regenerates the
blocks inside that frame. This is a seeded rebuild, not a fresh routing search.
The original behavioural model is retained; the `model` target disables its noise
and mismatch parameters for an ideal architecture check.

`verify/pex_c.spice` is the small, frozen C-only extraction used by the public FFT
entry point. `make pex` regenerates its electrical network; capacitor ordering and
numbers may change. The historical headline PEX result used full RC, so it is
not an equivalent extraction model. The public tree does not claim to reproduce
that full-RC analysis.
