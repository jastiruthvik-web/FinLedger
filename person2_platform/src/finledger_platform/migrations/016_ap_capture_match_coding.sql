-- Invoice capture provenance stays on documents (hash, raw bytes, client_id).
-- This migration adds line-level purchasing, receipt allocation, tolerances,
-- department routing, and human match facts. No sample company is inserted.
-- Delivery notes are not accepted goods receipts until a person sets status.

alter table documents drop constraint if exists documents_channel_check;
alter table documents add constraint documents_channel_check
  check (channel in ('link', 'email', 'csv', 'portal', 'whatsapp', 'mail_scan'));

alter table purchase_orders
  add column supplier_gstin text not null default '',
  add column currency text not null default 'INR',
  add column source text not null default 'manual' check (source in ('manual', 'import'));

alter table goods_receipts
  add column supplier_gstin text not null default '',
  add column currency text not null default 'INR',
  add column source text not null default 'manual' check (source in ('manual', 'import')),
  add column document_kind text not null default 'goods_receipt'
    check (document_kind in ('goods_receipt', 'delivery_note')),
  add column status text not null default 'accepted'
    check (status in ('pending_review', 'accepted', 'rejected', 'duplicate'));

create table purchase_order_lines (
  id                 uuid primary key default gen_random_uuid(),
  client_id          uuid not null references clients(id) on delete cascade,
  purchase_order_id  uuid not null references purchase_orders(id) on delete cascade,
  line_no            int not null check (line_no > 0),
  item_code          text not null default '',
  description        text not null default '',
  uom                text not null default '',
  quantity           numeric(14,3) not null check (quantity >= 0),
  unit_price         numeric(14,4) not null default 0 check (unit_price >= 0),
  tax_rate           numeric(8,4),
  currency           text not null default 'INR',
  unique (purchase_order_id, line_no)
);

create table goods_receipt_lines (
  id            uuid primary key default gen_random_uuid(),
  client_id     uuid not null references clients(id) on delete cascade,
  receipt_id    uuid not null references goods_receipts(id) on delete cascade,
  line_no       int not null check (line_no > 0),
  po_line_no    int not null check (po_line_no > 0),
  item_code     text not null default '',
  description   text not null default '',
  uom           text not null default '',
  quantity      numeric(14,3) not null check (quantity >= 0),
  unit_price    numeric(14,4),
  unique (receipt_id, line_no)
);
create index goods_receipt_lines_po on goods_receipt_lines (client_id, po_line_no);

create table receipt_allocations (
  id               bigint generated always as identity primary key,
  client_id        uuid not null references clients(id) on delete cascade,
  document_id      uuid not null,
  receipt_line_id  uuid not null references goods_receipt_lines(id) on delete restrict,
  invoice_line_no  int not null check (invoice_line_no > 0),
  quantity         numeric(14,3) not null check (quantity <> 0),
  kind             text not null check (kind in ('reserve', 'credit')),
  released_at      timestamptz,
  created_at       timestamptz not null default now(),
  foreign key (client_id, document_id) references documents(client_id, id) on delete cascade,
  check ((kind = 'reserve' and quantity > 0) or (kind = 'credit' and quantity < 0))
);
create unique index receipt_allocations_open
  on receipt_allocations (document_id, receipt_line_id, invoice_line_no)
  where released_at is null;
create index receipt_allocations_line on receipt_allocations (receipt_line_id) where released_at is null;

create function receipt_allocation_within_received() returns trigger
language plpgsql as $$
declare received numeric(14,3); net numeric(14,3); line_id uuid;
begin
  line_id := coalesce(new.receipt_line_id, old.receipt_line_id);
  select quantity into received from goods_receipt_lines where id = line_id for update;
  if received is null then
    raise exception 'receipt line missing' using errcode = '23514';
  end if;
  select coalesce(sum(quantity), 0) into net
    from receipt_allocations
   where receipt_line_id = line_id and released_at is null;
  if net > received then
    raise exception 'receipt line over-allocated' using errcode = '23514';
  end if;
  if net < 0 then
    raise exception 'credit exceeds invoiced quantity' using errcode = '23514';
  end if;
  return null;
end $$;

create constraint trigger receipt_allocations_cap
  after insert or update on receipt_allocations
  deferrable initially immediate
  for each row execute function receipt_allocation_within_received();

create table match_tolerances (
  client_id    uuid not null references clients(id) on delete cascade,
  version      int not null check (version > 0),
  qty_abs      numeric(14,3) not null default 0 check (qty_abs >= 0),
  qty_pct      numeric(8,6) not null default 0 check (qty_pct >= 0 and qty_pct <= 1),
  price_abs    numeric(14,4) not null default 0.0100 check (price_abs >= 0),
  price_pct    numeric(8,6) not null default 0 check (price_pct >= 0 and price_pct <= 1),
  tax_abs      numeric(8,4) not null default 0 check (tax_abs >= 0),
  amount_abs   numeric(14,2) not null default 0.01 check (amount_abs >= 0),
  note         text not null default '',
  created_by   uuid,
  created_at   timestamptz not null default now(),
  primary key (client_id, version)
);

