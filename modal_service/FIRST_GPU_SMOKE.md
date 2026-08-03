# First paid GPU smoke — do not run yet

This procedure requires a new explicit human authorization.

1. Confirm the current Modal credit and approve a maximum financial ceiling.
2. Confirm an official, validated template package is installed.
3. Confirm the pet photo is explicitly authorized for this test.
4. Set `GPU_GENERATION_ENABLED=true` only in the temporary development deployment.
5. Keep `max_containers=1`, `jobs_per_user_per_day=1`, and the smallest daily cap sufficient for one test.
6. Create exactly one job and generate exactly three Masters.
7. Record cold start, model load, inference duration, GPU-seconds, and actual cost.
8. Stop; disable generation and redeploy with `GPU_GENERATION_ENABLED=false`.
9. Ask for human approval of one Master and of the measured cost.
10. Only after that approval, test the three consistency poses.

Do not benchmark, retry automatically, generate six production poses, or proceed to twenty poses during this smoke.
