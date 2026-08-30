$ErrorActionPreference = "Stop"

# This script deploys only the v2 Production control plane. Cost-bearing work
# remains disabled; enabling it is a separate, audited operation.
$env:GRU_MASCOT_APP_NAME = "gru-mascot-v2-production"
$env:GRU_MASCOT_ENV = "production"
$env:GRU_MASCOT_RESOURCE_PREFIX = "gru-mascot-v2-production"
$env:GRU_FIREBASE_SECRET_NAME = "gru-mascot-v2-production-firebase-admin"
$env:GRU_PULEIRO_BFF_SECRET_NAME = "gru-mascot-v2-production-puleiro-bff"
$env:GPU_GENERATION_ENABLED = "false"
$env:REGISTRATION_ENABLED = "true"
$env:MASTER_GENERATION_ENABLED = "false"
$env:POSE_GENERATION_ENABLED = "false"

modal deploy .\modal_service\app.py