create table invoice_line_facts (
  client_id    uuid not null,
  document_id  uuid not null,
  line_no      int not null check (line_no > 0),
  uom          text not null default '',
  currency     text not null default '',
  item_code    text not null default '',
  po_line_no   int,
  primary key (document_id, line_no),
  foreign key (client_id, document_id) references documents(client_id, id) on delete cascade
);

create table match_overrides (
  id           bigint generated always as identity primary key,
  client_id    uuid not null,
  document_id  uuid not null,
  revision     int not null check (revision > 0),
  reason       text not null check (length(btrim(reason)) >= 8),
  actor_id     uuid not null,
  created_at   timestamptz not null default now(),
  unique (document_id, revision),
  foreign key (client_id, document_id) references documents(client_id, id) on delete cascade
);

create table departments (
  id           uuid primary key default gen_random_uuid(),
  client_id    uuid not null references clients(id) on delete cascade,
  code         text not null,
  name         text not null,
  cost_centre  text not null default '',
  active       boolean not null default true,
  created_at   timestamptz not null default now(),
  unique (client_id, code),
  check (length(btrim(code)) > 0),
  check (length(btrim(name)) > 0)
);

create table department_approvers (
  client_id      uuid not null references clients(id) on delete cascade,
  department_id  uuid not null references departments(id) on delete cascade,
  user_id        uuid not null references users(id),
  created_at     timestamptz not null default now(),
  primary key (department_id, user_id)
);

create table bill_routes (
  document_id    uuid primary key,
  client_id      uuid not null,
  department_id  uuid references departments(id),
  status         text not null check (status in (
                   'unassigned', 'pending', 'approved', 'rejected', 'no_approver', 'admin_fallback')),
  revision       int not null default 1 check (revision > 0),
  note           text not null default '',
  decided_by     uuid,
  decided_at     timestamptz,
  foreign key (client_id, document_id) references documents(client_id, id) on delete cascade
);

create table purchasing_events (
  id          bigint generated always as identity primary key,
  client_id   uuid not null references clients(id) on delete cascade,
  action      text not null,
  actor_id    uuid,
  payload     jsonb not null default '{}',
  created_at  timestamptz not null default now()
);

-- Labels for people already on this company. The caller must be inside that tenant.
create function client_member_labels(p_client_id uuid)
returns table (user_id uuid, email text)
language sql stable security definer set search_path = public, pg_temp as $$
  select u.id, u.email
    from users u
    join clients c on c.firm_id = u.firm_id
   where c.id = p_client_id
     and c.id = app_client_id()
$$;

alter table purchase_order_lines enable row level security;
alter table goods_receipt_lines enable row level security;
alter table receipt_allocations enable row level security;
alter table match_tolerances enable row level security;
alter table invoice_line_facts enable row level security;
alter table match_overrides enable row level security;
alter table departments enable row level security;
alter table department_approvers enable row level security;
alter table bill_routes enable row level security;
alter table purchasing_events enable row level security;

create policy tenant on purchase_order_lines
  using (client_id = app_client_id()) with check (client_id = app_client_id());
create policy tenant on goods_receipt_lines
  using (client_id = app_client_id()) with check (client_id = app_client_id());
create policy tenant on receipt_allocations
  using (client_id = app_client_id()) with check (client_id = app_client_id());
create policy tenant on match_tolerances
  using (client_id = app_client_id()) with check (client_id = app_client_id());
create policy tenant on invoice_line_facts
  using (client_id = app_client_id()) with check (client_id = app_client_id());
create policy tenant on match_overrides
  using (client_id = app_client_id()) with check (client_id = app_client_id());
create policy tenant on departments
  using (client_id = app_client_id()) with check (client_id = app_client_id());
create policy tenant on department_approvers
  using (client_id = app_client_id()) with check (client_id = app_client_id());
create policy tenant on bill_routes
  using (client_id = app_client_id()) with check (client_id = app_client_id());
create policy tenant on purchasing_events
  using (client_id = app_client_id()) with check (client_id = app_client_id());

grant select, insert, update, delete on
  purchase_order_lines, goods_receipt_lines, receipt_allocations, match_tolerances,
  invoice_line_facts, match_overrides, departments, department_approvers, bill_routes,
  purchasing_events
  to finledger_app;
grant usage, select on all sequences in schema public to finledger_app;

revoke all on function client_member_labels(uuid) from public;
revoke all on function receipt_allocation_within_received() from public;
grant execute on function client_member_labels(uuid) to finledger_app;
grant execute on function receipt_allocation_within_received() to finledger_app;

do $$
declare api_role text;
begin
  foreach api_role in array array['anon', 'authenticated', 'service_role'] loop
    if exists (select from pg_roles where rolname = api_role) then
      execute format('revoke all privileges on purchase_order_lines, goods_receipt_lines, receipt_allocations, match_tolerances, invoice_line_facts, match_overrides, departments, department_approvers, bill_routes, purchasing_events from %I', api_role);
    end if;
  end loop;
end $$;
