import json, sys, os
out = os.environ.get('BANK_OUTDIR','bank')
meta = json.load(open(os.path.join(out,'meta.json')))
L = [".subckt bank_side VIN TRK TRKB VREFP VREFN VDDA VSS " + ' '.join('BOT%d' % k for k in range(11)) + ' ' + ' '.join('LO%d' % k for k in range(11)) + ' ' + ' '.join('HIB%d' % k for k in range(10))]
for (name, kind, Wf, shared, gate, bot) in meta['lvs']:
    model = 'sky130_fd_pr__nfet_01v8' if kind == 'nfet' else 'sky130_fd_pr__pfet_01v8'
    bulk = 'VSS' if kind == 'nfet' else 'VDDA'
    L.append("%s %s %s %s %s %s w=%g l=0.15" % (name, bot, gate, shared, bulk, model, Wf))
L.append(".ends bank_side")
open(os.path.join(out,'bank_side_ref.spice'), 'w').write('\n'.join(L) + '\n')
