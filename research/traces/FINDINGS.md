# Trace extraction: reproducible scripts on public agent traces

## What this is
Reproducible scripts to run the TurboSkillSlug extractor over public agent-session
datasets. Provided so the dataset claim in the README is inspectable and runnable.
No extractions are committed here; run the scripts to generate them.

## Datasets
- SALT-NLP/SWE-chat
- nebius/SWE-agent-trajectories

## Reproduce
```
pip install datasets
export OPENROUTER_API_KEY=...
cd research/traces
python nebius_loader.py --n 12 --k 2 --out nebius_sample_extractions.json
# or: python fetch_swe_chat_v2.py --n 8 --out swe_chat_sessions.jsonl
#     python run_swe_chat_phases_v2.py --in swe_chat_sessions.jsonl --out out.json
```

## What we observed in development
On a handful of sessions, gotchas were specific and real (named functions, ref
namespaces, build-tool quirks). Cross-session promotion only fired within one
codebase. Offline check using a frontier extractor; the shipped app uses only
sub-32B models. Treated as exploratory, not a benchmark.
