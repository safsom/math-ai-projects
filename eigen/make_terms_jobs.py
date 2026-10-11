"""Jobs for the proof-term pass (GESTURE_CUTS=1 GESTURE_TERMS=1), all writing to out_terms/."""
import json, os
from lean3job import fill
HERE = os.path.dirname(os.path.abspath(__file__))
OT = os.path.join(HERE, 'out_terms')
os.makedirs(OT, exist_ok=True)


def save(name, j):
    json.dump(fill(j), open(os.path.join(HERE, f'job_terms_{name}.json'), 'w'))


j = json.load(open('job_cut_mathlib.json')); j['out'] = OT; save('mathlib', j)
for n in ('SphereEversion', 'oai_olean'):
    j = json.load(open(f'job_cut_{n}.json')); j['out'] = OT; save(n, j)
# Carleson from the oleans its isolated cut run wrote against this mathlib
j = json.load(open('job_cut_Carleson.json')); j['out'] = OT; j['oleanDir'] = os.path.join(HERE, 'out_cut', 'olean'); save('Carleson', j)
j = json.load(open('job_cut_CarlesonIso.json')); j['out'] = OT; j['oleanDir'] = os.path.join(OT, 'olean'); save('CarlesonIso', j)
# the 9 OpenAI projects compiled module by module (isolation check): read from their oleans, for invariance
I = json.load(open('job_I.json'))
mods = [m['mod'] for p in I['projects'] for m in p['modules']]
save('iso', dict(out=os.path.join(HERE, 'out_terms_iso'), imports=['Lean.Elab.Tactic.Omega', 'Mathlib'] + mods,
                 oleanDir=I['oleanDir'], oleanProjects=I['projects']))
os.makedirs(os.path.join(HERE, 'out_terms_iso'), exist_ok=True)
j = json.load(open('job_cut_oai.json')); j['out'] = OT; save('oai', j)
for c in ('putnam2025', 'imo2025', 'spherepacking'):
    j = json.load(open(f'job_ai_{c}.json')); j['out'] = os.path.join(HERE, 'out_terms_ai', c); save(c, j)
print('ok')
