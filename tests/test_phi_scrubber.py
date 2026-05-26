from core.phi_scrubber import scrub_phi


def test_scrub_phi_dni():
    r = scrub_phi("Paciente Juan Perez DNI: 12345678")
    assert "OFUSCADO" in r
    assert "12345678" not in r


def test_scrub_phi_email():
    r = scrub_phi("Email: test@example.com")
    assert "OFUSCADO" in r
    assert "test@example.com" not in r


def test_scrub_phi_telefono():
    r = scrub_phi("Telefono: 1155551234")
    assert "OFUSCADO" in r
    assert "1155551234" not in r


def test_scrub_phi_direccion():
    r = scrub_phi("Calle San Martin 1234")
    assert "OFUSCADO" in r


def test_scrub_phi_cuit():
    r = scrub_phi("CUIT: 20-12345678-9")
    assert "OFUSCADO" in r


def test_scrub_phi_normal():
    assert scrub_phi("texto normal sin datos") == "texto normal sin datos"


def test_scrub_phi_vacio():
    assert scrub_phi("") == ""
    assert scrub_phi(None) is None
