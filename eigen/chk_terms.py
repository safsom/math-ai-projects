"""Consistency checks of the proof-term pass on a gestures output file."""
import json, math, statistics as st, sys
lg = math.log2
R = [json.loads(l) for l in open(sys.argv[1])]
ok = [r for r in R if not r.get('tt') and not r.get('ctr') and 'tS' in r]
print('n', len(R), 'ok', len(ok), 'tS==N3', sum(r['tS'] == r['cN'][3] for r in ok),
      'within 1%', sum(abs(r['tS'] - r['cN'][3]) <= 0.01 * r['cN'][3] + 1 for r in ok))
X = [(lg(r['tS'] / r['tG']), lg(r['tS'] / r['tD']), lg(r['cN'][3] / r['cN'][4]), r['tResid'], lg(r['tOccMax']))
     for r in ok if r['nodes'] >= 10]
for i, nm in enumerate(['chi*_lb', 'chi*_dag', 'chi_author', 'resid', 'log2 occmax']):
    print(nm, round(st.mean(x[i] for x in X), 3), 'max', round(max(x[i] for x in X), 2))
print('author<=dag', sum(x[2] <= x[1] + 1e-9 for x in X) / len(X), 'lb<=dag', sum(x[0] <= x[1] + 1e-9 for x in X) / len(X),
      'lb>=author', sum(x[0] >= x[2] - 1e-9 for x in X) / len(X), 'resid>0', sum(x[3] > 0 for x in X) / len(X))
bad = [r for r in ok if r['cN'][4] and r['nodes'] >= 10 and lg(r['cN'][3] / r['cN'][4]) > lg(r['tS'] / r['tD']) + 1e-9]
for r in bad[:6]:
    print(r['n'], r['cN'], r['tS'], r['tD'], r['tG'], [c[:3] for c in r['cuts'][:5]])
