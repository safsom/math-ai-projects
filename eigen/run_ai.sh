#!/bin/zsh
# Other AI corpora, after the cut-statistics chain: streaming shared-mode jobs, smallest first.
cd /Users/safsom/Projects/math-ai-projects/eigen
until grep -q "CARLESON DONE" out_cut/chain.log 2>/dev/null; do sleep 60; done
export GESTURE_CUTS=1
mkdir -p out_ai
for c in putnam2025 imo2025 spherepacking erdos90 flt; do
  echo "$(date +%T) start $c" >> out_ai/chain.log
  python3 run_stream.py job_ai_$c.json >> out_ai/chain.log 2>&1
  echo "$(date +%T) done $c" >> out_ai/chain.log
done
echo "$(date +%T) AI ALL DONE" >> out_ai/chain.log
