# KARMO H0.1 Failure-Test Matrix

Status: FROZEN FOR REVIEW — TESTS NOT YET EXECUTED

All pre-cutover tests use an isolated PostgreSQL test namespace and the isolated Qdrant collection `karmo_h01_outbox_test`. Tests must never point to `karmo_semantic_memory`, `karmo_documents`, or `karmo_h00_dense_baseline` unless a row explicitly says read-only baseline verification.

| ID | Scenario | Injection/action | Required result |
| --- | --- | --- | --- |
| H01-T01 | Evidence continuity | Reverify H0.0 and every H0.1 manifest | All pass before testing |
| H01-T02 | Fail after user insert | Raise before assistant insert | Zero exchange rows and zero outbox rows commit |
| H01-T03 | Fail after assistant insert | Raise before outbox insert | Zero exchange rows and zero outbox rows commit |
| H01-T04 | Fail after outbox insert | Raise before transaction exit | Zero exchange rows and zero outbox rows commit |
| H01-T05 | Successful atomic exchange | Commit one controlled exchange | Exactly two conversation rows and one pending event commit |
| H01-T06 | Ollama unavailable | Block the isolated worker embedding endpoint | Event becomes retry; conversation rows remain; no point is created |
| H01-T07 | Qdrant unavailable | Block the isolated Qdrant target | Event becomes retry; conversation rows remain; no point is lost |
| H01-T08 | Crash before Qdrant write | Kill worker after claim | Stale lease is reclaimed; one point is eventually delivered |
| H01-T09 | Crash after Qdrant write | Kill worker before delivered update | Retry uses the same point ID; exactly one point exists; event becomes delivered |
| H01-T10 | Duplicate delivery | Deliver the same event at least three times | Same point is replaced; point count remains one for that event |
| H01-T11 | Claim-token fencing | Let an old worker finish after lease reclamation | Old token updates zero rows and cannot overwrite the newer state |
| H01-T12 | Concurrent workers | Run two workers against at least 20 events | All events deliver without duplicate knowledge |
| H01-T13 | Malformed permanent event | Supply invalid payload in isolated test data | Event becomes dead, stores sanitized error, creates no point, and is not auto-requeued |
| H01-T14 | Restart recovery | Stop/restart worker with pending, retry, and stale-processing rows | Every valid event is eventually delivered without duplicates |
| H01-T15 | Behavior preservation | Commit one user/assistant exchange | Only the user prompt is represented in semantic memory |
| H01-T16 | Digest integrity | Alter isolated authoritative content after enqueue | Digest mismatch becomes dead; incorrect text is never embedded |
| H01-T17 | Healthy delivery latency | Deliver at least 20 warm events | 100% delivered within 10 seconds each; no query/delivery error |
| H01-T18 | Baseline and rollback drill | Reverify live counts/hashes and exercise non-destructive rollback procedure | H0.0 stays reproducible; no existing row/point is deleted or rewritten |

Pass rule: every required result must pass. Any failure blocks production schema or application changes. Test criteria may not be weakened after results are known; a design revision requires a new directory and manifest.
