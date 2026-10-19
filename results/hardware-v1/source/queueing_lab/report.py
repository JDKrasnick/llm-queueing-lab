"""All-cell reporting; figures show means and min/max across whole traces."""

from collections import defaultdict
import gzip
import json
from pathlib import Path
import statistics


def render(directory):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out = Path(directory)
    rows = json.loads((out/"summary.json").read_text())
    certificates = json.loads((out/"certificates.json").read_text())
    groups = defaultdict(list)
    for row in rows:
        groups[(row["setting"],row["pattern"],row["load"],row["policy"])].append(row)
    plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False})
    colors = {"fcfs":"#6a737d","pressure":"#087e8b"}
    figure,axes = plt.subplots(1,3,figsize=(14,4),layout="constrained")
    for setting,ax in zip(certificates,axes,strict=True):
        for policy in colors:
            keys = sorted(k for k in groups if k[0]==setting and k[1]=="poisson" and k[3]==policy)
            x,y,low,high = [],[],[],[]
            for key in keys:
                values = [r["metrics"]["completion_rate_s"] for r in groups[key]]
                x.append(key[2]); y.append(statistics.mean(values)); low.append(min(values)); high.append(max(values))
            ax.plot(x,y,"o-",label=policy,color=colors[policy])
            ax.fill_between(x,low,high,color=colors[policy],alpha=0.12)
        ax.axhline(certificates[setting]["requests_s"],linestyle="--",color="#bc4749",label="model capacity")
        ax.set(title=setting,xlabel="Offered rate / model capacity",ylabel="Completed requests / second")
    axes[0].legend(fontsize=8)
    figure.suptitle("Synthetic gated model · Poisson arrivals · mean and min/max of five traces")
    figure.savefig(out/"throughput.png",dpi=160)
    plt.close(figure)
    representative = []
    with gzip.open(out/"runs.jsonl.gz","rt") as f:
        for line in f:
            row = json.loads(line)
            if row["setting"]=="kv32_rows8" and row["pattern"]=="poisson" and row["load"] in (0.85,1.05) and row["seed"]==20261021:
                representative.append(row)
    figure,axes = plt.subplots(1,2,figsize=(11,4),layout="constrained")
    for ax,load in zip(axes,(0.85,1.05)):
        for row in representative:
            if row["load"]==load:
                ax.plot([x[0] for x in row["backlog"]],[x[1] for x in row["backlog"]],label=row["policy"],color=colors[row["policy"]])
        ax.set(title=f"Offered rate = {load:.2f} × model capacity",xlabel="Time (seconds)",ylabel="Unfinished requests")
        ax.legend()
    figure.suptitle("Preselected example trace · synthetic model, not a stability proof")
    figure.savefig(out/"backlog.png",dpi=160)
    plt.close(figure)
    figure,axes = plt.subplots(1,2,figsize=(11,4),layout="constrained")
    for policy in colors:
        keys = sorted(k for k in groups if k[0]=="kv32_rows8" and k[1]=="poisson" and k[3]==policy)
        x=[k[2] for k in keys]
        for ax,metric in zip(axes,("restricted_mean_response_s","observed_mean_ttft_s")):
            ax.plot(x,[statistics.mean(r["metrics"][metric] for r in groups[k]) for k in keys],"o-",color=colors[policy],label=policy)
    axes[0].set(ylabel="Restricted mean response (seconds)",title="Includes all offered requests; unfinished censored")
    axes[1].set(ylabel="Observed mean first-token latency (seconds)",title="Observed tokens only; censoring in the tables")
    for ax in axes:
        ax.set_xlabel("Offered rate / model capacity"); ax.legend()
    figure.savefig(out/"latency.png",dpi=160)
    plt.close(figure)
    lines=["# Complete synthetic screen", "", "These are model experiments, not ONNX Runtime GenAI speedup measurements.",
           "All cells below are retained. Values average five independent arrival traces; no confidence claim.",
           "Completion rates count only completions before the fixed horizon. Restricted response averages min(response, remaining observation time), including unfinished work.",
           "", "![Completion rate](throughput.png)","", "![Backlog](backlog.png)","", "![Latency](latency.png)","",
           "| Setting | Pattern | Load / capacity | Policy | Completed/s | Unfinished | Restricted response, s | Observed TTFT, s | TTFT censored |",
           "|---|---|---:|---|---:|---:|---:|---:|---:|"]
    for (setting,pattern,load,policy),cell in sorted(groups.items()):
        def avg(metric): return statistics.mean(r["metrics"][metric] for r in cell)
        lines.append(f"| {setting} | {pattern} | {load:.2f} | {policy} | {avg('completion_rate_s'):.2f} | {avg('unfinished'):.1f} | {avg('restricted_mean_response_s'):.3f} | {avg('observed_mean_ttft_s'):.3f} | {avg('ttft_censored'):.1f} |")
    pairs=json.loads((out/"pairs.json").read_text())
    costs={m:sum(p["metrics"][m]["relative_pct"] is not None and
                  p["metrics"][m]["relative_pct"] > 2 for p in pairs)
           for m in ("restricted_mean_response_s","observed_mean_ttft_s","observed_p99_gap_s")}
    lines += ["", "## Costs are retained", "",f"Across {len(pairs)} paired traces, pressure worsens these point metrics by more than 2%: `{costs}`.",
              "These counts are descriptive. Observed-only TTFT and gap metrics are not valid unconditional latency comparisons when censoring differs.",
              "", "## Network evidence", "", "`network.jsonl.gz` contains all fork/join task transitions, join buffers and root outcomes. `network-summary.json` retains every policy/seed/load.",
              "The single-server theorem is not a proof of network stability or a hardware multi-GPU result.",
              "", "## Reproduction", "", "The frozen plan includes settings, seeds, horizon and source SHA256 hashes. `runs.jsonl.gz` retains every offered request and cohort; synthetic token paths can be reconstructed from config and cohort start/action. This compact file is not a full per-token event log."]
    (out/"REPORT.md").write_text("\n".join(lines)+"\n")
    print(out/"REPORT.md")

