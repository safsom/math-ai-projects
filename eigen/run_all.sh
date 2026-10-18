#!/bin/zsh
# The whole extraction, one job at a time (about a day on a laptop; the OpenAI pass alone takes two hours).
# Stage 1 compiles the human projects and nine OpenAI projects module by module, as Lean's build would, and keeps
# their .olean files. Stage 2 is the final pass over every corpus: gestures, cut sizes and proof-term measures.
# Run python3 localize_jobs.py first, and build the driver (cd driver && lake build).
cd ${0:A:h}
export GESTURE_CUTS=1 GESTURE_TERMS=1 DRIVER=run_driver.sh
J=jobs/local
L=out_terms_v4/chain.log
mkdir -p out_h2 out_iso out_terms_v4 out_terms_v4_iso out_terms_v4_ai
for j in isolated_human isolated_openai isolated_openai_retry; do
  echo "$(date +%T) start $j" >> $L
  python3 run_isolated.py $J/$j.json out_terms_v4/run_$j.log >> $L 2>&1
done
for j in mathlib SphereEversion oai_olean iso oai; do
  echo "$(date +%T) start $j" >> $L
  ./run_driver.sh $J/terms_$j.json out_terms_v4/run_$j.log
  echo "$(date +%T) done $j rc=$?" >> $L
done
for c in putnam2025 imo2025 spherepacking; do
  echo "$(date +%T) start $c" >> $L
  python3 run_stream.py $J/terms_$c.json >> $L 2>&1
done
echo "$(date +%T) start Carleson (isolated)" >> $L
python3 run_isolated.py $J/terms_CarlesonIso.json out_terms_v4/run_CarlesonIso.log >> $L 2>&1
echo "$(date +%T) ALL DONE" >> $L
