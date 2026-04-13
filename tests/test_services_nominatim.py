from unittest.mock import MagicMock, patch

from services.nominatim import reverse_geocode_short_label


@patch("services.nominatim.urllib.request.urlopen")
def test_reverse_geocode_acorta_display_name(mock_open):
    mock_resp = MagicMock()
    mock_resp.read.return_value = (
        b'{"display_name": "A, B, C, D, E, F"}'
    )
    mock_resp.__enter__.return_value = mock_resp
    mock_open.return_value = mock_resp

    out = reverse_geocode_short_label(-34.6, -58.4)
    assert out == "A, B, C"


def test_reverse_geocode_error_devuelve_fallback():
    with patch("services.nominatim.urllib.request.urlopen", side_effect=OSError("net")):
        out = reverse_geocode_short_label(0, 0)
    assert "no disponible" in out.lower()
