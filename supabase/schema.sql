-- Cuentas de casa — esquema. Ejecutar entero en Supabase → SQL Editor.
-- Proyecto compartido con Carga GPS (ref laqwymoxwegemdjlqqya): no hay tablas con estos nombres.

create table profiles (
  id uuid primary key references auth.users on delete cascade,
  nombre text not null
);

create table cuentas (
  id text primary key,
  nombre text not null,
  banco text not null,
  tipo text not null check (tipo in ('corriente', 'ahorro', 'inversion', 'efectivo', 'deuda')),
  owner uuid references auth.users,          -- null = compartida
  iban_final text,                           -- últimos 4 dígitos, para reconocer el extracto
  orden int not null default 0
);

create table categorias (
  id text primary key,
  nombre text not null,
  icono text not null,
  cuenta_como_gasto boolean not null default true,
  orden int not null default 0,
  grupo text check (grupo in ('piso')),      -- null = categoría normal
  owner uuid references auth.users           -- null = de todos; si no, solo la ve su dueño
);

create table movimientos (
  id uuid primary key default gen_random_uuid(),
  cuenta_id text not null references cuentas,
  fecha date not null,
  importe_cent integer not null,             -- negativo = sale dinero
  descripcion text not null default '',
  comercio text not null,
  categoria_id text references categorias,
  nota text not null default '',
  ticket_path text,                         -- foto en Storage: <cuenta_id>/<uuid>.jpg
  no_es_gasto boolean not null default false,
  origen text not null check (origen in ('import', 'manual')),
  creado_por uuid references auth.users default auth.uid(),
  huella text not null unique default ('manual-' || gen_random_uuid()::text),
  created_at timestamptz not null default now()
);
create index movimientos_cuenta_fecha on movimientos (cuenta_id, fecha);

create table reglas (
  id uuid primary key default gen_random_uuid(),
  patron text not null,                      -- se busca contenido en el comercio, sin mayúsculas
  categoria_id text not null references categorias,
  owner uuid references auth.users,          -- null = compartida
  created_at timestamptz not null default now(),
  unique nulls not distinct (patron, owner)
);

create table saldos (
  cuenta_id text not null references cuentas,
  fecha date not null,
  saldo_cent bigint not null,
  primary key (cuenta_id, fecha)
);

-- Privacidad -----------------------------------------------------------------

-- Solo los dos usuarios con perfil (creados por el administrador) son "de casa".
create function es_de_casa() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from profiles where id = auth.uid())
$$;

create function puede_ver_cuenta(c text) returns boolean
language sql stable security definer set search_path = public as $$
  select es_de_casa() and exists (select 1 from cuentas where id = c and (owner is null or owner = auth.uid()))
$$;

alter table profiles enable row level security;
alter table cuentas enable row level security;
alter table categorias enable row level security;
alter table movimientos enable row level security;
alter table reglas enable row level security;
alter table saldos enable row level security;

create policy "perfiles visibles" on profiles for select to authenticated using (es_de_casa());
create policy "cuentas propias o compartidas" on cuentas for select to authenticated
  using (es_de_casa() and (owner is null or owner = auth.uid()));
create policy "categorias visibles" on categorias for select to authenticated
  using (es_de_casa() and (owner is null or owner = auth.uid()));

create policy "ver movimientos" on movimientos for select to authenticated
  using (puede_ver_cuenta(cuenta_id));
create policy "apuntar a mano" on movimientos for insert to authenticated
  with check (puede_ver_cuenta(cuenta_id) and origen = 'manual' and creado_por = auth.uid());
create policy "editar movimientos" on movimientos for update to authenticated
  using (puede_ver_cuenta(cuenta_id)) with check (puede_ver_cuenta(cuenta_id));
create policy "borrar lo apuntado a mano" on movimientos for delete to authenticated
  using (origen = 'manual' and creado_por = auth.uid());

create policy "ver reglas" on reglas for select to authenticated
  using (es_de_casa() and (owner is null or owner = auth.uid()));
create policy "crear reglas" on reglas for insert to authenticated
  with check (es_de_casa() and (owner is null or owner = auth.uid()));
create policy "editar reglas" on reglas for update to authenticated
  using (es_de_casa() and (owner is null or owner = auth.uid()))
  with check (es_de_casa() and (owner is null or owner = auth.uid()));

create policy "ver saldos" on saldos for select to authenticated
  using (puede_ver_cuenta(cuenta_id));

-- Permisos: nada para anónimos; desde la app solo se editan 4 columnas de movimientos
-- y solo se pueden insertar las columnas de un apunte manual (id y huella salen de los defaults).
-- Solo nuestras tablas: el proyecto se comparte con las notificaciones de Carga GPS
-- (tabla gps_push_subs, que el anónimo SÍ necesita). No tocar permisos de todo el esquema.
revoke all on profiles, cuentas, categorias, movimientos, reglas, saldos from anon;
revoke execute on function es_de_casa() from public, anon;
grant execute on function es_de_casa() to authenticated;
revoke execute on function puede_ver_cuenta(text) from public, anon;
grant execute on function puede_ver_cuenta(text) to authenticated;
revoke update on movimientos from authenticated;
grant update (categoria_id, nota, no_es_gasto, ticket_path) on movimientos to authenticated;
revoke insert on movimientos from authenticated;
grant insert (cuenta_id, fecha, importe_cent, descripcion, comercio, categoria_id, nota, no_es_gasto, origen, creado_por, ticket_path)
  on movimientos to authenticated;

-- Fotos de tickets ---------------------------------------------------------------
-- Ruta <cuenta_id>/<uuid>.jpg: solo quien puede ver la cuenta ve o sube sus fotos.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('tickets', 'tickets', false, 5242880, array['image/jpeg']);

create policy "ver tickets" on storage.objects for select to authenticated
  using (bucket_id = 'tickets' and public.puede_ver_cuenta(split_part(name, '/', 1)));
create policy "subir tickets" on storage.objects for insert to authenticated
  with check (bucket_id = 'tickets' and public.puede_ver_cuenta(split_part(name, '/', 1)));
