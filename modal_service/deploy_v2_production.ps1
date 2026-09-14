param(
  [switch]$EnableProductionGeneration
)

$ErrorActionPreference = "Stop"

# This switch is deliberately explicit because the deployment can schedule
# paid GPU work. The default publishes only the compatible control plane.
$enabled = $EnableProductionGeneration.IsPresent
$env:GRU_MASCOT_APP_NAME = "gru-mascot-v2-production"
$env:GRU_MASCOT_ENV = "production"
$env:GRU_MASCOT_RESOURCE_PREFIX = "gru-mascot-v2-production"
$env:GRU_FIREBASE_SECRET_NAME = "gru-mascot-v2-production-firebase-admin"
$env:GRU_PULEIRO_BFF_SECRET_NAME = "gru-mascot-v2-production-puleiro-bff"
$env:GPU_GENERATION_ENABLED = if ($enabled) { "true" } else { "false" }
$env:REGISTRATION_ENABLED = "true"
$env:MASTER_GENERATION_ENABLED = if ($enabled) { "true" } else { "false" }
$env:POSE_GENERATION_ENABLED = if ($enabled) { "true" } else { "false" }
$env:INCUBATOR_FLOW_ENABLED = if ($enabled) { "true" } else { "false" }
$env:INCUBATOR_AUTO_RANKING_ENABLED = if ($enabled) { "true" } else { "false" }
$env:INCUBATOR_VISUAL_ENCODER_DIR = "/gru-models/siglip-base-p16-224-zeroshot-v1"

if ($enabled) {
  Write-Host "Deploying the production generation path with explicit GPU authorization."
} else {
  Write-Host "Deploying the production control plane with cost-bearing work disabled."
}

modal deploy -m modal_service.app
