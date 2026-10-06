-- Permite cuentas de tipo "deuda" (p. ej. prestamo de los padres). Ejecutar una vez en el SQL Editor.
alter table cuentas drop constraint cuentas_tipo_check;
alter table cuentas add constraint cuentas_tipo_check
  check (tipo in ('corriente', 'ahorro', 'inversion', 'efectivo', 'deuda'));
