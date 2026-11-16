# Floorplan → block layout and extraction → integration

This instruction applied only to FromScratch-VA.

1. Estimate device, MIM and standard-cell area before block layout. Draw outlines, pins,
   sensitive routes and the differential symmetry axis. Compare two or three floorplans
   at the same physical scale and record the choice.
2. Reduce empty area and sensitive-wire length while keeping a practical aspect ratio.
   Fix each block's outline, pin layer, position and pitch before drawing its internals.
3. Require each block to pass DRC and LVS. Extract capacitance and, where relevant,
   resistance. Repeat its block tests with the extracted model: comparator behaviour,
   track/hold spectrum, DAC weights, reference settling and logic timing. Iterate at
   block level until the post-layout budgets hold.
4. Integrate per the floorplan, routing sensitive nets first. Repeat full-macro DRC, LVS,
   extraction and ADC simulation. Diagnose regressions with the block extraction tests.
