# Modal v2 Production

The fail-closed production deployment uses a dedicated Modal app, resource
prefix, and secret names. `deploy_v2_production_fail_closed.ps1` intentionally
sets GPU, Master generation, and pose generation to `false`.

Before deployment, provision only these secrets in the Production Modal
environment:

- `gru-mascot-v2-production-puleiro-bff` with `PULEIRO_BFF_JWT_SECRET`;
- `gru-mascot-v2-production-firebase-admin` with the production Firebase
  credential if legacy v1 endpoints remain enabled.

The Web BFF must use the same production-only JWT secret, issuer, audience and
TTL (maximum 120 seconds). Do not enable cost-bearing flags until health and
capabilities confirm the fail-closed deployment and an authorized production
test is ready to begin.
