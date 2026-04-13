import unittest
from unittest.mock import patch


class TestBloqueEstadoVacio(unittest.TestCase):
    @patch("core.view_helpers.st.markdown")
    def test_escapa_html_en_texto(self, mock_md):
        from core.view_helpers import bloque_estado_vacio

        bloque_estado_vacio("Titulo", 'Texto <b>x</b>', sugerencia="Y & Z")
        html = mock_md.call_args[0][0]
        self.assertIn("&lt;b&gt;", html)
        self.assertIn("&amp;", html)
        self.assertNotIn("<b>x</b>", html)
        self.assertIn("mc-empty-state--compact", html)

    @patch("core.view_helpers.st.markdown")
    def test_modo_relajado_usa_clase(self, mock_md):
        from core.view_helpers import bloque_estado_vacio

        bloque_estado_vacio("A", "B", compact=False)
        html = mock_md.call_args[0][0]
        self.assertIn("mc-empty-state--relaxed", html)
        self.assertNotIn("mc-empty-state--compact", html)


if __name__ == "__main__":
    unittest.main()
