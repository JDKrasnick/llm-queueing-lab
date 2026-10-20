# Queueing networks for LLM scheduling

## Problem

An LLM server must share GPU compute and memory between incoming prompts and ongoing generation. Long prompts delay other requests; repeated prompt prefixes can duplicate work before their cached attention state (the KV cache) becomes reusable.

## Approach

We started from a pinned fork of Microsoft's open-source [ONNX Runtime GenAI](https://github.com/microsoft/onnxruntime-genai), rebuilt its native C++ scheduler, and tested changes inside the real Engine. All percentages use the frozen fork's normal configuration as baseline ([source snapshot](native/coalesce-source-manifest.json), `3d0d6eb`), with the same model, request traces and resource budgets.

Queueing models describe compute and KV-cache limits. The prototype orders requests by uncached work and cache demand, lets one request compute a shared cold prefix before its duplicates, and trains a small RL actor to choose between scheduling rules.

## Results

One L4 GPU, Qwen2.5-0.5B-Instruct INT4, two held-out traces per workload/capacity setting. Compared with normal repository code:

Shorter prompts received their first token in **633 ms versus 1,160 ms—527 ms sooner (−45.4%)** across all held-out workloads. Longer prompts paid a smaller average cost:

![Mean first-token wait: shorter prompts fall from 1,160 to 633 ms with either policy; longer prompts rise from 1,282 to 1,359 ms with cache-aware scheduling and 1,379 ms with RL.](docs/figures/first-token-tradeoff.png)

The strongest workload-specific gains follow. Peaks come from different workloads; burst throughput does not establish sustainable serving capacity.

![Best improvements for cache-aware / RL: first-token latency 14.1% / 14.3%, completion latency 10.9% / 11.4%, p99 streaming gap 6.0% / 10.8%, burst throughput 6.9% / 5.5%. Each bar labels its selected workload and KV capacity.](docs/figures/best-measured-gains.png)

**What worked:** request ordering reduced average latency; coalescing increased observed prefix reuse in some workloads. **RL did not establish an advantage over the fork's existing shortest-prefill option**, which beat each prototype on mean first-token latency in 7/8 cells.

**Tradeoff:** longer prompts waited **77 ms more (+6.0%)** with cache-aware scheduling and **97 ms more (+7.6%)** with RL on average. Individual delays reached 1.32/1.37 seconds; some streaming gaps worsened. Default enablement is not justified.

[Full results and graphs](CACHE_RL_REPORT.md) · [Theory](docs/THEORY.md) · [Reproduce](cache_rl/REPRODUCE.md) · [Validate](VALIDATE_CACHE_RL.md)

Regenerate these figures with `.venv/bin/python scripts/plot_readme.py`.
