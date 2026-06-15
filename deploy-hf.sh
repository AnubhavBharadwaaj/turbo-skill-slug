#!/bin/bash
git checkout --orphan hf-deploy
git add -A
git rm -r --cached --ignore-unmatch \
  sample_session.wav \
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
  swe_chat_loader.py
git commit -m "deploy"
git push hf hf-deploy:main --force
git push org hf-deploy:main --force
HF_DEPLOY_TOKEN=$(git remote get-url hf | sed -E 's#https://[^:]+:([^@]+)@.*#\1#')
hf upload legendarydragontamer/TurboSkillSlug sample_session.wav sample_session.wav \
  --repo-type=space \
  --token "$HF_DEPLOY_TOKEN" \
  --commit-message="upload sample session audio"
hf upload build-small-hackathon/TurboSkillSlug sample_session.wav sample_session.wav \
  --repo-type=space \
  --token "$HF_DEPLOY_TOKEN" \
  --commit-message="upload sample session audio"
if [ -f sample_session.wav ]; then
  TMP_SAMPLE=$(mktemp "${TMPDIR:-/tmp}/sample_session.deploy.XXXXXX")
  mv sample_session.wav "$TMP_SAMPLE"
fi
git checkout main
git branch -D hf-deploy
