# GV POWERS Backup & Owner Server — API Contract (v1)

ERP (`erp.gvpowers.in`) → Backup Server (`backup.gvpowers.in`).

The backup server is an **IMMUTABLE HISTORICAL ARCHIVE**, not a live mirror.
This contract is binding for whoever implements/maintains the backup server.

## NON-NEGOTIABLE RETENTION RULES

1. Once business data reaches the backup database it must **never be physically
   deleted** because of anything that happens in the ERP.
2. There is **no delete/purge endpoint**. The ERP never sends one, and none may
   ever be added that removes archived data.
3. ERP DELETE ≠ BACKUP DELETE. A deletion in the ERP produces a `deleted`
   event; the archive marks the record `DELETED_IN_ERP` and keeps:
   - the complete original record,
   - every stored version,
   - the deletion event, timestamp (`deleted_at`),
   - the responsible user (`deleted_by`),
   - the original ERP record ID.
4. Updates are append-only: each `updated` event becomes a NEW version;
   previous versions are never overwritten.
5. Deleted records remain searchable/viewable on the backup site forever.

## Transport & security

- HTTPS only. The ERP rejects non-HTTPS endpoints unless the host is localhost.
- Every request carries:
  - `Authorization: Bearer <BACKUP_API_KEY>` (server-to-server key)
  - `X-GV-Site-Id: <site_id>` (default `gvpowers-erp`)
  - `X-GV-Event-Id: <event_id>` (idempotency key)
  - `X-GV-Timestamp: <ISO8601 UTC>`
  - `Content-Type: application/json`

## Endpoints

### `GET /api/v1/health`

Response:

```json
{ "status": "ok", "service": "gvpowers-backup" }
```

Must not expose server internals.

### `POST /api/v1/events`

Ingests exactly one event. Response codes:

| Code | Meaning | ERP behaviour |
|------|---------|---------------|
| 200 / 201 / 202 | stored (or already stored) | event completed |
| 409 | duplicate `event_id` | treated as SUCCESS (idempotent) |
| 401 / 403 | bad key | event kept for retry, connection marked failed |
| 429 / 5xx | temporary failure | retry with exponential backoff |
| 400 | malformed payload | event failed after retries; error surfaced in Settings |

### `POST /api/v1/events/batch`

Same semantics per item; used by "Sync Now". Body: `{"events": [ ... ]}`.

## Event envelope

```json
{
  "event_id": "32-hex-uuid4",
  "site_id": "gvpowers-erp",
  "entity": "invoice",
  "operation": "created | updated | deleted",
  "entity_id": 123,
  "version": 3,
  "timestamp": "2026-08-21T11:00:00Z",
  "actor": { "id": 1, "username": "admin" },
  "data": { "...full record snapshot..." },
  "previous_data": { "...snapshot before an update..." },
  "deletion": {
    "status": "DELETED_IN_ERP",
    "deleted_at": "2026-08-21T11:00:00Z",
    "deleted_by": "admin"
  }
}
```

Rules:

- `data` is ALWAYS the complete record (including child items arrays), so the
  archive can reconstruct history without querying the ERP.
- `operation=deleted` still carries the FULL last-known snapshot in `data`.
- The backup server MUST deduplicate on `event_id`: receiving the same event
  twice returns success and creates nothing new.
- Supported entities: `customer`, `product`, `supplier`, `purchase_order`
  (embeds purchase items), `quotation` (embeds quotation items), `invoice`
  (embeds invoice items), `payment`, `user`, `audit_log`.
- `user` payloads NEVER contain password hashes or secrets.

## Versioning

`version` starts at 1 on `created` and increments on every `updated`/`deleted`
event emitted by the ERP for that entity ID. It is advisory; the archive's own
append-only history is authoritative.

## Failure isolation

The ERP queues events locally (`backup_events` outbox table) and retries with
exponential backoff. The ERP keeps working normally when the backup server is
offline, misconfigured, or slow. Backup failures must never block or roll back
ERP transactions.
