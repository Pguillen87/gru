# Models

| Provider | Purpose | License | Production status |
| --- | --- | --- | --- |
| Qwen-Image-Edit-2511 | primary master and pose candidate | Apache-2.0 | candidate |
| OmniGen2 | benchmark comparison | Apache-2.0 | candidate |
| FLUX.2 Klein | technical comparison | non-commercial weights | benchmark only |

## First Master smoke

The base candidate is pinned to `Qwen/Qwen-Image-Edit-2511` revision
`6f3ccc0b56e431dc6a0c2b2039706d7d26f22cb9`. The first smoke loads the
Apache-2.0 4-step Lightning LoRA from
`lightx2v/Qwen-Image-Edit-2511-Lightning` revision
`d74eba145674fd7e31b949324e148e21e7118abd`.

The BF16 repository is larger than the 48 GB available on L40S, so the guarded
smoke uses one H100. Input is capped at 1024 pixels on its longest side, exactly
three seeds are generated, the worker has no automatic retry, and its timeout is
900 seconds. Pose generation remains disabled until official templates and the
consistency gate are approved.
