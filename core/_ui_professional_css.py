"""CSS global del tema profesional de Medicare Pro."""

CUSTOM_CSS = """
<style>
    /* Fuentes */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Variables CSS - dark theme */
    :root {
        --primary: #2563EB;
        --primary-dark: #1D4ED8;
        --primary-light: #1e3a5f;
        --secondary: #94a3b8;
        --success: #10B981;
        --warning: #F59E0B;
        --danger: #EF4444;
        --info: #06B6D4;
        --background: #0f172a;
        --surface: rgba(30,41,59,0.7);
        --text-primary: #e2e8f0;
        --text-secondary: #94a3b8;
        --border: rgba(148,163,184,0.15);
        --radius: 8px;
        --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.3);
        --shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.4), 0 1px 2px 0 rgba(0, 0, 0, 0.3);
        --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.4), 0 4px 6px -2px rgba(0, 0, 0, 0.3);
    }

    /* Cards */
    .card {
        background: rgba(30,41,59,0.7);
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
        background: rgba(30,41,59,0.7);
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
        background: rgba(16,185,129,0.15);
        color: #6ee7b7;
    }

    .badge-warning {
        background: rgba(245,158,11,0.15);
        color: #fcd34d;
    }

    .badge-danger {
        background: rgba(239,68,68,0.15);
        color: #fca5a5;
    }

    .badge-info {
        background: rgba(6,182,212,0.15);
        color: #67e8f9;
    }

    .badge-neutral {
        background: rgba(148,163,184,0.15);
        color: #cbd5e1;
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
        background: rgba(16,185,129,0.1);
        border: 1px solid rgba(16,185,129,0.2);
        color: #6ee7b7;
    }

    .alert-warning {
        background: rgba(245,158,11,0.1);
        border: 1px solid rgba(245,158,11,0.2);
        color: #fcd34d;
    }

    .alert-danger {
        background: rgba(239,68,68,0.1);
        border: 1px solid rgba(239,68,68,0.2);
        color: #fca5a5;
    }

    .alert-info {
        background: rgba(37,99,235,0.1);
        border: 1px solid rgba(37,99,235,0.2);
        color: #93c5fd;
    }

    /* Tables */
    .data-table {
        width: 100%;
        border-collapse: collapse;
        background: rgba(30,41,59,0.7);
        border-radius: var(--radius);
        overflow: hidden;
        box-shadow: var(--shadow);
    }

    .data-table th {
        background: rgba(15,23,42,0.6);
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
        background: rgba(255,255,255,0.03);
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
        background: linear-gradient(90deg, rgba(30,41,59,0.5) 25%, rgba(51,65,85,0.5) 50%, rgba(30,41,59,0.5) 75%);
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
    @media (min-width: 768px) {
        header {visibility: hidden;}
    }

    /* Custom scrollbar */
    ::-webkit-scrollbar {
        width: 5px;
        height: 5px;
    }

    ::-webkit-scrollbar-track {
        background: transparent;
    }

    ::-webkit-scrollbar-thumb {
        background: rgba(14,165,233,0.15);
        border-radius: 4px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: rgba(14,165,233,0.3);
    }

    /* Scroll containers */
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
        scrollbar-color: rgba(14,165,233,0.15) transparent;
        -webkit-overflow-scrolling: touch;
    }
    .mc-scroll-block::-webkit-scrollbar { width: 5px; }
    .mc-scroll-block::-webkit-scrollbar-thumb { background: #10B981; border-radius: 4px; }
</style>
"""
