"""Entry point for Streamlit Cloud - Medicare Billing Pro."""
import sys
from pathlib import Path

# Add medicare_billing_pro to path
billing_path = Path(__file__).resolve().parent / "medicare_billing_pro"
if str(billing_path) not in sys.path:
    sys.path.insert(0, str(billing_path))

# Import and run the billing app (billing_app.py evita conflicto con este main.py)
import billing_app