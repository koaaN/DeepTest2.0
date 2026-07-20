import unittest

from deeptesting.captcha_handler import CaptchaWebServer


class CaptchaHandlerTests(unittest.TestCase):
    def test_callback_keeps_complete_raw_json(self):
        server = CaptchaWebServer()
        raw = '{"success":true,"provider":"DINGXIANG","result":"{\\"ret\\":0,\\"ticket\\":\\"abc\\"}"}'
        response = server.app.test_client().get("/captcha/callback", query_string={"token": raw})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(server.captcha_token, raw)
        self.assertTrue(server.token_received.is_set())

    def test_html_injects_prompt_callback(self):
        server = CaptchaWebServer()
        server.set_html("<html><head></head><body></body></html>")
        self.assertIn("window.prompt = function", server.html_content)
        self.assertIn("encodeURIComponent(message)", server.html_content)


if __name__ == "__main__":
    unittest.main()
