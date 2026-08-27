$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

# This script has no Modal app deploy and no GPU call. Its immutable target is
# the staging Volume only; the installer rejects the production prefix.
$env:GRU_MASCOT_ENV = "staging"
$env:GRU_MASCOT_RESOURCE_PREFIX = "gru-mascot-v2-staging"
$env:GRU_MASCOT_MODAL_ENVIRONMENT = "gru-mascot-v2-staging"

py -3.12 -m modal_service.tools.install_pose_templates `
  modal_service/pose_templates/web-poses-v1 `
  --resource-prefix "gru-mascot-v2-staging" `
  --environment "gru-mascot-v2-staging"
