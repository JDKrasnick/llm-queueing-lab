# Cache-aware / RL active run

Native worktree: `/Users/fastcheetah/projects/onnxruntime-genai-cache-rl`, branch `research/cache-aware-rl`, base3d0d6eb. Python project on the same branch. Original private PR unchanged.

Native overlay built successfully in the authorized L4 Colab runtime. Wheel SHA256112bdf7820015a63ec3c1a92b0d1d9fe4b588cd7aefbaa1eccb62650c0d37efb. Full/focused Engine tests succeeded; exact counts await XML collection.

Experiment source uploaded and checksum-verified:82345bytes, SHA2563342d7ae0b0a6b839ec0091ba9a0d3571a8e0afa8e0906fbea326fcac8c52ccf. Native build upload50638bytes SHA25608c5e1dc0aa5bb639162cc792fdb29b1457abb41acbf239163df8cecff4aab7b.

Driver launched via own Safari Cell1 after a capture failure was checked to have caused no execution. `/content/cache-rl-experiments.log`; output `/content/cache-rl-results-v1`. Fixed cache screen28jobs, then8training references,24real-engine REINFORCE episodes, then64frozen holdout jobs. Checkpoints `/content/cache-rl-cache-screen.zip`, `/content/cache-rl-trained.zip`, `/content/cache-rl-complete.zip`.

Own notebook: https://colab.research.google.com/drive/1P9dXAUp8PR5PUp4L9yotyx0uftHJSw7d?authuser=1
CUA binding `labSafari`; helper `cacheCell(code)` clicks editor, super+A, pastes, Home and snapshot, End then ctrl+Return. Use CUA only for notebook work. Terminal panel is disconnected; query through Cell1. Do not run old cells, other notebooks, Kaggle or projects/genai-rl-scheduling. Do not spawn agents.

Experiments have not yet been analyzed. No gain, trained-policy quality or holdout pass is claimed. Download and verify checkpoints, analyze all failures/censoring/output hashes and per-request costs, verify source/binaries and action activity. Preserve frozen source; do not silently retune on holdout.

## Coalescing follow-up queued

The fixed cache ranking improves many TTFT points vs baseline but largely duplicates shortest; the v1 actor has nonzero learned weights and would choose shortest on1798/1808 recorded training states. New hypothesis: prevent duplicate cold prefixes from being admitted before a leader can seal reusable blocks. See COALESCE_PLAN.md. Native branch now research/cache-coalesce-rl; v1 native prototype committed separately. Coalescing tests pass under ASAN/UBSAN.

Final follow-up bundle `/private/tmp/cache-coalesce-upload.zip`:92868bytes, SHA2563fdb011a3618e08c26cf48c0c9034c5f3b0cd0c810d6eed9cf2048c01b184d1e. A previous92381byte bundle was uploaded but never extracted/executed; superseded before launch to strengthen the shortest control to the baseline native built-in option. Own Cell1 is completing final upload (`coalesce_upload2`). Need verify100%, extract to `/content/cache-coalesce-lab`, await original `cache_experiments` process, then launch `cache_rl/run_coalesce_pipeline.py`; this serializes build/GPU work after v1 holdout. No v2 build or experiments have started yet.

V1 checkpoint downloads saved: results/cache-rl-cache-screen-v1 (28jobs) and results/cache-rl-trained-v1 (60jobs). Checksums verified. Native actor audit verifies1808decisions, sampled actions[726,763,319], shortest reference, weight norm0.001328. Full Engine tests927pass/1skip/4disabled;48focusedpass. Need collect v1 complete124jobs and analyze.

## Follow-up launched; original pilot fully audited

Final v2 upload completed100%, checksum asserted. Coalescing pipeline PID128563 launched only after `cache_experiments.wait()` returned0. It runs `/content/cache-coalesce-lab/cache_rl/run_coalesce_pipeline.py` (build then124jobs) and logs `/content/cache-coalesce-pipeline.log`; native package `/content/cache-coalesce-package`, build `/content/cache-coalesce-build`, results `/content/cache-coalesce-results-v1`. Native build writes overlay and may recompile all164objects because mtimes are refreshed; do not overlap other GPU experiments.

