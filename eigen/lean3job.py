"""Fill a driver job with every field the driver's derived FromJson expects."""
import json, sys
D = dict(mathlibNames='', projects=[], trace=[], isolated=False, oleanDir='', maxModules=1000000, oleanProjects=[],
         maxHeartbeats=0, synthHeartbeats=0, falseOptions=[], natOptions=[], streaming=False)


def fill(j):
    for k, v in D.items():
        j.setdefault(k, v)
    for p in j['projects'] + j['oleanProjects']:
        for m in p['modules']:
            m.setdefault('replay', False)
    return j


if __name__ == '__main__':
    for p in sys.argv[1:]:
        json.dump(fill(json.load(open(p))), open(p, 'w'))
