# First paid GPU smoke

Authorized on 2026-08-03 with a maximum ceiling of US$ 5.00. The implementation
uses a stricter one-job, 900-second H100 boundary whose GPU maximum is below
approximately US$ 1.00 at the current published Modal rate.

1. Confirm the current Modal credit and obtain explicit approval for a maximum financial ceiling. Current code must not be treated as proof of the live balance.
2. Pose templates are not required for the Master-only smoke; keep all pose generation blocked.
3. Use only the pet photo already uploaded by the authenticated Android user.
4. Confirm model `Qwen/Qwen-Image-Edit-2511` plus the 4-step Lightning LoRA, GPU `H100`, environment `development`, and exactly three Master outputs.
5. Keep `max_containers=1`, `generations_per_user_per_day=1`, no automatic retry, and a US$ 1.00 logical reservation.
6. Set `GPU_GENERATION_ENABLED=true` only in the temporary development deployment and verify `/health` before submitting the one job.
7. Create exactly one job and generate exactly three Masters. Do not approve a Master or start poses.
8. Record cold start, model load, inference duration, GPU-seconds, actual cost, and any failure.
9. Immediately set `GPU_GENERATION_ENABLED=false`, redeploy, and verify `/health` reports `generation_enabled=false`. Cancel the job first if it is still active.
10. Ask for human approval of one Master and of the measured cost. Only after a new explicit approval may the three consistency poses be tested.

Do not benchmark, retry automatically, generate six production poses, or proceed to twenty poses during this smoke.
