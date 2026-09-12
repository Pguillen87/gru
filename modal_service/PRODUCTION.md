# Modal v2 Production

The production deployment uses a dedicated Modal app, resource prefix, and
secret names. `deploy_v2_production_fail_closed.ps1` intentionally sets GPU,
Master generation, and pose generation to `false`. The compatible deployment
script `deploy_v2_production.ps1` keeps that safe default and requires the
explicit `-EnableProductionGeneration` switch before paid work can run.

Before deployment, provision only these secrets in the Production Modal
environment:

- `gru-mascot-v2-production-puleiro-bff` with `PULEIRO_BFF_JWT_SECRET`;
- `gru-mascot-v2-production-firebase-admin` with the production Firebase
  credential if legacy v1 endpoints remain enabled.

The Web BFF must use the same production-only JWT secret, issuer, audience and
TTL (maximum 120 seconds). Do not enable cost-bearing flags until health and
capabilities confirm the fail-closed deployment, the encoder/QC contract is
verified, and an authorized production test is ready to begin. New jobs use
`master-ranker-policy-v2`: among candidates passing hard gates, the highest
score wins and ties are resolved by candidate ID; no margin gate or human
selection is part of the normal path.
