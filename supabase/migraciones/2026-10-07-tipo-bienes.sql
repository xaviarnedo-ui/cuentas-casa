-- Piso y coche como cuentas de Patrimonio: su saldo es un valor estimado que se registra a mano.
alter table cuentas drop constraint cuentas_tipo_check;
alter table cuentas add constraint cuentas_tipo_check
  check (tipo in ('corriente', 'ahorro', 'inversion', 'efectivo', 'deuda', 'inmueble', 'vehiculo'));
