#!/bin/zsh
# Third pass (Prop test that unfolds definitions in ranks; count of hidden-proposition cuts), after sphere packing.
# Replaces the tail of run_terms_night.sh (Carleson second pass). One job at a time.
cd /Users/safsom/Projects/math-ai-projects/eigen
export GESTURE_CUTS=1 GESTURE_TERMS=1 DRIVER=run_driver3.sh
L=out_terms/chain.log; L3=out_terms_v3/chain.log
mkdir -p out_terms_v3 out_terms_v3_iso out_terms_v3_ai
while pgrep -f "run_stream.py job_terms_spherepacking.json" > /dev/null; do sleep 60; done
echo "$(date +%T) done spherepacking" >> $L
echo "$(date +%T) TERMS ALL DONE" >> $L
cp lean3b/.lake/build/bin/gestures lean3/.lake/build/bin/gestures.new && mv lean3/.lake/build/bin/gestures.new lean3/.lake/build/bin/gestures
cp lean3b/Terms.lean lean3/Terms.lean
echo "$(date +%T) binary v3 $(md5 -q lean3/.lake/build/bin/gestures)" >> $L3
for j in mathlib SphereEversion oai_olean iso; do
  echo "$(date +%T) start $j" >> $L3
  ./run_driver3.sh job_terms3_$j.json out_terms_v3/run_$j.log
  echo "$(date +%T) done $j rc=$?" >> $L3
done
for c in putnam2025 imo2025; do
  echo "$(date +%T) start $c" >> $L3
  python3 run_stream.py job_terms3_$c.json >> $L3 2>&1
  echo "$(date +%T) done $c" >> $L3
done
echo "$(date +%T) start Carleson (isolated)" >> $L3
python3 run_isolated.py job_terms3_CarlesonIso.json out_terms_v3/run_CarlesonIso.log >> $L3 2>&1
echo "$(date +%T) V3 ALL DONE" >> $L3
