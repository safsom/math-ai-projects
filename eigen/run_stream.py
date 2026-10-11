"""Run a streaming-mode job to completion: one shared environment, theorems written per module.

When the driver stalls (no output for STALL seconds) or dies, the module it was on is marked bad,
it and everything importing it are dropped, and the driver restarts: modules already extracted that
remaining ones still import are replayed (elaborated, not extracted). Usage: run_stream.py JOB.json
JOB must carry `deps` ({module: [project modules it imports]}) next to the driver's own fields.
"""
import json, os, signal, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
STALL = int(os.environ.get('STALL', 1800))
job = json.load(open(sys.argv[1]))
out, P = job['out'], job['projects'][0]
deps = job.pop('deps')
order = [m['mod'] for m in P['modules']]
path = {m['mod']: m['path'] for m in P['modules']}
logp = os.path.join(out, P['name'] + '.log.jsonl')
badp = os.path.join(out, P['name'] + '.bad.txt')
os.makedirs(out, exist_ok=True)


def closure(ms):
    seen, stack = set(), list(ms)
    while stack:
        m = stack.pop()
        if m in seen:
            continue
        seen.add(m)
        stack += [d for d in deps.get(m, []) if d in path]
    return seen


for attempt in range(1000):
    done = {json.loads(l)['module'] for l in open(logp)} if os.path.exists(logp) else set()
    bad = set(open(badp).read().split()) if os.path.exists(badp) else set()
    # drop everything that imports a bad module
    dead = set(bad)
    for m in order:
        if any(d in dead for d in deps.get(m, [])):
            dead.add(m)
    rest = [m for m in order if m not in done and m not in dead]
    if not rest:
        print(time.strftime('%H:%M:%S'), f'finished: {len(done)} extracted, {len(dead)} dropped', flush=True)
        break
    need = closure(rest)
    mods = [dict(mod=m, path=path[m], replay=m in done) for m in order if m in need]
    jp = os.path.join(out, 'job_stream_cur.json')
    json.dump(dict(job, projects=[dict(name=P['name'], modules=mods)]), open(jp, 'w'))
    runlog = os.path.join(out, f'run_{attempt}.log')
    print(time.strftime('%H:%M:%S'), f'attempt {attempt}: {len(rest)} to extract, {len(mods) - len(rest)} to replay', flush=True)
    proc = subprocess.Popen([os.path.join(HERE, 'run_driver3.sh'), jp, runlog], start_new_session=True)
    last_size, last_t = -1, time.time()
    while proc.poll() is None:
        time.sleep(15)
        size = os.path.getsize(runlog) if os.path.exists(runlog) else 0
        if size != last_size:
            last_size, last_t = size, time.time()
        elif time.time() - last_t > STALL:
            break
    if proc.poll() is None:
        os.killpg(proc.pid, signal.SIGKILL)
        time.sleep(3)
    if 'streaming pass finished' in open(runlog, errors='replace').read():
        continue
    # the module the driver was on: first one in this job's order that it did not report
    reported = set()
    for line in open(runlog, errors='replace'):
        if line.startswith('  ') and ':' in line:
            reported.add(line.split(':')[0].strip())
    cur = next((m['mod'] for m in mods if m['mod'] not in reported), None)
    if cur:
        with open(badp, 'a') as f:
            f.write(cur + '\n')
        print(time.strftime('%H:%M:%S'), f'stalled or died on {cur}; dropping it and its dependents', flush=True)
