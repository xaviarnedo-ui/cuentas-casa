-- Prueba de privacidad entre Xavi y Andrea. Ejecutar entero en el SQL Editor.
-- RESULTADO ESPERADO: un error que empieza por "RLS_OK". Es intencionado: así se
-- deshacen los datos de prueba.
-- Si sale CUALQUIER cosa distinta de un error "RLS_OK: ...", hay un problema.
do $$
declare
  xavi uuid := (select id from profiles where nombre = 'Xavi');
  andrea uuid := (select id from profiles where nombre = 'Andrea');
  yo uuid; otro uuid; cuenta_otro text; cuenta_propia text; manual_otro text; manual_propio text;
  n int;
begin
  if xavi is null or andrea is null then
    raise exception 'FALLO: faltan los perfiles de Xavi y Andrea (ejecuta perfiles.sql)';
  end if;

  -- Datos de prueba, como administrador
  insert into cuentas (id, nombre, banco, tipo, owner) values
    ('test-xavi', 'Test Xavi', 'test', 'corriente', xavi),
    ('test-andrea', 'Test Andrea', 'test', 'corriente', andrea);
  insert into movimientos (cuenta_id, fecha, importe_cent, comercio, origen, huella) values
    ('test-xavi', '2026-09-01', -100, 'PRIVADO XAVI', 'import', 'test-1'),
    ('test-andrea', '2026-09-01', -100, 'PRIVADO ANDREA', 'import', 'test-2'),
    ('comun', '2026-09-01', -100, 'COMPARTIDO', 'import', 'test-3');
  insert into movimientos (cuenta_id, fecha, importe_cent, comercio, origen, huella, creado_por) values
    ('comun', '2026-09-01', -100, 'MANUAL', 'manual', 'test-manual-xavi', xavi),
    ('comun', '2026-09-01', -100, 'MANUAL', 'manual', 'test-manual-andrea', andrea);
  insert into saldos values ('test-xavi', '2026-09-01', 1), ('test-andrea', '2026-09-01', 1);
  insert into reglas (patron, categoria_id, owner) values
    ('test-xavi', 'otros', xavi), ('test-andrea', 'otros', andrea);
  insert into categorias (id, nombre, icono, owner) values
    ('test-cat-xavi', 'T', 'x', xavi), ('test-cat-andrea', 'T', 'x', andrea);
  -- Solo las filas de metadatos (sin fichero): bastan para probar las políticas de Storage.
  insert into storage.objects (bucket_id, name) values
    ('tickets', 'test-xavi/t.jpg'), ('tickets', 'test-andrea/t.jpg'), ('tickets', 'comun/t.jpg');

  perform set_config('role', 'authenticated', true);

  for i in 1..2 loop
    if i = 1 then
      yo := xavi; otro := andrea; cuenta_otro := 'test-andrea'; cuenta_propia := 'test-xavi';
      manual_otro := 'test-manual-andrea'; manual_propio := 'test-manual-xavi';
    else
      yo := andrea; otro := xavi; cuenta_otro := 'test-xavi'; cuenta_propia := 'test-andrea';
      manual_otro := 'test-manual-xavi'; manual_propio := 'test-manual-andrea';
    end if;
    perform set_config('request.jwt.claims',
      json_build_object('sub', yo, 'role', 'authenticated')::text, true);

    -- Lo propio y lo compartido SÍ se ve (si no, las pruebas negativas no demostrarían nada)
    select count(*) into n from cuentas where id = cuenta_propia;
    if n <> 1 then raise exception 'FALLO: % no ve su propia cuenta', yo; end if;
    select count(*) into n from movimientos where cuenta_id = cuenta_propia;
    if n <> 1 then raise exception 'FALLO: % no ve su propio movimiento', yo; end if;
    select count(*) into n from saldos where cuenta_id = cuenta_propia;
    if n <> 1 then raise exception 'FALLO: % no ve su propio saldo', yo; end if;
    select count(*) into n from reglas where owner = yo and patron like 'test-%';
    if n <> 1 then raise exception 'FALLO: % no ve su propia regla', yo; end if;
    select count(*) into n from categorias where owner = yo and id like 'test-cat-%';
    if n <> 1 then raise exception 'FALLO: % no ve su propia categoría', yo; end if;
    select count(*) into n from storage.objects where bucket_id = 'tickets' and name = cuenta_propia || '/t.jpg';
    if n <> 1 then raise exception 'FALLO: % no ve sus tickets', yo; end if;
    select count(*) into n from storage.objects where bucket_id = 'tickets' and name = 'comun/t.jpg';
    if n <> 1 then raise exception 'FALLO: % no ve los tickets de la común', yo; end if;

    select count(*) into n from cuentas where id = cuenta_otro;
    if n <> 0 then raise exception 'FALLO: % ve la cuenta privada del otro', yo; end if;
    select count(*) into n from movimientos where cuenta_id = cuenta_otro;
    if n <> 0 then raise exception 'FALLO: % ve movimientos privados del otro', yo; end if;
    select count(*) into n from saldos where cuenta_id = cuenta_otro;
    if n <> 0 then raise exception 'FALLO: % ve saldos privados del otro', yo; end if;
    select count(*) into n from reglas where owner = otro;
    if n <> 0 then raise exception 'FALLO: % ve reglas privadas del otro', yo; end if;
    select count(*) into n from categorias where owner = otro;
    if n <> 0 then raise exception 'FALLO: % ve categorías privadas del otro', yo; end if;
    select count(*) into n from storage.objects where bucket_id = 'tickets' and name = cuenta_otro || '/t.jpg';
    if n <> 0 then raise exception 'FALLO: % ve tickets privados del otro', yo; end if;
    begin
      insert into storage.objects (bucket_id, name) values ('tickets', cuenta_otro || '/hack.jpg');
      raise exception 'FALLO: % puede subir tickets a la cuenta del otro', yo;
    exception when insufficient_privilege then null;
    end;
    -- Subir a lo propio y a la común SÍ debe poder (si no, la prueba negativa no demuestra nada)
    insert into storage.objects (bucket_id, name) values ('tickets', cuenta_propia || '/ok.jpg');
    insert into storage.objects (bucket_id, name) values ('tickets', 'comun/ok-' || i || '.jpg');
    select count(*) into n from movimientos where huella = 'test-3';
    if n <> 1 then raise exception 'FALLO: % no ve la cuenta común', yo; end if;

    update movimientos set nota = 'hack' where cuenta_id = cuenta_otro;
    get diagnostics n = row_count;
    if n <> 0 then raise exception 'FALLO: % puede editar movimientos del otro', yo; end if;

    begin
      insert into movimientos (cuenta_id, fecha, importe_cent, comercio, origen)
      values (cuenta_otro, '2026-09-02', -1, 'HACK', 'manual');
      raise exception 'FALLO: % puede apuntar en la cuenta del otro', yo;
    exception when insufficient_privilege then null;
    end;

    begin
      insert into movimientos (cuenta_id, fecha, importe_cent, comercio, origen)
      values ('comun', '2026-09-02', -1, 'HACK', 'import');
      raise exception 'FALLO: % puede crear movimientos "importados"', yo;
    exception when insufficient_privilege then null;
    end;

    begin
      update movimientos set importe_cent = 0 where huella = 'test-3';
      raise exception 'FALLO: % puede cambiar importes', yo;
    exception when insufficient_privilege then null;
    end;

    begin
      insert into movimientos (cuenta_id, fecha, importe_cent, comercio, origen, huella)
      values ('comun', '2026-09-02', -1, 'HACK', 'manual', 'hack');
      raise exception 'FALLO: % puede fijar la huella a mano', yo;
    exception when insufficient_privilege then null;
    end;

    insert into movimientos (cuenta_id, fecha, importe_cent, comercio, origen)
    values ('comun', '2026-09-02', -1, 'TEST-BORRAR', 'manual');
    update movimientos set categoria_id = 'otros', nota = 'ok' where huella = 'test-3';
    get diagnostics n = row_count;
    if n <> 1 then raise exception 'FALLO: % no puede recategorizar la común', yo; end if;
    update movimientos set ticket_path = 'comun/t.jpg' where huella = 'test-3';
    get diagnostics n = row_count;
    if n <> 1 then raise exception 'FALLO: % no puede adjuntar un ticket', yo; end if;

    -- Borrado: solo lo apuntado a mano por uno mismo
    delete from movimientos where huella = 'test-3';
    get diagnostics n = row_count;
    if n <> 0 then raise exception 'FALLO: % puede borrar movimientos importados', yo; end if;
    select count(*) into n from movimientos where huella = manual_otro;
    if n <> 1 then raise exception 'FALLO: % no ve lo apuntado a mano por el otro en la común', yo; end if;
    select count(*) into n from movimientos where huella = manual_propio;
    if n <> 1 then raise exception 'FALLO: % no ve lo que apuntó a mano en la común', yo; end if;
    delete from movimientos where huella = manual_otro;
    get diagnostics n = row_count;
    if n <> 0 then raise exception 'FALLO: % puede borrar lo apuntado a mano por el otro', yo; end if;
    delete from movimientos where comercio = 'TEST-BORRAR' and creado_por = yo;
    get diagnostics n = row_count;
    if n <> 1 then raise exception 'FALLO: % no puede borrar lo que apuntó a mano', yo; end if;

    -- Regla compartida: guardarla dos veces no debe duplicarla (unique nulls not distinct)
    insert into reglas (patron, categoria_id, owner) values ('test-compartida', 'otros', null)
      on conflict (patron, owner) do update set categoria_id = excluded.categoria_id;
    insert into reglas (patron, categoria_id, owner) values ('test-compartida', 'otros', null)
      on conflict (patron, owner) do update set categoria_id = excluded.categoria_id;
    select count(*) into n from reglas where patron = 'test-compartida';
    if n <> 1 then raise exception 'FALLO: la regla compartida se duplicó (% filas)', n; end if;
  end loop;

  -- Alguien con sesión pero sin perfil (no es de casa) no ve nada, ni lo compartido
  perform set_config('request.jwt.claims',
    json_build_object('sub', gen_random_uuid(), 'role', 'authenticated')::text, true);
  select count(*) into n from cuentas where id = 'comun';
  if n <> 0 then raise exception 'FALLO: un extraño ve la cuenta común'; end if;
  select count(*) into n from movimientos where cuenta_id = 'comun';
  if n <> 0 then raise exception 'FALLO: un extraño ve movimientos de la común'; end if;
  select count(*) into n from categorias;
  if n <> 0 then raise exception 'FALLO: un extraño ve las categorías'; end if;
  select count(*) into n from profiles;
  if n <> 0 then raise exception 'FALLO: un extraño ve los perfiles'; end if;

  select count(*) into n from storage.objects where bucket_id = 'tickets';
  if n <> 0 then raise exception 'FALLO: un extraño ve tickets'; end if;

  raise exception 'RLS_OK: todas las comprobaciones pasaron (error intencionado para deshacer los datos de prueba)';
end $$;
