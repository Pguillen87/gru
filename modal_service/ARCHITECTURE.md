# Architecture

The Modal app owns asynchronous mascot work only. `modal_service.domain` contains the stable job state machine; API and GPU code depend on it, not the reverse.

## Resources

- `gru-mascot-assets` Volume: private original, master, consistency, pose, and temporary objects.
- `gru-mascot-models` Volume: model cache only; it contains no user media.
- `gru-mascot-jobs` Dict: short-lived operational job state.
- `gru-mascot-idempotency` Dict: duplicate-charge protection.
- `gru-mascot-usage` Dict: cost-guard ledger.

Approved assets require an external durable object store before production, because Modal Dict entries expire after inactivity and Volumes are not a database. The API exposes identifiers only; it never exposes container paths.

## API lifecycle

`create → poll → approve master → consistency → generate MVP poses → poll result`.

The currently deployed API only opens the master approval transition. Consistency and pose endpoints are intentionally withheld until the official pose-reference assets and the external authenticated control plane exist; generating against absent pose assets would create unreviewable, billable output.
