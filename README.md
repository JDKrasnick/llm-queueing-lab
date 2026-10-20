# Queueing networks for LLM scheduling

## Problem

An LLM server must share GPU compute and memory between incoming prompts and ongoing generation. Long prompts delay other requests; repeated prompt prefixes can duplicate work before their cached attention state (the KV cache) becomes reusable.

## Approach

We started from a pinned fork of Microsoft's open-source [ONNX Runtime GenAI](https://github.com/microsoft/onnxruntime-genai), rebuilt its native C++ scheduler, and tested changes inside the real Engine. All percentages use the frozen fork's normal configuration as baseline ([source snapshot](native/coalesce-source-manifest.json), `3d0d6eb`), with the same model, request traces and resource budgets.

- **Queue-aware ordering:** favor requests with less uncached prompt work, so smaller jobs spend less time behind expensive ones. Waiting age can override that preference.
- **Cache-aware scheduling:** consider KV-memory demand and prefix reuse. When queued requests share an uncached prefix, let one compute it first so the others can reuse its cached state.
- **RL:** train a small actor to choose FIFO, shortest-prefill or the cache-aware rule from the observed queue/cache state. The existing allocator still decides what fits.

## Results

One L4 GPU, Qwen2.5-0.5B-Instruct INT4, two held-out traces per workload/capacity setting. All changes compare with the frozen baseline. Class means cover all workloads; the other rows select each policy's best workload, not one simultaneous win.

| Metric | Cache-aware | RL | Scope / KV blocks (cache-aware; RL) |
|---|---:|---:|---|
| Shorter-prompt mean first-token wait | **1,160 → 633 ms (−45.4%)** | **1,160 → 633 ms (−45.4%)** | All workloads; 769-token prompts |
| Longer-prompt mean first-token wait | 1,282 → 1,359 ms (+6.0%) | 1,282 → 1,379 ms (+7.6%) | All workloads; 1,537-token prompts |
| Best mean first-token latency | **−14.1%** | **−14.3%** | Prefix reuse / 128; same |
| Best mean completion latency | **−10.9%** | **−11.4%** | Prefix reuse / 128; same |
| Best p99 pause between streamed tokens | **−6.0%** | **−10.8%** | Warm→cold / 32; cache churn / 32 |
| Best burst throughput | **+6.9%** | **+5.5%** | Warm→cold / 128; cache churn / 32 |

**Why distinguish prompt sizes?** Serving smaller uncached jobs sooner can reduce mean waiting time while pushing longer jobs back. Our controlled mix was **34.4% shorter / 65.6% longer** (352 / 672 requests per policy), with 32 output tokens for both classes. These are relative size labels, not a production traffic estimate; whether the tradeoff is useful depends on the deployment's prompt mix and latency requirements.

**Shorter prompts started about 527 ms sooner.** KV blocks measure available cache capacity; burst throughput does not establish sustainable serving capacity.

**What worked:** request ordering reduced average latency; coalescing increased observed prefix reuse in some workloads. **RL did not establish an advantage over the fork's existing shortest-prefill option**, which beat each prototype on mean first-token latency in 7/8 cells.

**Tradeoff:** longer prompts waited **77 ms more (+6.0%)** with cache-aware scheduling and **97 ms more (+7.6%)** with RL on average. Individual delays reached 1.32/1.37 seconds; some streaming gaps worsened. Default enablement is not justified.

[Full results and graphs](CACHE_RL_REPORT.md) · [Theory](docs/THEORY.md) · [Reproduce](cache_rl/REPRODUCE.md) · [Validate](VALIDATE_CACHE_RL.md)
