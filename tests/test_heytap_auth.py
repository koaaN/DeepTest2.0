import unittest

from deeptesting.errors import ProtocolError
from deeptesting.heytap_auth import HeyTapAuthClient
from deeptesting.heytap_models import HeyTapConfig, HeyTapDeviceProfile, LoginChallenge, LoginSession, PrimaryAccountToken


class FakeTransport:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
        self.config = HeyTapConfig()
        self.device = HeyTapDeviceProfile(duid="duid")

    def post(self, path, payload, **kwargs):
        self.calls.append((path, payload, kwargs))
        return next(self.responses)


PRIMARY_RESPONSE = {
    "code": 200,
    "data": {
        "accountToken": {
            "accessToken": "primary-access",
            "idToken": "primary-id",
            "refreshToken": "primary-refresh",
        },
        "primaryToken": "primary-token",
        "refreshTicket": "refresh-ticket",
        "ssoid": "10001",
        "deviceId": "device-id",
        "secondaryTokenMap": {},
    },
}


class HeyTapAuthTests(unittest.TestCase):
    def test_phone_login_sends_sms_and_preserves_process_token(self):
        transport = FakeTransport([
            {"code": 200, "data": {"processToken": "process"}},
            {"code": 200, "data": {"codeLength": 6}},
        ])
        result = HeyTapAuthClient(transport).begin_login("13800000000", "phone", country_calling_code="+86")
        self.assertIsInstance(result, LoginSession)
        self.assertEqual(result.process_token, "process")
        self.assertEqual(transport.calls[1][1], {"processToken": "process", "captchaType": "SMS"})
        self.assertEqual(transport.calls[0][2]["headers"]["X-Validation-Method"], "phone")

    def test_email_login_uses_email_captcha_type(self):
        transport = FakeTransport([
            {"code": 200, "data": {"processToken": "process"}},
            {"code": 200, "data": None},
        ])
        result = HeyTapAuthClient(transport).begin_login("person@example.com", "email")
        self.assertIsInstance(result, LoginSession)
        self.assertEqual(transport.calls[1][1]["captchaType"], "EMAIL")

    def test_captcha_is_returned_as_challenge(self):
        transport = FakeTransport([{
            "code": 101001,
            "error": {"message": "captcha", "errorData": {"captchaHtml": "{}"}},
        }])
        result = HeyTapAuthClient(transport).begin_login("person@example.com", "email")
        self.assertEqual(result, LoginChallenge("captcha", payload="{}", message="captcha"))

    def test_captcha_handler_raw_result_is_retried_as_captcha_code(self):
        captcha_wrapper = '{"dialogSize":{},"html":"<html>captcha</html>"}'
        raw_result = '{"success":true,"provider":"DINGXIANG","result":"{\\"ret\\":0,\\"ticket\\":\\"raw-ticket\\"}"}'
        transport = FakeTransport([
            {
                "code": 101001,
                "error": {"message": "captcha", "errorData": {"captchaHtml": captcha_wrapper}},
            },
            {"code": 200, "data": {"processToken": "process"}},
            {"code": 200, "data": {"codeLength": 6}},
        ])
        handled_html = []
        client = HeyTapAuthClient(
            transport,
            captcha_handler=lambda html: handled_html.append(html) or raw_result,
        )
        result = client.begin_login(
            "person@example.com",
            "email",
            device_token="fixed-device-token",
        )
        self.assertIsInstance(result, LoginSession)
        self.assertEqual(handled_html, ["<html>captcha</html>"])
        first_payload = transport.calls[0][1]
        retry_payload = transport.calls[1][1]
        self.assertIsNone(first_payload["captchaCode"])
        self.assertEqual(retry_payload["captchaCode"], raw_result)
        self.assertEqual(retry_payload["deviceToken"], "fixed-device-token")

    def test_verify_complete_and_exchange_ticket(self):
        transport = FakeTransport([
            {"code": 200, "data": {"ticket": "valid-ticket", "verificationUrl": ""}},
            {"code": 200, "data": {}},
            PRIMARY_RESPONSE,
        ])
        session = LoginSession("person@example.com", "email", "process")
        token = HeyTapAuthClient(transport).verify_code(session, "123456")
        self.assertIsInstance(token, PrimaryAccountToken)
        self.assertEqual(token.access_token, "primary-access")
        self.assertEqual(transport.calls[1][1]["processToken"], "process")
        self.assertEqual(transport.calls[2][1]["ticket"], "valid-ticket")

    def test_verification_url_stops_before_completion(self):
        transport = FakeTransport([{
            "code": 200,
            "data": {"ticket": "partial", "verificationUrl": "https://verify.example"},
        }])
        result = HeyTapAuthClient(transport).verify_code(LoginSession("a", "email", "p"), "1")
        self.assertEqual(result.kind, "verification")
        self.assertEqual(len(transport.calls), 1)

    def test_login_response_requires_secondary_token_map(self):
        response = {"code": 200, "data": dict(PRIMARY_RESPONSE["data"])}
        del response["data"]["secondaryTokenMap"]
        with self.assertRaises(ProtocolError):
            HeyTapAuthClient(FakeTransport([response])).exchange_ticket(LoginSession("a", "email", "p"), "t")

    def test_biz_auth_maps_v3_access_token(self):
        primary = PrimaryAccountToken.from_login_response(PRIMARY_RESPONSE["data"])
        transport = FakeTransport([{
            "code": 200,
            "data": {
                "deviceId": "device-id",
                "v3BizTokenResp": {
                    "accessToken": "business-access",
                    "idToken": "business-id",
                    "refreshToken": "business-refresh",
                },
            },
        }])
        token = HeyTapAuthClient(transport).biz_auth(primary)
        self.assertEqual(token.access_token, "business-access")
        self.assertEqual(token.device_id, "device-id")
        self.assertEqual(transport.calls[0][2]["access_token"], "primary-access")
        self.assertEqual(transport.calls[0][2]["id_token"], "primary-id")

    def test_primary_refresh_preserves_account_state(self):
        primary = PrimaryAccountToken.from_login_response(PRIMARY_RESPONSE["data"])
        transport = FakeTransport([{
            "code": 200,
            "data": {
                "deviceId": "new-device-id",
                "secondaryTokenMap": {"pkg": "secondary"},
                "v3TokenResp": {
                    "accessToken": "new-access",
                    "idToken": "new-id",
                    "refreshToken": "new-refresh",
                },
            },
        }])
        token = HeyTapAuthClient(transport).refresh_primary(primary)
        self.assertEqual(token.access_token, "new-access")
        self.assertEqual(token.primary_token, "primary-token")
        self.assertEqual(token.device_id, "new-device-id")
        headers = transport.calls[0][2]["headers"]
        self.assertEqual(headers["X-AcRefreshToken"], "primary-refresh")
        self.assertEqual(headers["X-AcRefreshTicket"], "refresh-ticket")


if __name__ == "__main__":
    unittest.main()
