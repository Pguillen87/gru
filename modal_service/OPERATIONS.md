# Operations

## Initial state

The Modal workspace was inspected before implementation: no applications, secrets, or volumes existed. The Modal client is 1.3.0.post1.

## Deployment

Deploy with the active Modal profile. Deployment creates the named Volumes and Dicts lazily. GPU inference is charged only when generation is scheduled.

## Retention

Originals and rejected masters are temporary. Approved masters and poses require an external durable storage decision before production. Cleanup must be idempotent and delete only job-scoped prefixes after the configured retention period.
