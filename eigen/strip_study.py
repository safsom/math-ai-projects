"""The gesture analysis with automation, and then also rewriting, collapsed to one step per call.

A tactic such as ring or omega leaves a certificate in the proof term: many `tac:*` gestures that the author never
wrote. The rewriting glue (Eq.mpr, congrArg, Eq.trans, ... from rw and simp) is the same kind of artifact. Each
variant replaces a block of such gestures by a single token for the call, and keeps everything else, including the
facts the author passes to the tactic.

Gestures are nodes of a DAG and bigrams are its edges, so the number of calls is estimated per gesture as its node
count times the share of its incoming edges that come from outside the block (a root of the proof counts as a call).

A third variant drops the calls as well (analysis_author: only what the author wrote outside automation and rewriting).

Writes out_final/analysis_noauto, analysis_noauto_norw and analysis_author (decls.pkl, unigrams.pkl) for stats_eigen.py:
    GOUT=out_final RESNAME=analysis_noauto python3 stats_eigen.py
The proofs are those of analysis_merged (in analysis_author, less those with nothing left).
"""
import collections, os, pickle, sys
os.environ.update(GOUT='out_final', RESNAME='analysis_merged', MERGE_ARITH='1', WITH_AI='0')
import pandas as pd
import analyze

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, 'out_final', 'analysis_merged')


def cls_auto(g):
    return 'auto' if g.startswith('tac:') else None


def cls_norw(g):
    if g.startswith('tac:'):
        return 'auto'
    return 'rewrite' if analyze.family(g) == 'rewrite along an equation' else None


def inside(cp, cg):
    """Whether an edge from a parent of class cp to a child of class cg stays inside one call."""
    return cp == 'auto' or (cp is not None and cp == cg)


def strip(u, b, cls, drop=False):
    e_in, e_out = collections.Counter(), collections.Counter()
    for (p, g), v in b.items():
        cg = cls(g)
        if cg:
            (e_in if p != 'ROOT' and inside(cls(p), cg) else e_out)[g] += v
    out = collections.Counter()
    for g, n in u.items():
        cg = cls(g)
        if not cg:
            out[g] += n
        else:
            tot = e_in[g] + e_out[g]
            calls = n * e_out[g] / tot if tot else n
            if calls and not drop:
                out['(' + cg + ' call)'] += calls
    return out


def main():
    recs = [r for r in analyze.load() if not r['sorry']]
    D = pd.read_pickle(os.path.join(BASE, 'decls.pkl'))
    blob = pickle.load(open(os.path.join(BASE, 'unigrams.pkl'), 'rb'))
    assert len(recs) == len(D) and all(r['n'] == n and r['group'] == g for r, n, g in zip(recs, D.name, D.group))
    for name, cls, drop in (('analysis_noauto', cls_auto, False), ('analysis_noauto_norw', cls_norw, False),
                            ('analysis_author', cls_norw, True)):
        U = [strip(u, r['b'], cls, drop) for u, r in zip(blob['U'], recs)]
        mass = pd.DataFrame({'g': D.group.values, 'new': [sum(x.values()) for x in U], 'old': [sum(u.values()) for u in blob['U']]})
        mass = mass.groupby('g').sum()
        print(name, 'gesture mass kept by group:', (mass.new / mass.old).round(3).to_dict())
        out = os.path.join(HERE, 'out_final', name)
        os.makedirs(out, exist_ok=True)
        keep = pd.Series([sum(x.values()) > 0 for x in U])
        pos = keep[keep].index.to_numpy()
        D.iloc[pos].reset_index(drop=True).to_pickle(os.path.join(out, 'decls.pkl'))
        pickle.dump(dict(U=[U[i] for i in pos], A=[blob['A'][i] for i in pos]), open(os.path.join(out, 'unigrams.pkl'), 'wb'))
        print(name, 'proofs', len(pos), 'of', len(D))


if __name__ == '__main__':
    main()
