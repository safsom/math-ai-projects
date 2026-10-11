"""Run the gesture driver over a job's OpenAI projects, restarting it whenever a module stalls.

A project whose module makes no progress for STALL seconds is recorded in out/skipped.txt and skipped.
Progress = lines in the per-project module logs plus finished project outputs.
"""
import glob, json, os, signal, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = json.load(open(sys.argv[1]))['out'] if len(sys.argv) > 1 else os.path.join(HERE, 'out')
STALL = int(os.environ.get('STALL', 1500 if os.environ.get('GESTURE_CUTS') == '1' else 360))
DEADLINE = float(os.environ.get('DEADLINE', 1e18))
IMPORT_MAX = 1200
job = json.load(open(sys.argv[1]))
skip_path = os.path.join(OUT, 'skipped.txt')


def skipped():
    return set(open(skip_path).read().split()) if os.path.exists(skip_path) else set()


def progress(names):
    n = 0
    for p in names:
        lp = os.path.join(OUT, p + '.log.jsonl')
        if os.path.exists(lp):
            n += sum(1 for _ in open(lp))
        if os.path.exists(os.path.join(OUT, p + '.jsonl')):
            n += 1000
    return n


while True:
    sk = skipped()
    rest = [p for p in job['projects'] if not os.path.exists(os.path.join(OUT, p['name'] + '.jsonl')) and p['name'] not in sk]
    if not rest:
        print('all done', flush=True)
        break
    for p in rest:  # stale partial logs from a killed run
        lp = os.path.join(OUT, p['name'] + '.log.jsonl')
        if os.path.exists(lp):
            os.remove(lp)
    jr = dict(job, projects=rest, mathlibNames='')
    jp = os.path.join(OUT, 'job_rest.json')
    json.dump(jr, open(jp, 'w'))
    runlog = os.path.join(OUT, f'run_rest_{int(time.time())}.log')
    names = [p['name'] for p in rest]
    print(time.strftime('%H:%M:%S'), f'starting driver on {len(rest)} projects', flush=True)
    proc = subprocess.Popen([os.path.join(HERE, os.environ.get('DRIVER', 'run_driver.sh')), jp, runlog], start_new_session=True)
    t0 = time.time()
    last, last_t, started = progress(names), time.time(), False
    while proc.poll() is None:
        time.sleep(10)
        n = progress(names)
        if not started:
            if any(os.path.exists(os.path.join(OUT, x + '.log.jsonl')) for x in names):
                started, last, last_t = True, n, time.time()
            elif time.time() - t0 > IMPORT_MAX:
                print('import stalled; restarting', flush=True)
                os.killpg(proc.pid, signal.SIGKILL)
                break
            continue
        if n != last:
            if time.time() > DEADLINE and n // 1000 > last // 1000:
                print(time.strftime('%H:%M:%S'), 'deadline reached after a finished project; stopping', flush=True)
                os.killpg(proc.pid, signal.SIGKILL)
                sys.exit(0)
            last, last_t = n, time.time()
        elif time.time() - last_t > STALL:
            logs = [(os.path.getmtime(os.path.join(OUT, x + '.log.jsonl')), x) for x in names
                    if os.path.exists(os.path.join(OUT, x + '.log.jsonl')) and not os.path.exists(os.path.join(OUT, x + '.jsonl'))]
            cur = max(logs)[1] if logs else names[0]
            with open(skip_path, 'a') as f:
                f.write(cur + '\n')
            print(time.strftime('%H:%M:%S'), f'stalled in {cur}; skipping it and restarting', flush=True)
            os.killpg(proc.pid, signal.SIGKILL)
            time.sleep(5)
            break
    else:
        print(time.strftime('%H:%M:%S'), 'driver exited', proc.returncode, flush=True)
