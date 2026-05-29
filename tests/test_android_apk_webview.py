from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_ACTIVITY = ROOT / "android_apk/app/src/main/java/com/medicarepro/app/MainActivity.kt"
MANIFEST = ROOT / "android_apk/app/src/main/AndroidManifest.xml"


def test_android_apk_points_to_current_streamlit_login():
    source = MAIN_ACTIVITY.read_text(encoding="utf-8")

    assert "https://medicare-pro.streamlit.app" not in source
    assert "https://medicare-pro-v2-eyqvgkqwvd9e48r5z6klrf.streamlit.app/?login=1" in source
    assert "webView.loadUrl(APP_URL)" in source


def test_android_apk_webview_keeps_streamlit_runtime_settings():
    source = MAIN_ACTIVITY.read_text(encoding="utf-8")
    manifest = MANIFEST.read_text(encoding="utf-8")

    assert "android.permission.INTERNET" in manifest
    assert 'android:usesCleartextTraffic="false"' in manifest
    assert 'android:allowBackup="false"' in manifest
    assert "javaScriptEnabled = true" in source
    assert "domStorageEnabled = true" in source
    assert "setAcceptCookie(true)" in source
    assert "setAcceptThirdPartyCookies(webView, true)" in source
    assert "loadDataWithBaseURL" in source
