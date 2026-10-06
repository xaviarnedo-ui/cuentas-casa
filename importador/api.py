"""Cliente mínimo de la API REST de Supabase (PostgREST). Solo librería estándar.
Se usa con la clave de servicio, que se salta RLS: solo vive en el .env del Mac de Xavi."""
import json
import urllib.error
import urllib.parse
import urllib.request


class ApiError(Exception):
    pass


class Api:
    def __init__(self, url, clave):
        self.base = url.rstrip("/") + "/rest/v1/"
        self.cabeceras = {"apikey": clave, "Content-Type": "application/json"}
        if not clave.startswith("sb_"):  # las claves nuevas (sb_secret_…) no son JWT
            self.cabeceras["Authorization"] = "Bearer " + clave

    def _pedir(self, metodo, ruta, cuerpo=None, extra=None):
        datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
        cabeceras = dict(self.cabeceras, **(extra or {}))
        req = urllib.request.Request(self.base + ruta, data=datos, method=metodo, headers=cabeceras)
        try:
            with urllib.request.urlopen(req) as r:
                texto = r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            raise ApiError("%s %s → %s: %s" % (metodo, ruta.split("?")[0], e.code,
                                              e.read().decode("utf-8")))
        return json.loads(texto) if texto else None

    def leer(self, tabla, **filtros):
        """Filtros al estilo PostgREST: leer('movimientos', select='huella', cuenta_id='eq.comun')."""
        return self._pedir("GET", tabla + "?" + urllib.parse.urlencode(filtros))

    def insertar(self, tabla, filas, conflicto=None, al_chocar="ignore"):
        """Todo en una petición = una transacción. al_chocar: 'ignore' deja lo que ya
        existe; 'merge' lo actualiza."""
        ruta = tabla + ("?on_conflict=" + conflicto if conflicto else "")
        prefer = "return=minimal"
        if conflicto:
            prefer += ",resolution=%s-duplicates" % al_chocar
        self._pedir("POST", ruta, filas, {"Prefer": prefer})
