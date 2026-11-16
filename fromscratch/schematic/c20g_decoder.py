"""Reconstruct C20G's eleven raw decisions using its frozen physical DAC weights.

D10 is the first/sign decision, D0 is the final decision. This is a fixed
coefficient decoder, with no input phase, corner, tone or waveform dependence.
The native macro exposes raw decisions; the shared SAR specification permits
raw decisions with documented reconstruction. Return a fractional estimate
from the 2048 raw states; rounding to an integer is an optional extra step.
"""
from pathlib import Path
import json
_CONFIG=json.loads(Path(__file__).with_name('C20G_RECONSTRUCTION.json').read_text())
_WEIGHTS=tuple(_CONFIG['bit_weights_D0_to_D10'])
_GAIN=_CONFIG['normalization']
def decode(raw):
    raw=int(raw)
    if not 0<=raw<2048:
        raise ValueError('Expected eleven raw decision bits, 0…2047')
    return 1023.5+_GAIN*sum((2*((raw>>i)&1)-1)*w for i,w in enumerate(_WEIGHTS))
def decode_integer(raw):
    return min(2047,max(0,round(decode(raw))))
if __name__=='__main__':
    import sys
    for value in sys.argv[1:]:
        raw=int(value,0)
        print(raw,format(decode(raw),'.12g'),decode_integer(raw))
