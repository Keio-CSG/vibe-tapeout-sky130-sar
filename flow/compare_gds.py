#!/usr/bin/env python3
"""Compare flattened geometry by layer; GDS timestamps are ignored."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import klayout.db as db

def without_timestamps(data):
    records=[];offset=0
    while offset<len(data):
        length,kind=struct.unpack('>HH',data[offset:offset+4])
        record=data[offset:offset+length]
        if kind in (0x0102,0x0502):record=record[:4]+bytes(length-4)
        records.append(record);offset+=length
    return b''.join(records)

def compare(reference,generated,cell):
    a,b=db.Layout(),db.Layout();a.read(reference);b.read(generated)
    if a.dbu!=b.dbu:raise ValueError('GDS database units differ')
    ca,cb=a.cell(cell),b.cell(cell)
    layers=set((i.layer,i.datatype) for i in a.layer_infos())|set((i.layer,i.datatype) for i in b.layer_infos())
    differences=[]
    for layer,dt in sorted(layers):
        ra=db.Region(ca.begin_shapes_rec(a.layer(layer,dt)))
        rb=db.Region(cb.begin_shapes_rec(b.layer(layer,dt)))
        xor=ra^rb
        if not xor.is_empty():differences.append(dict(layer=layer,datatype=dt,xor_area_um2=xor.area()*a.dbu*a.dbu))
    raw_a,raw_b=Path(reference).read_bytes(),Path(generated).read_bytes()
    return dict(cell=cell,geometry_equal=not differences,xor_by_layer=differences,
                byte_equal=raw_a==raw_b,
                equal_except_timestamps=without_timestamps(raw_a)==without_timestamps(raw_b),
                reference_sha256=hashlib.sha256(raw_a).hexdigest(),
                generated_sha256=hashlib.sha256(raw_b).hexdigest(),
                reference_cells=a.cells(),generated_cells=b.cells(),
                reference_bbox_um=[v*a.dbu for v in [ca.bbox().left,ca.bbox().bottom,ca.bbox().right,ca.bbox().top]],
                generated_bbox_um=[v*b.dbu for v in [cb.bbox().left,cb.bbox().bottom,cb.bbox().right,cb.bbox().top]])

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('reference');ap.add_argument('generated');ap.add_argument('cell');ap.add_argument('--output')
    a=ap.parse_args();result=compare(a.reference,a.generated,a.cell);t=json.dumps(result,indent=2)+'\n'
    if a.output:open(a.output,'w').write(t)
    else:print(t)
    if not result['geometry_equal']:raise SystemExit(1)
