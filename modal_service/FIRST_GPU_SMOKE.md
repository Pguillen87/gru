# First paid GPU smoke

The first paid smoke was completed on 2026-08-03. Subsequent development testing
was explicitly authorized against the US$30.00 workspace credit. Every generation
still uses a single H100 container, a 900-second timeout, stable idempotency, and no
automatic retry.

1. Confirm the current Modal credit and obtain explicit approval for a maximum financial ceiling. Current code must not be treated as proof of the live balance.
2. Pose templates are not required for the Master-only smoke; keep all pose generation blocked.
3. Use only the pet photo already uploaded by the authenticated Android user.
4. Confirm model `Qwen/Qwen-Image-Edit-2511` plus the 4-step Lightning LoRA, GPU `H100`, environment `development`, and exactly three Master outputs.
5. Keep `max_containers=1`, no automatic retry, and the US$30.00 development ceiling.
6. Set `GPU_GENERATION_ENABLED=true` only in the temporary development deployment and verify `/health` before submitting the one job.
7. Each accepted job generates exactly three Masters. Do not start poses without the official templates.
8. Record cold start, model load, inference duration, GPU-seconds, actual cost, and any failure.
9. Immediately set `GPU_GENERATION_ENABLED=false`, redeploy, and verify `/health` reports `generation_enabled=false`. Cancel the job first if it is still active.
10. Ask for human approval of one Master and of the measured cost. Only after a new explicit approval may the three consistency poses be tested.

Do not benchmark, retry automatically, generate six production poses, or proceed to twenty poses during this smoke.
