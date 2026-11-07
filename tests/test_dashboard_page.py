"""The dashboard page must not send a JSON content type without a body.

A GET carrying `Content-Type: application/json` and an empty body makes the
server parse the body, fail, and answer 400 to every dashboard request.
"""
import re

from hermes.purple.purple_api import _DASHBOARD_HTML


def test_pedir_so_define_content_type_quando_ha_corpo():
    fonte = re.search(r"function pedir\(url.*?\n}", _DASHBOARD_HTML, re.S).group(0)
    assert "if (opcoes.body)" in fonte, "pedir() tem de condicionar o Content-Type ao corpo"
