# FromScratch-VA

The locked reset-buffer and top-shunt design is published here. Its original
signoff was **C-only PEX**, with passing TT/SS/FF results. Full-RC FFT and voltage
reliability qualification were not completed.

See [DESIGN.md](DESIGN.md). From the repository root:

```sh
make ARM=fromscratch-va model schematic layout drc lvs pex compare
make ARM=fromscratch-va MODEL=schematic CORNER=tt fft
make ARM=fromscratch-va MODEL=pex CORNER=tt smoke
make ARM=fromscratch-va MODEL=pex CORNER=tt fft
```

Use `CORNER=ss` or `ff` for the other stock model corners. Outputs go under
`fromscratch-va/runs/`. The layout generator rebuilds the capacitor array, sampling
and reference banks, comparator and top assembly. The selected routed logic MAG is
a frozen seed; the original routing-search cache is unnecessary and excluded.
Cached PDK device MAG files preserve the selected geometry.

The original `model/fm_blocks.va` documents the behavioural block abstractions.
It is not directly executable by this ngspice workflow. `make model` runs a portable
Python ideal architecture check; transistor schematic and PEX runs use ngspice only.

`verify/pex_c.spice` is the frozen flattened C-only extraction after exact parallel
MIM and coupling-capacitor compaction. The `pex` target repeats flattening, extraction
and the original compaction algorithm. The `compare` target ignores capacitor
numbering and checks devices and the capacitance network.