Own Safari Cell1 currently runs a collector that waits for each `/content/cache-coalesce-{cache-screen,trained,complete}.zip`, prints checksum and calls files.download. **Do not edit or rerun Cell1 while collector is running**. Read its output/Downloads to track progress. If pipeline fails, collector asserts with last1200logchars; preserve all partial files before recovery. Binding `coalesce_pipeline` is process handle.

V1 complete downloaded `/Users/fastcheetah/Downloads/cache-rl-complete.zip`, SHA256b1eb3a223e5ae73de571166f9cf57cca45d494bf28e83d5ef5bc76c395037ad2, verified against notebook output. Extracted `results/cache-rl-native-v1`, analyzed and plotted.124jobs/7,936offered and complete;4,352paired complete output comparisons,0mismatches.27? localtests: previously26plus one reward test =>27 expected; rerun final suite. Heldout cache TTFT means improve3.2–14.2% vsbaseline but mostly match shortest, some gaps/throughput worsen. RL mostly shortest, no convincing increment over shortest.22per-trace/control metric cost flags. `cache_rl/analyze.py` andplot adapted for v2 package/mode and builtin shortest config difference. v2 frozen GPU source snapshot predates this local analysis adaptation, which is not executed inside driver.

V2 collector expected local downloads `cache-coalesce-cache-screen.zip`, `cache-coalesce-trained.zip`, `cache-coalesce-complete.zip`. Verify printedSHA, extract to distinct results/cache-coalesce-native-v1 (checkpoints to separate names), run `python -m cache_rl.analyze DIR` (or --partial), `python -m cache_rl.plot DIR`; audit all raw outputs, actor probabilities, source hashes, masks and CMakeXML. Fields support coalesce and baseline built-in SJF (no research helper overhead). New seeds development20262301,training20262401/2,heldout20262501/2. Do not retune either holdout.

Remaining: finishcoalescing/RLexperiment, analyze and report results honestly against baseline and builtin-shortest, add figures/summary/validation prompt, local test and native sanitizer checks, commit both standalone andnative worktrees without upstream/private PR changes, preserveoriginald147 archive. No new PR/push/contact.

## Safari visibility interruption

Collector was executing normally at4m33 with no checkpoints yet. Subsequent AX returnedcgWindowNotFound; getApp(Safari) alsofailed. Asked user asynchronously to bring ownnotebook front. Do not interrupt/restartremotejobs; v2 childpipeline andnotebookcollector continueindependently. Check Downloads for cache-coalesce-* files and wait for visiblewindow. No v2 results collected yet asoflastcheck.

Local collected-pilot report is CACHE_RL_REPORT.md; it explicitly marks coalescing results pending. VALIDATE_CACHE_RL.md covers native admission, real REINFORCE and fresh dataset controls. Replay verifies all24returns/6updates/frozenweights from1,808native decisions. No second-pilot results have been claimed.

## Pending user-visible window, final local checkpoint

Safari inventory confirms app running with no accessiblewindow. Rebindingbothname andcom.apple.Safari returnscgWindowNotFound. Userbring-notebook-front question remains pending; no approval is assumed. Lastnotebookstate collectorExecuting4m33, remotechildno observedfailure. No v2 archives inDownloads on latestcheck. All independent work is complete:28localtests pass; C++coalescing/smoke/2000-statefuzzsanitizerspass; first-pilot all28+32+64=124jobs audited/replayed.

Do not claim v2outcome/runningstatus ascurrentlyverified. Native sourceworktreecommits preservebothprototypes. Standaloneprojectoriginald147 archiveandoldverificationdescribeoriginalrelease; latestcache/RLworkisnewresearchbranch. CurrenthumanreportCACHE_RL_REPORT.md explicitlymarksv2pending. Finishcollecting/reportingv2onceSafariavailable, thenupdateartifacts/manifest/currentverificationandfullarchive.
