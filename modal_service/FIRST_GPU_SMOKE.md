# First paid GPU smoke — do not run yet

This procedure requires a new explicit human authorization.

1. Confirm the current Modal credit and obtain explicit approval for a maximum financial ceiling. Current code must not be treated as proof of the live balance.
2. Confirm the official, validated template package is installed.
3. Record the exact pet photo selected by the user for the smoke; status is currently **pending explicit selection and authorization**.
4. Confirm model `Qwen/Qwen-Image-Edit-2511`, GPU `L40S`, environment `development`, and exactly three Master outputs.
5. Keep `max_containers=1`, `jobs_per_user_per_day=1`, one total test job, no automatic retry, and the smallest approved daily cap.
6. Set `GPU_GENERATION_ENABLED=true` only in the temporary development deployment and verify `/health` before submitting the one job.
7. Create exactly one job and generate exactly three Masters. Do not approve a Master or start poses.
8. Record cold start, model load, inference duration, GPU-seconds, actual cost, and any failure.
9. Immediately set `GPU_GENERATION_ENABLED=false`, redeploy, and verify `/health` reports `generation_enabled=false`. Cancel the job first if it is still active.
10. Ask for human approval of one Master and of the measured cost. Only after a new explicit approval may the three consistency poses be tested.

Do not benchmark, retry automatically, generate six production poses, or proceed to twenty poses during this smoke.
