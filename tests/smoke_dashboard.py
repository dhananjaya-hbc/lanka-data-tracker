"""Render every tab of the dashboard headlessly and fail on any exception.

Needs the dashboard requirements (not part of the stdlib unit tests):
    pip install -r dashboard/requirements.txt && python tests/smoke_dashboard.py
"""

import os
import sys

from streamlit.testing.v1 import AppTest

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dashboard", "app.py")

at = AppTest.from_file(APP, default_timeout=120).run()
problems = [e.message for e in at.exception] + [e.value for e in at.error]
print(f"{len(at.subheader)} sections, {len(at.metric)} metrics, {len(at.dataframe)} tables rendered")
for p in problems:
    print(f"::error::{p}")
sys.exit(1 if problems else 0)
