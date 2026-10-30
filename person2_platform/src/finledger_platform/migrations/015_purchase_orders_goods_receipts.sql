-- Purchase orders and goods receipts for a three-way match.
-- Every row is one client's. No sample client is inserted.

create table purchase_orders (
  id           uuid primary key default gen_random_uuid(),
  client_id    uuid not null references clients(id) on delete cascade,
  po_number    text not null,
  vendor_name  text not null default '',
  quantity     numeric(14,3) not null check (quantity >= 0),
  amount       numeric(14,2) not null check (amount >= 0),
  created_at   timestamptz not null default now(),
  constraint purchase_orders_number_not_blank check (length(btrim(po_number)) > 0),
  unique (client_id, po_number)
);

create table goods_receipts (
  id                 uuid primary key default gen_random_uuid(),
  client_id          uuid not null references clients(id) on delete cascade,
  grn_number         text not null,
  po_number          text not null,
  quantity_received  numeric(14,3) not null check (quantity_received >= 0),
  created_at         timestamptz not null default now(),
  constraint goods_receipts_number_not_blank check (length(btrim(grn_number)) > 0),
  constraint goods_receipts_po_not_blank check (length(btrim(po_number)) > 0),
  unique (client_id, grn_number)
);
create index goods_receipts_client_po on goods_receipts (client_id, po_number);

alter table purchase_orders enable row level security;
alter table goods_receipts enable row level security;
create policy tenant on purchase_orders
  using (client_id = app_client_id()) with check (client_id = app_client_id());
create policy tenant on goods_receipts
  using (client_id = app_client_id()) with check (client_id = app_client_id());

grant select, insert, update, delete on purchase_orders, goods_receipts to finledger_app;

do $$
declare api_role text;
begin
  foreach api_role in array array['anon', 'authenticated', 'service_role'] loop
    if exists (select from pg_roles where rolname = api_role) then
      execute format('revoke all privileges on purchase_orders, goods_receipts from %I', api_role);
    end if;
  end loop;
end $$;
