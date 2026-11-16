# Functional model → block tests → integration

This instruction applied only to FromScratch-VA.

1. Before transistor design, write Verilog-A models of sampling switches (on resistance,
   injection and aperture), CDAC (including top-plate parasitics), comparator (offset,
   noise, delay and kickback), SAR timing and references. Assemble a complete ADC and
   demonstrate the 256-point typical-corner FFT target. Sweep each nonideality until
   the ADC reaches its limit, then allocate a tighter numerical budget to each block.
2. Design and test one transistor block at a time with realistic loads and otherwise
   ideal or behavioural surroundings. Measure the block's allocated quantities directly:
   track/hold spectrum, resistance and injection versus input; comparator offset, noise,
   delay and kickback; DAC/reference settling; and logic timing.
3. Replace behavioural blocks one at a time. After each replacement run a few static
   points, a slow ramp and the coherent FFT. Localize any regression to the block most
   recently replaced and return to its block test.

The retained Verilog-A source documents the original functional abstractions.
The portable reproduction targets use ngspice transistor netlists and a separate Python
ideal architecture check; they do not require a Verilog-A compiler.
