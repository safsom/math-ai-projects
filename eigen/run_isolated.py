"""Run an isolated-mode job to completion, restarting the driver after a crash.

Before each restart, theorem lines from modules that never reached the log are dropped.
"""
import json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
job_path, runlog = sys.argv[1], sys.argv[2]
job = json.load(open(job_path))
stalls, last = 0, None
for attempt in range(200):
    for p in job['projects']:
        lp = os.path.join(job['out'], p['name'] + '.log.jsonl')
        dp = os.path.join(job['out'], p['name'] + '.jsonl')
        done = {json.loads(l)['module'] for l in open(lp)} if os.path.exists(lp) else set()
        if os.path.exists(dp):
            keep = [l for l in open(dp) if json.loads(l)['m'] in done]
            open(dp, 'w').writelines(keep)
    with open(runlog, 'a') as f:
        f.write(f'== attempt {attempt} {time.strftime("%H:%M:%S")}\n')
    rc = subprocess.call(['zsh', '-c', f'{HERE}/{os.environ.get("DRIVER", "run_driver.sh")} {job_path} {runlog}.cur; cat {runlog}.cur >> {runlog}'])
    if 'theorems extracted' in open(f'{runlog}.cur').read().split('project ')[-1]:
        print('finished', flush=True)
        break
    cur = open(f'{runlog}.cur').read()
    logged = sum(sum(1 for _ in open(os.path.join(job['out'], p['name'] + '.log.jsonl')))
                 for p in job['projects'] if os.path.exists(os.path.join(job['out'], p['name'] + '.log.jsonl')))
    stalls = stalls + 1 if logged == last else 0
    last = logged
    if stalls >= 3:
        print(time.strftime('%H:%M:%S'), 'no progress in 3 attempts; giving up', flush=True)
        break
    print(time.strftime('%H:%M:%S'), 'budget spent; restarting' if 'budget spent' in cur else 'driver died; restarting', flush=True)
