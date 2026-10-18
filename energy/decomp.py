"""Split the text-energy gap by token class: name pieces, unknown names spelled out, operators and syntax, numerals.

Pooled over all sampled declarations, bits per token by class for each group. Output: data/out/decomp.json.
"""
import json

import pandas as pd

from analysis_groups import group_of

T = pd.read_pickle('data/text_energy.pkl')
T['group'] = [group_of(c, p) for c, p in zip(T.corpus, T.project)]
dec = []
for g in ['mathlib', 'human-upstream', 'human', 'strongpnt', 'openai', 'openai-ten']:
    d = T[T.group == g]
    n = d.n_tok.sum()
    dec.append(dict(group=g, c_name=d.E_n.sum() / n, c_unk=d.E_unk.sum() / n, c_op=d.E_o.sum() / n,
                    c_num=d.E_k.sum() / n, c_end=d.E_e.sum() / n))
DEC = pd.DataFrame(dec).set_index('group')
DEC.to_json('data/out/decomp.json', orient='index')
gap = DEC.loc['openai'].sum() - DEC.loc['mathlib'].sum()
names = (DEC.loc['openai', ['c_name', 'c_unk']].sum() - DEC.loc['mathlib', ['c_name', 'c_unk']].sum()) / gap
syntax = DEC.loc['openai', 'c_op'] - DEC.loc['mathlib', 'c_op']
print(json.dumps(dict(gap_bits_per_token=gap, share_in_names=names, syntax_bits_per_token=syntax), indent=1))
