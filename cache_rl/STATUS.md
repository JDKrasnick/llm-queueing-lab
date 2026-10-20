# Cache-aware scheduling and RL: complete

Both pilots are collected, analyzed and replayed. Start with CACHE_RL_REPORT.md.
The latest native policy and RL actor do not qualify for default enablement:
mean TTFT improves versus normal baseline, but class/individual costs remain
and the existing built-in shortest policy usually has lower mean TTFT.

## Repositories and scope

- Python project: /Users/fastcheetah/projects/llm-queueing-lab, research/cache-aware-rl.
- Native prototype: /Users/fastcheetah/projects/onnxruntime-genai-cache-rl,
  research/cache-coalesce-rl, commit fd7b66a. Base3d0d6eb1327a959c54f2a41f6741ab9414e50286.
- No upstream/private PR push or merge. Original KV-cap PR left unchanged.
- Original d147a49 release archive preserved with its original checksum.

## Evidence

- Ranking pilot: results/cache-rl-native-v1.124jobs,7936offered/completed,
  4352complete paired outputs,1808verified sampled decisions,24replayed
  episodes and6reproduced updates.
- Corrected coalescing repeat: results/cache-coalesce-native-v1.124jobs,
  7936offered/completed,4352complete paired outputs,1818verified decisions,
  24replayed episodes and6reproduced updates. No output mismatches/failed jobs.
- Complete repeat download: /Users/fastcheetah/Downloads/cache-coalesce-complete.zip,
  43738066bytes, SHA256c2bfd704bc4c8557ffd2ce70f7e7a54d980652d8e53c153d60f9ade04af5cf69.
- Retained build bundle: results/cache-coalesce-native-v1/build/build-evidence.zip,
  SHA2564f61dcef020a6d049746fe332ed999b5911e15f35005c5820e6c03416f026898.
  Both measured binary packages match retained wheel members. Baseline source
  archive matches all1311tracked Git blobs; all7overlayfiles match fd7b66a.
- Baseline wheel SHA256b32679acd52cd56ca5e98f3b59968259698b36ddc4295855444d24fa49a24d75.
- Candidate wheel SHA25686fb57946f71afc9d0b790831a522310e64378e74ac9cb5af5e5d4e3e31445a1.
- All11current measurement/training/build Python files match executed snapshot.
  Additional local analysis/reporting edits are separate and archived in Git.
- Native Engine tests927pass/1skip/4disabled, focused48pass. Local56tests pass;
  standalone C++ order/coalescing and2000-state fuzz pass ASAN/UBSAN.
- Full validation summary: results/cache-rl-verification.json.

## Relevant independent audit repairs

User supplied ../llm-queueing-lab-validation-20261019/REPORT.md, auditing d147a49.
Applied relevant shared harness/report repairs before repeat measurements.
See VALIDATION_REPAIRS.md and tests/test_validation_repairs.py. Original raw
observations and the independent validator's snapshot were not edited.
The lost first coalescing run is excluded from performance evidence; its
completion checksums are retained in results/cache-coalesce-lost-run.json.

## Runtime

Authorized notebook in Safari/jdk342 account:
https://colab.research.google.com/drive/1P9dXAUp8PR5PUp4L9yotyx0uftHJSw7d?authuser=1

Corrected pipeline and collector both completed with exit0. No experiment is
running. Cell1 retains the successful collector output. Safari download
permission was accepted and the final local archive verified. Do not rerun
old notebook cells. Read-only reproduction instructions: cache_rl/REPRODUCE.md.
Earlier operational details and setup failures are preserved in RUN_LOG.md.

## Delivery

Current package version0.2.0. artifacts/llm_queueing_lab-0.2.0-py3-none-any.whl
matches all28packaged Python source files and passed an isolated installation
smoke check. Default enablement and a general serving improvement are unsupported.
Independent-agent instructions are VALIDATE_CACHE_RL.md.
