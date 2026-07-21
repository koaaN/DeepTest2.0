import unittest

from deeptesting.token_cli import _host_for_country


class TokenCliTests(unittest.TestCase):
    def test_host_for_country_handles_grouped_mapping(self):
        mapping = {
            "CN": "https://uc-client-cn.heytapmobi.com",
            "HU,CZ,PL": "https://uc-client-fr.heytapmobile.com",
            "default": "https://client-uc.heytapmobi.com",
        }
        self.assertEqual(_host_for_country(mapping, "pl"), "https://uc-client-fr.heytapmobile.com")

    def test_host_for_country_falls_back_to_default(self):
        self.assertEqual(
            _host_for_country({"default": "https://client-uc.heytapmobi.com/"}, "ZZ"),
            "https://client-uc.heytapmobi.com",
        )


if __name__ == "__main__":
    unittest.main()
