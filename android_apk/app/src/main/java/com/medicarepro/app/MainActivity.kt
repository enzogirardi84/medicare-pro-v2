package com.medicarepro.app

import android.annotation.SuppressLint
import android.app.ProgressDialog
import android.os.Build
import android.os.Bundle
import android.view.Window
import android.webkit.CookieManager
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {

    companion object {
        private const val APP_URL = "https://medicare-pro-v2-eyqvgkqwvd9e48r5z6klrf.streamlit.app/?login=1"
    }

    private lateinit var webView: WebView
    private var progressDialog: ProgressDialog? = null

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        requestWindowFeature(Window.FEATURE_NO_TITLE)
        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.webView)

        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            javaScriptCanOpenWindowsAutomatically = true
            allowFileAccess = false
            allowContentAccess = false
            cacheMode = WebSettings.LOAD_DEFAULT
            loadWithOverviewMode = false
            useWideViewPort = true
            builtInZoomControls = false
            displayZoomControls = false
            setSupportZoom(false)
            mixedContentMode = WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE
            userAgentString = "$userAgentString MedicareProAndroid"
        }

        CookieManager.getInstance().apply {
            setAcceptCookie(true)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                setAcceptThirdPartyCookies(webView, true)
            }
        }

        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                hideProgress()
                super.onPageFinished(view, url)
            }

            override fun onReceivedError(
                view: WebView?,
                request: WebResourceRequest?,
                error: WebResourceError?
            ) {
                super.onReceivedError(view, request, error)
                if (request?.isForMainFrame == true) {
                    hideProgress()
                    Toast.makeText(
                        this@MainActivity,
                        "No se pudo cargar MediCare. Revisa tu conexion.",
                        Toast.LENGTH_LONG
                    ).show()
                    view?.loadDataWithBaseURL(
                        APP_URL,
                        """
                        <html>
                          <head>
                            <meta name="viewport" content="width=device-width, initial-scale=1">
                            <style>
                              body {
                                margin: 0;
                                min-height: 100vh;
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                background: #0f172a;
                                color: #e2e8f0;
                                font-family: sans-serif;
                                text-align: center;
                                padding: 24px;
                              }
                              a {
                                display: block;
                                margin-top: 16px;
                                padding: 14px 18px;
                                border-radius: 12px;
                                background: #2563eb;
                                color: white;
                                text-decoration: none;
                                font-weight: 700;
                              }
                            </style>
                          </head>
                          <body>
                            <main>
                              <h1>MediCare PRO</h1>
                              <p>No se pudo abrir la aplicacion. Revisa WiFi o datos moviles.</p>
                              <a href="$APP_URL">Reintentar</a>
                            </main>
                          </body>
                        </html>
                        """.trimIndent(),
                        "text/html",
                        "UTF-8",
                        null
                    )
                }
            }
        }

        webView.webChromeClient = object : WebChromeClient() {
            override fun onProgressChanged(view: WebView?, newProgress: Int) {
                if (newProgress < 100) {
                    showProgress()
                } else {
                    hideProgress()
                }
                super.onProgressChanged(view, newProgress)
            }
        }

        webView.loadUrl(APP_URL)
    }

    private fun showProgress() {
        if (progressDialog == null) {
            progressDialog = ProgressDialog(this).apply {
                setMessage("Cargando Medicare Pro...")
                setCancelable(false)
            }
        }
        if (!progressDialog!!.isShowing) {
            progressDialog!!.show()
        }
    }

    private fun hideProgress() {
        progressDialog?.let {
            if (it.isShowing) {
                it.dismiss()
            }
        }
    }

    override fun onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }

    override fun onDestroy() {
        progressDialog?.dismiss()
        webView.destroy()
        super.onDestroy()
    }
}
