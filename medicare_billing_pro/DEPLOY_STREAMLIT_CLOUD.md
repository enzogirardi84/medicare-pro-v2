# Deploy en Streamlit Cloud (share.streamlit.io)

## 1. Conectar repo
1. Andá a https://share.streamlit.io
2. Logueate con tu cuenta de GitHub
3. Hacé clic en **"New app"**
4. Seleccioná el repo: `enzogirardi84/medicare-pro-v2`
5. En **"Main file path"** escribí: `medicare_billing_pro/main.py`
6. Hacé clic en **"Deploy"**

## 2. Configurar Secrets (obligatorio)
1. En el panel de tu app en Streamlit Cloud, andá a **Settings → Secrets**
2. Pegá esto (reemplazá con tus credenciales reales):

```toml
SUPABASE_URL = "https://cvgybjwmkyjtxmbaaimt.supabase.co"
SUPABASE_KEY = "sb_publishable_hfeivzW1BcBKvkZiDI_8vw_N3YnGZR2"
SUPABASE_SERVICE_ROLE_KEY = "TU_SERVICE_ROLE_KEY_AQUI"
```

> **IMPORTANTE:** No subas el `secrets.toml` al repo. Ya está en `.gitignore`.

## 3. Reiniciar la app
Después de guardar los secrets, hacé clic en **"Reboot"** o **"Restart"** en la app.

## 4. Verificar
Una vez que arranque, el panel de estado debe mostrar **"Supabase activo"** en verde.

---

## Notas
- La app usa **SQLite local** como fallback si Supabase no está disponible.
- En Streamlit Cloud, los datos locales son **efímeros** (se borran al reiniciar). Siempre usá Supabase para persistencia real.
- La URL pública de tu app será algo como: `https://medicare-billing-pro-tuusuario.streamlit.app`
