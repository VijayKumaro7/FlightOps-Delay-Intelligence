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
import streamlit as st
from sqlalchemy import create_engine, text
from config import CACHE_TTL_SECONDS

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        host     = os.getenv("FLIGHTOPS_HOST",     "localhost")
        port     = os.getenv("FLIGHTOPS_PORT",     "3306")
        user     = os.getenv("FLIGHTOPS_USER",     "root")
        password = os.getenv("FLIGHTOPS_PASSWORD", "")
        db       = os.getenv("FLIGHTOPS_DB",       "flightops")
        url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}"
        _engine = create_engine(
            url,
            pool_pre_ping=True,     # Detect stale connections before use
            pool_recycle=3600,      # Recycle connections every hour
            pool_size=5,            # Keep 5 connections warm
            max_overflow=10,        # Allow up to 10 extra connections under load
        )
    return _engine


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def run_query(sql: str, params: dict = None) -> pd.DataFrame:
    """
    Execute a SQL string and return a pandas DataFrame.
    Results are cached for CACHE_TTL_SECONDS (default 5 minutes) to
    avoid re-querying 500K rows on every sidebar interaction.
    """
    try:
        with get_engine().connect() as conn:
            return pd.read_sql(text(sql), conn, params=params)
    except Exception as exc:
        # Surface a readable error; return empty DataFrame so callers don't crash
        st.error(f"Database error: {exc}")
        return pd.DataFrame()
