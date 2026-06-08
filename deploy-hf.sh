#!/bin/bash
# After running this, re-upload sample_session.wav via browser on both HF Spaces
git checkout --orphan hf-deploy
git add -A
git commit -m "deploy"
git push hf hf-deploy:main --force
git push org hf-deploy:main --force
git checkout main
git branch -D hf-deploy
