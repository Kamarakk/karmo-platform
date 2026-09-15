# KARMO Project Save — 2026-09-14 Dual-Worker Commander Checkpoint

## Status
**VERIFIED — dual-worker Commander READ production gate PASS**

Reviewed Commander activation merge: `1423bc7ef82ca0bb9d9f421f3be5c25dcf52c002`

Production coordinator host: `karmo-ai01`

## Activated worker capabilities
Both production workers are ACTIVE with the same durable capability claim:

- `local_model_probe` `1.0.0`
- `commander.system_snapshot` `1.0.0`
- `commander.service_status` `1.0.0`
- `commander.listener_snapshot` `1.0.0`

`commander.bounded_text_read` and `commander.directory_list` remain disabled. Their `allowed_root` wiring is not yet production-complete and they continue to fail closed.

## Worker01 production proof
- Worker: `KARMO-WORKER01`
- Canary tool: `commander.system_snapshot` `1.0.0`
- Approval: `f8d15b7f-1591-40fb-8269-8d875bade029`
- Job: `f00c7b5a-cab6-43c3-83d1-256688202409`
- Job state: `SUCCEEDED`
- Attempt count: `1`
- Approval final state: `EXECUTED`
- Execution ticket: issued and consumed
- Result digest: `d3e012370e73bdae4eeda0dd85698e4059a1a22d4ddbaccf699be1c184cd5132`
- Durable event chain verified: `JOB_LEASED` → `EXECUTION_TICKET_ISSUED` → `EXECUTION_TICKET_CONSUMED` → `RESULT_SUBMITTED` → `JOB_SUCCEEDED`
- Tool invocation ledger reached terminal `EXECUTED` state.

## Worker02 production proof
- Worker: `KARMO-WORKER02`
- Canary tool: `commander.system_snapshot` `1.0.0`
- Approval: `8b75487c-f5f2-4d61-b9b3-4e93890b4958`
- Job: `65797770-00a2-4cfd-95e9-c6bbc1a45589`
- Job state: `SUCCEEDED`
- Attempt count: `1`
- Approval final state: `EXECUTED`
- Execution ticket: consumed
- Result digest: `3c944c6611cd209129cd0c3530942320a845d49da347146fe864d70fa5317976`
- Durable events verified for the job include `JOB_LEASED`, `RESULT_SUBMITTED`, and `JOB_SUCCEEDED`; ticket state independently confirms consumption.
- Tool invocation ledger reached terminal `EXECUTED` state.

## Production permission repairs
Two least-privilege database grants were required to let the existing reviewed gateway API persist the real approval/job path. No broader role expansion was made for these fixes.

```sql
GRANT INSERT ON TABLE public.core_approval_records TO karmo_gateway;
GRANT INSERT ON TABLE public.karmo_worker_jobs TO karmo_gateway;
```

After repair, `karmo_gateway` has the required approval/job persistence rights while the production workflow still uses KARMO's approval engine, durable worker queue, payload binding, one-time execution ticket, authenticated result submission, event log, and invocation ledger.

## Network and listener verification
- No new KARMO application listener was introduced on `karmo-ai01` during Worker01 Commander activation/canary.
- Worker02 post-activation listener output remained limited to expected OS services (DHCP/DNS/SSH); no Commander listener was introduced.
- Production worker execution remains outbound worker → AI01 coordination; no inbound Commander service was added to workers.

## Security properties preserved
- No cloud provider credentials or APIs were introduced.
- No arbitrary shell capability was enabled.
- No unrestricted file read/list capability was enabled.
- SSH host-key verification remained enforced for worker deployment.
- Admin private key remained on the development Mac during worker deployment.
- Root SSH remained disabled on workers.

## Gate closure
The two-worker Commander READ activation gate is closed. Worker01 and Worker02 are independently production-proven through the durable approval → job → payload → lease → ticket → execution → authenticated result → event/ledger path.

## Next approved sequence
1. Complete durable memory and operational state using the existing local PostgreSQL/Qdrant/Ollama foundation and reviewed Core boundaries.
2. Preserve progressive disclosure and fail-closed capability exposure.
3. After durable memory/operations, selectively adapt useful ECC concepts rather than installing the full external stack.
4. Later reduce or replace temporary broad AI01 sudo delegation after launch-critical deployment work is complete.
