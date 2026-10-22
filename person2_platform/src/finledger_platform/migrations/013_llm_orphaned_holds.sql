-- Orphaned token holds. A worker that dies between llm_reserve_tokens and settlement leaves a 'held' row with
-- no expiry, and held rows count toward the bill's cap forever. 012 is applied as written; this adds:
--
--   state 'expired'                    the call's outcome is unknown: kept for audit, no longer counted toward the
--                                      cap (llm_reserve_tokens counts only 'held'), never reconciled or released
--   llm_expire_orphaned_tokens(...)    called by a worker right after claiming a document's job, under that live
--                                      lease: expires the document's holds created before this claim, unless some
--                                      other job for the document is still running under a live lease
--
-- Nothing here changes who may reserve, reconcile or release, or grants posting or payment.

alter table llm_token_reservations drop constraint llm_token_reservations_state_check;
alter table llm_token_reservations add constraint llm_token_reservations_state_check
  check (state in ('held', 'reconciled', 'released', 'expired'));

create function llm_expire_orphaned_tokens(p_client_id uuid, p_document_id uuid, p_job_id bigint,
                                           p_claim_token uuid) returns int
language plpgsql volatile security definer set search_path = public, pg_temp as $$
declare claimed_at timestamptz; expired int;
begin
  perform llm_worker_required();
  if app_client_id() is distinct from p_client_id then
    raise exception 'tenant_mismatch';
  end if;
  -- Same row lock as llm_reserve_tokens, so no reservation for this bill lands mid-sweep.
  perform 1 from documents where client_id = p_client_id and id = p_document_id for update;
  if not found then
    raise exception 'document_not_found';
  end if;
  -- claim_job stamps updated_at when it leases a job; holds older than that belong to earlier attempts.
  select updated_at into claimed_at from jobs
   where id = p_job_id and client_id = p_client_id and document_id = p_document_id
     and state = 'running' and claim_token = p_claim_token and locked_until >= now();
  if not found then
    raise exception 'live_lease_required';
  end if;
  if exists (select 1 from jobs
              where client_id = p_client_id and document_id = p_document_id and id <> p_job_id
                and state = 'running' and locked_until >= now()) then
    return 0;
  end if;
  update llm_token_reservations set state = 'expired', updated_at = now()
   where client_id = p_client_id and document_id = p_document_id and state = 'held' and created_at < claimed_at;
  get diagnostics expired = row_count;
  return expired;
end $$;

revoke execute on function llm_expire_orphaned_tokens(uuid, uuid, bigint, uuid) from public, finledger_app;
grant execute on function llm_expire_orphaned_tokens(uuid, uuid, bigint, uuid)
  to finledger_worker_extract, finledger_worker_score, finledger_worker_map;
