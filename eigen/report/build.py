"""Assemble eigenproofs.html from the analysis outputs. Prose lives in prose.py (written after the results)."""
import json
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, '/Users/safsom/Projects/math-ai-projects/energy')
from gloss import describe  # noqa: E402
from lexer import declarations, strip_comments  # noqa: E402

RES = os.path.join(ROOT, os.environ.get('GOUT', 'out'), os.environ.get('RESNAME', 'analysis_merged'))
R = json.load(open(os.path.join(RES, 'results.json')))
P = pd.read_csv(os.path.join(RES, 'projects.csv'))

OLD = [('concepts_per_100_thm', 'Concepts per 100 theorems'), ('single_use_lemma_share', 'Single-use lemmas'),
       ('auto_per_1k', 'Automation tactics per 1k tokens'), ('struct_per_1k', 'Structural tactics per 1k tokens'),
       ('casebash_token_share', 'Case bashing'), ('cert_token_share', 'Certificate mass'),
       ('numbered_share', 'Numbered names'), ('skel_dup_share', 'Template proofs'),
       ('library_ref_share', 'Library references'), ('proof_to_statement', 'Proof / statement length'),
       ('e_tok', 'Text energy'), ('e_ir', 'Compiled energy')]


def bh(ps):
    ps = np.asarray(ps, float)
    o = np.argsort(ps)
    q = ps[o] * len(ps) / (np.arange(len(ps)) + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty_like(q)
    out[o] = np.minimum(q, 1)
    return out


cells = [(k, a) for k, row in R['old_corr'].items() for a in row]
qs = bh([R['old_corr'][k][a]['p'] for k, a in cells]) if cells else []
for (k, a), q in zip(cells, qs):
    R['old_corr'][k][a]['q'] = float(q)


def source(corpus, module, name):
    roots = {'mathlib': '/Users/safsom/Projects/math-ai-projects/mathlib4',
             'openai': '/Users/safsom/Projects/math-ai-projects/corpora/openai_math/lean'}
    path = os.path.join(roots[corpus], *module.split('.')) + '.lean'
    for d in declarations(strip_comments(open(path, encoding='utf-8').read())):
        full = '.'.join(d['namespace'] + [d['name']]) if d['name'] else ''
        if full == name or name.endswith('.' + full) or full.endswith('.' + name):
            return d['text']
    return ''


def load_trace(path, name):
    for line in open(path):
        r = json.loads(line)
        if r['n'] == name:
            return r['tree']
    return None


def example(label, corpus, module, name, trace_path):
    tree = load_trace(trace_path, name) or []
    tree = [[d, re.sub(r'P:[A-Za-z]+', 'P', g)] for d, g in tree]
    return dict(label=label, name=name, src=source(corpus, module, name),
                tree=[[d, g, describe(g)] for d, g in tree])


def build(text, figs, examples, titles):
    modes = R['modes']
    for m in modes:
        t = titles.get(m['rank'], {})
        m['title'] = t.get('title', f"Eigenproof {m['rank']}")
        m['blurb'] = t.get('blurb', '')
    proj = P[['group', 'project', 'e_ir', 'e_tok', 'n']].copy()
    proj = proj.replace({np.nan: None})
    extra = {}
    cp = os.environ.get('CUTS_JSON', os.path.join(ROOT, 'out_cut', 'report_cuts.json'))
    if os.path.exists(cp):
        extra['cuts'] = json.load(open(cp))
    ap = os.environ.get('AI_JSON', os.path.join(ROOT, 'out_ai', 'report_ai.json'))
    if os.path.exists(ap):
        extra['ai'] = json.load(open(ap))
    data = dict(**extra, text=text, figs=figs, example=examples, projects=proj.to_dict('records'), groups=R['groups'],
                tests=R['tests'], spectrum=R['spectrum'], null=R['null'], modes=modes, stability=R['stability'],
                normal=R['normal_modes'], over=R['over'], under=R['under'], old_corr=R['old_corr'],
                old_cols=[c for c in OLD if any(c[0] in row for row in R['old_corr'].values())])
    html = open(os.path.join(HERE, 'template.html')).read()
    html = html.replace('/*BASESTYLE*/', open(os.path.join(HERE, 'base_style.css.html')).read())
    html = html.replace('/*DATA*/null', json.dumps(data, ensure_ascii=False, allow_nan=False, default=float).replace('</', '<\\/'))
    html = html.replace('/*SCRIPT*/', open(os.path.join(HERE, 'eigen.js')).read())
    out = os.path.join(HERE, 'eigenproofs.html')
    open(out, 'w').write(html)
    print('wrote', out, len(html))


if __name__ == '__main__':
    from prose import EXAMPLES, FIGS, TEXT, TITLES  # noqa: E402
    build(TEXT, FIGS, [example(*e) for e in EXAMPLES], TITLES)
