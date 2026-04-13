"""Constantes y JSON-LD de SEO (sin ejecutar Streamlit)."""

from core.seo_streamlit import (
    META_DESCRIPTION,
    PAGE_TITLE_PUBLIC,
    canonical_www_apex_hosts,
    resolve_public_site_url,
    schema_software_application,
)


def test_meta_description_long_enough_for_seo():
    assert len(META_DESCRIPTION) >= 80
    assert "MediCare" in META_DESCRIPTION


def test_page_title_includes_product_name():
    assert "MediCare Enterprise PRO" in PAGE_TITLE_PUBLIC


def test_schema_software_application_shape():
    s = schema_software_application()
    assert s["@context"] == "https://schema.org"
    assert s["@type"] == "SoftwareApplication"
    assert s["applicationCategory"] == "HealthApplication"
    assert "description" in s

    with_url = schema_software_application(canonical_url="https://example.com/app")
    assert with_url["url"] == "https://example.com/app"


def test_canonical_www_apex_hosts():
    assert canonical_www_apex_hosts("") is None
    assert canonical_www_apex_hosts("https://sin-www.com") is None
    assert canonical_www_apex_hosts("https://www.ejemplo.com/path") == ("ejemplo.com", "www.ejemplo.com")
    assert canonical_www_apex_hosts("https://WWW.EJEMPLO.COM") == ("ejemplo.com", "www.ejemplo.com")


def test_resolve_public_site_url_from_env(monkeypatch):
    monkeypatch.delenv("APP_CANONICAL_URL", raising=False)
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    monkeypatch.setenv("SITE_URL", "https://app.ejemplo.com/")
    assert resolve_public_site_url() == "https://app.ejemplo.com"
