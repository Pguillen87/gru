# Cost controls

All environments default to `GPU_GENERATION_ENABLED=false`. The authorized development environment permits one Modal container and uses the available US$30.00 workspace credit as its logical daily ceiling. Idempotency and serialized scheduling remain mandatory, but validation jobs are not artificially restricted during product testing.

Two ledgers are intentionally separate:

- `user-jobs:<day>:<uid>` and `global-jobs:<day>` count accepted job creations and protect API/storage abuse, including churn across anonymous UIDs;
- `user-cost:<day>:<uid>` and `global-cost:<day>` reserve estimated generation cost only immediately before a GPU operation.

An idempotent replay does not increment either ledger. When generation is disabled, no cost key is created and no GPU function is spawned. Estimates are not billing facts; actual GPU-seconds and Modal billing must be measured during the separately authorized smoke.
