"""Regression test for the proof-term pass on hand-checkable theorems.

python3 tests/terms_toy/check.py   (from eigen/; writes a scratch job next to this file)
Expected values are worked out by hand: see the comments.
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EIGEN = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, EIGEN)
import lean3job  # noqa: E402

# name: (S cut-free size, D distinct nodes, G explicit layout, tResid, tResidP, rk cells, rku cells)
# rk cell = 3 * rank + use class (0 dead, 1 linear, 2 shared)
EXPECT = {
    't_share': (11, 8, 11, 0, 0, [2], [2]),    # same cut-free proof as t_cse; naming a 3-node pair used twice does not pay
    't_cse': (11, 8, 11, 0, 0, [], []),        # no cuts written; the DAG still shares the pair
    't_cse3': (15, 9, 13, 0, 0, [], []),       # used three times, naming pays
    't_res': (15, 8, 14, 1, 1, [5], [5]),      # f : p → p ∧ p shared, applied to a proof: one created proof redex (identical uses merge)
    't_inst': (9, 7, 9, 2, 0, [2], [2]),       # g : ∀ n, p applied to data only: redexes, none applied to a proof
    't_unf': (6, 6, 6, 1, 1, [1], [4]),        # Imp p p is rank 0 as written, rank 1 unfolded
    't_prefix': (6, 6, 6, 1, 1, [4], [4]),     # the cut behind a data β-prefix is seen, rank 1
    't_nest': (17, 6, 13, 0, 0, [2], [2]),     # the author's layout is optimal: G = N4 = 13; S/D = 17/6 <= occMax 8
}

out = os.path.join(HERE, 'out')
os.makedirs(out, exist_ok=True)
job = lean3job.fill({'out': out, 'imports': ['Init'], 'mathlibNames': '', 'trace': [], 'isolated': False, 'oleanDir': '',
                     'maxModules': 1000000, 'oleanProjects': [],
                     'projects': [{'name': 'OAI.Toy.T', 'modules': [{'mod': 'OAI.Toy.T', 'path': os.path.join(HERE, 'Toy.lean')}]}]})
json.dump(job, open(os.path.join(out, 'job.json'), 'w'))
env = dict(os.environ, GESTURE_CUTS='1', GESTURE_TERMS='1')
subprocess.run([os.path.join(EIGEN, 'run_driver3.sh'), os.path.join(out, 'job.json'), os.path.join(out, 'run.log')], env=env, check=True)
got = {}
for line in open(os.path.join(out, 'OAI.Toy.T.jsonl')):
    r = json.loads(line)
    if r['n'] in EXPECT:
        got[r['n']] = (r['tS'], r['tD'], r['tG'], r['tResid'], r['tResidP'],
                       [i for i, v in enumerate(r['rk']) if v], [i for i, v in enumerate(r['rku']) if v])
bad = {n: (e, got.get(n)) for n, e in EXPECT.items() if got.get(n) != e}
print('ok' if not bad else bad)
sys.exit(1 if bad else 0)
