"""
FlightOps Delay Intelligence — Database connection helper.
Reads MySQL credentials from environment variables (or falls back to defaults).

Environment variables:
    FLIGHTOPS_HOST      (default: localhost)
    FLIGHTOPS_PORT      (default: 3306)
    FLIGHTOPS_USER      (default: root)
    FLIGHTOPS_PASSWORD  (default: "")
    FLIGHTOPS_DB        (default: flightops)
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        host = os.getenv("FLIGHTOPS_HOST", "localhost")
        port = os.getenv("FLIGHTOPS_PORT", "3306")
        user = os.getenv("FLIGHTOPS_USER", "root")
        password = os.getenv("FLIGHTOPS_PASSWORD", "")
        db = os.getenv("FLIGHTOPS_DB", "flightops")
        url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}"
        _engine = create_engine(url, pool_pre_ping=True)
    return _engine


def run_query(sql: str, params: dict = None) -> pd.DataFrame:
    """Execute a SQL string and return a pandas DataFrame."""
    with get_engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)
