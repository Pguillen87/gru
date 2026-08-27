param(
    [switch]$EnableGpuTest
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

$stagingEnvironment = "gru-mascot-v2-staging"
$env:GRU_MASCOT_ENV = "staging"
$env:GRU_MASCOT_APP_NAME = "gru-mascot-v2-staging"
$env:GRU_MASCOT_RESOURCE_PREFIX = "gru-mascot-v2-staging"
$env:GRU_FIREBASE_SECRET_ENVIRONMENT = $stagingEnvironment
$env:GRU_FIREBASE_SECRET_NAME = "gru-mascot-v2-staging-firebase-admin"
$env:GRU_PULEIRO_BFF_SECRET_NAME = "gru-mascot-v2-staging-puleiro-bff"
$generationEnabled = if ($EnableGpuTest) { "true" } else { "false" }
$env:GPU_GENERATION_ENABLED = $generationEnabled
$env:REGISTRATION_ENABLED = "true"
$env:MASTER_GENERATION_ENABLED = $generationEnabled
# A Master-only smoke must never make pose generation callable. Poses need a
# separate explicit rollout after their own pre-flight and authorization.
$env:POSE_GENERATION_ENABLED = "false"
$env:PULEIRO_BFF_JWT_ISSUER = "puleiro-bff"
$env:PULEIRO_BFF_JWT_AUDIENCE = "gru-modal"
$env:PULEIRO_BFF_JWT_MAX_TTL_SECONDS = "120"

modal deploy -m modal_service.app --env $stagingEnvironment --name "gru-mascot-v2-staging"
