#!/bin/bash
# After running this, re-upload sample_session.wav via browser on both HF Spaces
git checkout --orphan hf-deploy
git add -A
git rm -r --cached --ignore-unmatch \
  swe_chat_traces \
  distractor_runs \
  skill_eval_runs \
  run_swe_chat_phases_v2.py \
  fetch_swe_chat_v2.py \
  nebius_loader.py \
  trace2skill_faithful.py \
  promotion_engine.py \
  gotcha_cluster.py \
  session_store.py \
  artifact_meta.py \
  rule_phrasing.py \
  swe_chat_loader.py
git commit -m "deploy"
git push hf hf-deploy:main --force
git push org hf-deploy:main --force
git checkout main
git branch -D hf-deploy
