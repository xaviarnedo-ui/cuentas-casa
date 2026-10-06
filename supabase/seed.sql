-- Cuentas de casa — datos iniciales. Ejecutar después de schema.sql.

insert into categorias (id, nombre, icono, cuenta_como_gasto, orden) values
  ('super', 'Súper', '🛒', true, 1),
  ('casa', 'Casa', '🏠', true, 2),
  ('restaurantes', 'Restaurantes', '🍽️', true, 3),
  ('ocio', 'Ocio', '🎉', true, 4),
  ('transporte', 'Transporte', '🚗', true, 5),
  ('salud', 'Salud', '💊', true, 6),
  ('compras', 'Compras', '🛍️', true, 7),
  ('suscripciones', 'Suscripciones', '📺', true, 8),
  ('viajes', 'Viajes', '✈️', true, 9),
  ('formacion', 'Formación', '📚', true, 10),
  ('entrenamiento', 'Entrenamiento', '🏃', true, 10),
  ('otros', 'Otros', '📦', true, 11),
  ('ingresos', 'Ingresos', '💶', false, 12),
  ('ahorro-inversion', 'Ahorro e inversión', '📈', false, 12),
  ('transferencias', 'Transferencias / Aportaciones', '🔁', false, 13);

insert into cuentas (id, nombre, banco, tipo, owner, iban_final, orden) values
  ('comun', 'Común', 'Revolut', 'corriente', null, '3805', 1);

insert into reglas (patron, categoria_id) values
  ('mercadona', 'super'), ('lidl', 'super'), ('carrefour', 'super'), ('eroski', 'super'),
  ('aldi', 'super'), ('netflix', 'suscripciones'), ('spotify', 'suscripciones'),
  ('hbo', 'suscripciones'), ('disney', 'suscripciones'), ('galp', 'transporte'),
  ('repsol', 'transporte'), ('cepsa', 'transporte'), ('farmacia', 'salud'),
  ('ikea', 'casa'), ('decathlon', 'compras'), ('h&m', 'compras'), ('zara', 'compras'),
  ('primor', 'compras'), ('müller', 'compras'), ('burger king', 'restaurantes'),
  ('mcdonald', 'restaurantes');
