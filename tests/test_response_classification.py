import importlib.util
import sys
import types
import unittest
from pathlib import Path

# Import api with stub sibling modules to avoid Home Assistant dependency.
base = Path(__file__).resolve().parents[1] / "custom_components" / "pseg_mymeter"
sys.modules["pseg_mymeter"] = types.ModuleType("pseg_mymeter")
sys.modules["pseg_mymeter"].__path__ = [str(base)]
c = types.ModuleType("pseg_mymeter.const")
c.CHART_URL = "https://example.invalid/data"
c.MYMETER_ROOT = "https://example.invalid/"
sys.modules[c.__name__] = c
p = types.ModuleType("pseg_mymeter.parser")
p.ChartDataError = ValueError
p.extract_intervals = lambda _: []
sys.modules[p.__name__] = p
spec = importlib.util.spec_from_file_location("pseg_mymeter.api", base / "api.py")
api = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = api
spec.loader.exec_module(api)

class ResponseTests(unittest.TestCase):
    def test_login_page(self):
        self.assertIs(api.classify_non_json(b'<html><form><input type="password"></form></html>', 'text/html'), api.LoginHtmlResponse)
    def test_security_page(self):
        self.assertIs(api.classify_non_json(b'<html>Cloudflare challenge</html>', 'text/html'), api.SecurityHtmlResponse)
    def test_other_html(self):
        self.assertIs(api.classify_non_json(b'<html>Meter offline</html>', 'text/html'), api.OtherHtmlResponse)
    def test_plain_text(self):
        self.assertIs(api.classify_non_json(b'ERROR', 'text/plain'), api.OtherTextResponse)
    def test_cookie_prefix_not_allowed(self):
        for value in ('Cookie: foo=bar', 'cookie: foo=bar'):
            with self.assertRaises(ValueError): api.validate_cookie_string(value)
    def test_cookie_value_allowed(self):
        self.assertEqual(api.validate_cookie_string('foo=bar; x=y'), 'foo=bar; x=y')

if __name__ == '__main__': unittest.main()
