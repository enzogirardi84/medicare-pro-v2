"""CSS global del tema profesional de Medicare Pro.

Extraído de core/ui_professional.py.
"""

PROFESSIONAL_THEME = {
    "primaryColor": "#2563EB",
    "backgroundColor": "#F8FAFC",
    "secondaryBackgroundColor": "#FFFFFF",
    "textColor": "#1E293B",
    "font": "Inter",
    "baseFontSize": "16px",
}

CUSTOM_CSS = """
<style>
    /* Fuentes */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Variables CSS */
    :root {
        --primary: #2563EB;
        --primary-dark: #1D4ED8;
        --primary-light: #DBEAFE;
        --secondary: #64748B;
        --success: #10B981;
        --warning: #F59E0B;
        --danger: #EF4444;
        --info: #06B6D4;
        --background: #F8FAFC;
        --surface: #FFFFFF;
        --text-primary: #1E293B;
        --text-secondary: #64748B;
        --border: #E2E8F0;
        --radius: 8px;
        --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        --shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
        --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
    }
    
    /* Main container */
    .main .block-container {
        padding: 2rem 3rem;
        max-width: 1400px;
    }
    
    /* Headers */
    h1 {
        color: var(--text-primary);
        font-weight: 700;
        font-size: 2rem;
        margin-bottom: 0.5rem;
    }
    
    h2 {
        color: var(--text-primary);
        font-weight: 600;
        font-size: 1.5rem;
        margin-top: 1.5rem;
        margin-bottom: 0.75rem;
    }
    
    h3 {
        color: var(--text-primary);
        font-weight: 600;
        font-size: 1.25rem;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
    }
    
    /* Cards */
    .card {
        background: var(--surface);
        border-radius: var(--radius);
        padding: 1.5rem;
        box-shadow: var(--shadow);
        border: 1px solid var(--border);
        margin-bottom: 1rem;
        transition: box-shadow 0.2s ease, transform 0.2s ease;
    }
    
    .card:hover {
        box-shadow: var(--shadow-lg);
    }
    
    .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid var(--border);
    }
    
    .card-title {
        font-size: 1.125rem;
        font-weight: 600;
        color: var(--text-primary);
        margin: 0;
    }
    
    /* Metric cards */
    .metric-card {
        background: var(--surface);
        border-radius: var(--radius);
        padding: 1.25rem;
        box-shadow: var(--shadow);
        border-left: 4px solid var(--primary);
        transition: transform 0.2s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: var(--text-primary);
        line-height: 1;
    }
    
    .metric-label {
        font-size: 0.875rem;
        color: var(--text-secondary);
        margin-top: 0.25rem;
    }
    
    .metric-delta {
        font-size: 0.75rem;
        margin-top: 0.5rem;
    }
    
    .metric-delta.positive {
        color: var(--success);
    }
    
    .metric-delta.negative {
        color: var(--danger);
    }
    
    /* Status badges */
    .badge {
        display: inline-flex;
        align-items: center;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 500;
    }
    
    .badge-success {
        background: #D1FAE5;
        color: #065F46;
    }
    
    .badge-warning {
        background: #FEF3C7;
        color: #92400E;
    }
    
    .badge-danger {
        background: #FEE2E2;
        color: #991B1B;
    }
    
    .badge-info {
        background: #CFFAFE;
        color: #155E75;
    }
    
    .badge-neutral {
        background: #F1F5F9;
        color: #475569;
    }
    
    /* =====================================================
       BUTTONS - GREEN THEME - USA data-testid MODERNO
       ===================================================== */

    /* BASE: todos los botones visibles */
    .stButton > button,
    [data-testid="stDownloadButton"] > button,
    [data-testid="stFormSubmitButton"] > button,
    .stButton button {
        opacity: 1 !important;
        visibility: visible !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        min-height: 2.5rem !important;
        font-family: system-ui, -apple-system, sans-serif !important;
    }

    /* PRIMARY - Verde con texto blanco (selector viejo + nuevo Streamlit) */
    .stButton > button[kind="primary"],
    [data-testid="baseButton-primary"],
    [data-testid="stBaseButton-primary"],
    [data-testid="stFormSubmitButton"] > button,
    button[type="submit"] {
        background: linear-gradient(135deg, #10B981 0%, #059669 100%) !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        border: 2px solid #047857 !important;
        font-weight: 700 !important;
        font-size: 0.9rem !important;
        padding: 0.6rem 1.4rem !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 6px -1px rgba(16,185,129,0.4) !important;
        letter-spacing: 0.3px !important;
    }
    .stButton > button[kind="primary"] p,
    .stButton > button[kind="primary"] span,
    [data-testid="baseButton-primary"] p,
    [data-testid="baseButton-primary"] span,
    [data-testid="stBaseButton-primary"] p,
    [data-testid="stBaseButton-primary"] span,
    [data-testid="stFormSubmitButton"] > button p,
    [data-testid="stFormSubmitButton"] > button span,
    button[type="submit"] p,
    button[type="submit"] span {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        font-weight: 700 !important;
    }

    /* SECONDARY - Gris claro con texto oscuro legible */
    .stButton > button[kind="secondary"],
    [data-testid="baseButton-secondary"],
    [data-testid="stBaseButton-secondary"] {
        background: #E2F0E8 !important;
        color: #064E3B !important;
        -webkit-text-fill-color: #064E3B !important;
        border: 2px solid #34D399 !important;
        font-weight: 600 !important;
        font-size: 0.875rem !important;
        padding: 0.5rem 1.1rem !important;
        border-radius: 8px !important;
    }
    .stButton > button[kind="secondary"] p,
    .stButton > button[kind="secondary"] span,
    [data-testid="baseButton-secondary"] p,
    [data-testid="baseButton-secondary"] span,
    [data-testid="stBaseButton-secondary"] p,
    [data-testid="stBaseButton-secondary"] span {
        color: #064E3B !important;
        -webkit-text-fill-color: #064E3B !important;
        font-weight: 600 !important;
        font-size: 0.875rem !important;
    }
    
    /* TERTIARY/Link buttons - GREEN */
    button[kind="tertiary"] {
        color: #10B981 !important;
        background: transparent !important;
        border: 2px solid #10B981 !important;
        font-weight: 600 !important;
        padding: 0.5rem 1rem !important;
        border-radius: 6px !important;
    }
    
    /* DOWNLOAD BUTTON - Verde oscuro con texto blanco */
    [data-testid="stDownloadButton"] > button {
        background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        border: 2px solid #065F46 !important;
        font-weight: 700 !important;
        border-radius: 8px !important;
    }
    [data-testid="stDownloadButton"] > button p,
    [data-testid="stDownloadButton"] > button span {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        font-weight: 700 !important;
    }

    /* CATCH-ALL: cualquier boton que quede sin texto visible */
    .stButton > button p,
    .stButton > button span {
        opacity: 1 !important;
        visibility: visible !important;
        font-weight: 600 !important;
        font-size: 0.875rem !important;
    }

    /* Hover states */
    .stButton > button[kind="primary"]:hover,
    [data-testid="stBaseButton-primary"]:hover {
        background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 8px -1px rgba(16,185,129,0.5) !important;
    }
    .stButton > button[kind="secondary"]:hover,
    [data-testid="stBaseButton-secondary"]:hover {
        background: #c6e8d4 !important;
        border-color: #10B981 !important;
    }

    /* Focus */
    .stButton > button:focus {
        outline: 2px solid #10B981 !important;
        outline-offset: 2px !important;
    }

    /* Sidebar buttons */
    [data-testid="stSidebar"] .stButton > button {
        width: 100% !important;
        margin-bottom: 0.5rem !important;
    }

    /* =====================================================
       SCROLL CONTAINERS INTERNOS
       ===================================================== */
    .mc-scroll-block {
        max-height: 220px;
        overflow-y: auto;
        overflow-x: hidden;
        background: rgba(30,41,59,0.5);
        border: 1px solid rgba(148,163,184,0.3);
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 0.88rem;
        line-height: 1.6;
        color: #cbd5e1;
        white-space: pre-wrap;
        word-break: break-word;
        scrollbar-width: thin;
        scrollbar-color: #10B981 transparent;
        -webkit-overflow-scrolling: touch;
    }
    .mc-scroll-block::-webkit-scrollbar { width: 5px; }
    .mc-scroll-block::-webkit-scrollbar-thumb { background: #10B981; border-radius: 4px; }
    
    /* Tables */
    .data-table {
        width: 100%;
        border-collapse: collapse;
        background: var(--surface);
        border-radius: var(--radius);
        overflow: hidden;
        box-shadow: var(--shadow);
    }
    
    .data-table th {
        background: #F8FAFC;
        padding: 0.75rem 1rem;
        text-align: left;
        font-size: 0.75rem;
        font-weight: 600;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        border-bottom: 1px solid var(--border);
    }
    
    .data-table td {
        padding: 1rem;
        border-bottom: 1px solid var(--border);
        color: var(--text-primary);
        font-size: 0.875rem;
    }
    
    .data-table tr:last-child td {
        border-bottom: none;
    }
    
    .data-table tr:hover {
        background: #F8FAFC;
    }
    
    /* Sidebar */
    .css-1d391kg, .css-163ttbj {
        background: var(--surface);
    }
    
    /* Alerts */
    .alert {
        padding: 1rem 1.25rem;
        border-radius: var(--radius);
        margin-bottom: 1rem;
        display: flex;
        align-items: flex-start;
        gap: 0.75rem;
    }
    
    .alert-success {
        background: #D1FAE5;
        border: 1px solid #A7F3D0;
        color: #065F46;
    }
    
    .alert-warning {
        background: #FEF3C7;
        border: 1px solid #FDE68A;
        color: #92400E;
    }
    
    .alert-danger {
        background: #FEE2E2;
        border: 1px solid #FECACA;
        color: #991B1B;
    }
    
    .alert-info {
        background: #DBEAFE;
        border: 1px solid #BFDBFE;
        color: #1E40AF;
    }
    
    /* Forms */
    .stTextInput > div > div > input {
        border-radius: var(--radius);
        border: 1px solid var(--border);
        padding: 0.625rem 0.875rem;
        font-size: 0.875rem;
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: var(--primary);
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
    }
    
    /* Select boxes */
    .stSelectbox > div > div > div {
        border-radius: var(--radius);
        border: 1px solid var(--border);
    }
    
    /* Progress bar */
    .stProgress > div > div > div > div {
        background: var(--primary);
    }
    
    /* Spinner */
    .stSpinner > div {
        border-color: var(--primary) transparent transparent transparent;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        border-bottom: 1px solid var(--border);
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 0.75rem 1.25rem;
        font-weight: 500;
        color: var(--text-secondary);
        border-bottom: 2px solid transparent;
    }
    
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: var(--primary);
        border-bottom-color: var(--primary);
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        font-weight: 500;
        color: var(--text-primary);
    }
    
    /* Tooltips */
    [data-testid="stTooltipIcon"] {
        color: var(--text-secondary);
    }
    
    /* Dividers */
    hr {
        border: none;
        border-top: 1px solid var(--border);
        margin: 1.5rem 0;
    }
    
    /* Avatar */
    .avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: linear-gradient(135deg, var(--primary), var(--primary-dark));
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: 600;
        font-size: 0.875rem;
    }
    
    /* Animations */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .animate-fade-in {
        animation: fadeIn 0.3s ease-out;
    }
    
    /* Loading skeleton */
    .skeleton {
        background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
        background-size: 200% 100%;
        animation: loading 1.5s infinite;
        border-radius: var(--radius);
    }
    
    @keyframes loading {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
    }
    
    /* Hide default elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    /* Ocultar header solo en desktop; en móvil el header contiene el botón nativo de sidebar */
    @media (min-width: 768px) {
        header {visibility: hidden;}
    }
    
    /* Custom scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: var(--background);
    }
    
    ::-webkit-scrollbar-thumb {
        background: var(--border);
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: var(--text-secondary);
    }
</style>
"""
