"""Floorplan constants shared by the block generators and gen_top (macro coordinates, um)."""
CDAC_OX, CDAC_OY = 6.0, 4.36          # cdac_core block origin offset -> bbox lower-left at (0,0)
BANK_OX = 14.25                       # bank x offset (bank 79.5 wide centred over the 108 wide array)
import os
XC = float(os.environ.get('FP_XC', '128'))  # macro vertical symmetry axis
