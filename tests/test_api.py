import unittest

from importador.api import Api


class Cabeceras(unittest.TestCase):
    def test_clave_jwt_va_tambien_en_authorization(self):
        api = Api("https://x.supabase.co/", "eyJabc")
        self.assertEqual(api.base, "https://x.supabase.co/rest/v1/")
        self.assertEqual(api.cabeceras["apikey"], "eyJabc")
        self.assertEqual(api.cabeceras["Authorization"], "Bearer eyJabc")

    def test_clave_nueva_sb_solo_en_apikey(self):
        api = Api("https://x.supabase.co", "sb_secret_abc")
        self.assertEqual(api.cabeceras["apikey"], "sb_secret_abc")
        self.assertNotIn("Authorization", api.cabeceras)


if __name__ == "__main__":
    unittest.main()
