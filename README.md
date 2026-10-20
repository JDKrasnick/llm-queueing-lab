# Queueing networks for LLM scheduling

## Problem

Long prompts delay other requests; repeated prompt prefixes waste compute and KV-cache space.

## Approach

Model compute/KV limits as queues, then test cache-aware request ordering, shared-prefix coalescing, and RL selection among scheduling rules in Microsoft's ONNX Runtime GenAI Engine.

## Results

One L4 GPU, Qwen2.5-0.5B-Instruct INT4, two held-out traces per workload/capacity setting. Compared with normal repository code:

| Metric | Cache-aware | RL |
|---|---:|---:|
| Shorter-prompt mean time to first token, all workloads | **−45.4%** | **−45.4%** |
| Best workload mean time to first token | **−14.1%** | **−14.3%** |
| Best workload mean completion latency | **−10.9%** | **−11.4%** |
| Best workload p99 pause between streamed tokens | **−6.0%** | **−10.8%** |
| Best workload burst throughput | **+6.9%** | **+5.5%** |

Shorter prompts received their first token in **633 ms versus 1,160 ms—527 ms sooner**. Peaks come from different workloads; burst throughput does not establish sustainable serving capacity.

**What worked:** request ordering reduced average latency; coalescing increased observed prefix reuse in some workloads. **RL showed no established advantage over existing shortest-prefill**, which beat each prototype on mean first-token latency in 7/8 cells.

**Tradeoff:** longer prompts waited **77 ms more (+6.0%)** with cache-aware scheduling and **97 ms more (+7.6%)** with RL on average. Individual delays reached 1.32/1.37 seconds; some streaming gaps worsened. Default enablement is not justified.

[Full results and graphs](CACHE_RL_REPORT.md) · [Theory](docs/THEORY.md) · [Reproduce](cache_rl/REPRODUCE.md) · [Validate](VALIDATE_CACHE_RL.md)
