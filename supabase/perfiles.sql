-- Ejecutar DESPUÉS de crear los dos usuarios en Authentication → Users.
-- Antes de ejecutar, sustituye EMAIL_DE_XAVI por el email con el que se creó el usuario de Xavi.
insert into profiles (id, nombre)
select id, case when email = 'EMAIL_DE_XAVI' then 'Xavi' else 'Andrea' end
from auth.users
on conflict (id) do update set nombre = excluded.nombre;

-- Lo privado de Xavi: su cuenta de efectivo y las categorías del piso alquilado.
insert into cuentas (id, nombre, banco, tipo, owner, orden)
select 'efectivo', 'Efectivo', 'Efectivo', 'efectivo', id, 3 from profiles where nombre = 'Xavi'
on conflict (id) do nothing;

insert into cuentas (id, nombre, banco, tipo, owner, iban_final, orden)
select 'caixabank', 'CaixaBank', 'CaixaBank', 'corriente', id, '5987', 2 from profiles where nombre = 'Xavi'
on conflict (id) do nothing;

insert into cuentas (id, nombre, banco, tipo, owner, orden)
select c.id, c.nombre, c.banco, c.tipo, p.id, c.orden
from (values
  ('myinvestor', 'MyInvestor', 'MyInvestor', 'inversion', 4),
  ('traderepublic', 'Trade Republic', 'Trade Republic', 'inversion', 5),
  ('myaxa', 'MyAXA', 'AXA', 'ahorro', 6)
) as c(id, nombre, banco, tipo, orden)
cross join profiles p
where p.nombre = 'Xavi'
on conflict (id) do nothing;

insert into categorias (id, nombre, icono, cuenta_como_gasto, orden, grupo, owner)
select c.id, c.nombre, c.icono, false, c.orden, 'piso', p.id
from (values
  ('piso-alquiler', 'Piso · Alquiler', '🔑', 20),
  ('piso-luz-gas', 'Piso · Luz y gas', '💡', 21),
  ('piso-agua', 'Piso · Agua', '🚰', 22),
  ('piso-comunidad', 'Piso · Comunidad', '🏢', 23),
  ('piso-ibi', 'Piso · IBI', '🧾', 24),
  ('piso-seguro', 'Piso · Seguro', '🛡️', 25),
  ('piso-reparaciones', 'Piso · Reparaciones', '🔧', 26),
  ('piso-otros', 'Piso · Otros', '📎', 27),
  ('piso-hipoteca', 'Piso · Hipoteca', '🏦', 28)
) as c(id, nombre, icono, orden)
cross join profiles p
where p.nombre = 'Xavi'
on conflict (id) do nothing;

select nombre, count(*) over () as total from profiles;  -- debe salir Xavi y Andrea, total 2
