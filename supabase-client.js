/* Cuentas de casa — cliente Supabase. La clave pública lo es por diseño: protege RLS. */
(function () {
  "use strict";
  var SUPABASE_URL = "https://laqwymoxwegemdjlqqya.supabase.co";
  var SUPABASE_CLAVE_PUBLICA = "sb_publishable_pegqesc0ZQEwn1c_-wxbAQ_hkHhfVU7";            
  window.CUENTAS_DB = window.supabase.createClient(SUPABASE_URL, SUPABASE_CLAVE_PUBLICA);
})();
