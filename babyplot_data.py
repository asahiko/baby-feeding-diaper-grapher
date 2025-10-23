"""Data loading and parsing utilities for babyplot.

This module provides side-effect-free functions to load a raw CSV/XLSX (or sample)
and parse it into structured pandas DataFrames suitable for plotting.
"""
from __future__ import annotations

import datetime
import re
from typing import Dict, Optional

import pandas as pd


def load_raw_df(filename: Optional[str] = None) -> pd.DataFrame:
    """Load raw input file or return sample DataFrame when filename is None.

    Returned DataFrame always has a `date` column converted to datetime.date.
    """
    if filename is None:
        data = {
            "date": ["2025-09-15", "2025-09-16"],
            "breast": ["08:00L15R20 11:30", "07:30L20R15"],
            "pumped": ["09:00-60 14:00-40", "10:00-50"],
            "formula": ["12:30-100 18:30-80", "13:00-120"],
            "urine": ["07:00 10:00 15:30", "08:00 12:00"],
            "stool": ["09:00 13:00△", "09:30× 16:00"],
            "weight": [4.5, 4.7],
        }
        df = pd.DataFrame(data)
    else:
        if filename.endswith(".csv"):
            df = pd.read_csv(filename)
        elif filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(filename)
        else:
            raise ValueError("対応しているのはCSVかExcelファイルのみです")

    # Normalize date column
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def parse_time(s: Optional[str]) -> Optional[datetime.time]:
    """Parse time token like '9', '9:00' into datetime.time.

    If only hour given (e.g. '9'), return time at 9:30 as legacy behavior.
    Returns None when input is falsy or cannot be parsed.
    """
    if not s:
        return None
    s = str(s).strip()
    if not s:
        return None
    # bare hour like '9' -> 9:30
    if re.fullmatch(r"\d{1,2}", s):
        h = int(s)
        if 0 <= h <= 23:
            return datetime.time(h, 30)
        return None
    try:
        return datetime.datetime.strptime(s, "%H:%M").time()
    except Exception:
        return None


def _parse_breast_token(token: str):
    """Parse breast token e.g. '08:00L15R20' or '08:00 15' etc.

    Returns (time, total_minutes, note)
    """
    token = token.strip()
    if not token:
        return None, None, None
    # time at start
    m = re.match(r"^(\d{1,2}(?::\d{2})?)(.*)$", token)
    if not m:
        return None, None, None
    t = parse_time(m.group(1))
    rest = m.group(2).strip()
    total = None
    note = None
    # try to extract Lxx and Ryy or numbers
    if rest:
        # find numbers after L or R
        parts = re.findall(r"[LR]?(\d{1,3})", rest)
        if parts:
            try:
                total = sum(int(p) for p in parts)
            except Exception:
                total = None
        else:
            note = rest
    return t, total, note


def _parse_diaper_token(token: str):
    """Parse diaper token like '9', '9:00', '9△' etc.

    Returns (time, note)
    """
    token = token.strip()
    if not token:
        return None, None
    m = re.match(r"^(\d{1,2}(?::\d{2})?)(.*)$", token)
    if not m:
        return None, None
    t = parse_time(m.group(1))
    note = m.group(2).strip() if m.group(2).strip() else None
    return t, note


def parse_records(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Parse raw dataframe into structured DataFrames.

    Returns dict with keys: breast, pumped, formula, urine, stool, count, weight
    Each value is a pandas.DataFrame (may be empty).
    """
    breast_records = []
    pumped_records = []
    formula_records = []
    urine_records = []
    stool_records = []
    count_records = []
    weight_records = []

    # iterate rows safely
    for row in df.itertuples(index=False):
        # access by attribute name if present
        try:
            date = getattr(row, 'date')
        except Exception:
            # skip rows without date
            continue

        # breast
        if hasattr(row, 'breast') and pd.notna(getattr(row, 'breast', None)):
            for token in str(getattr(row, 'breast')).split():
                t, length, note = _parse_breast_token(token)
                if t:
                    breast_records.append({'date': date, 'time': t, 'length': length, 'note': note})

        # pumped
        if hasattr(row, 'pumped') and pd.notna(getattr(row, 'pumped', None)):
            for token in str(getattr(row, 'pumped')).split():
                m = re.match(r"^(\d{1,2}(?::\d{2})?)-?(\d{1,4})$", token)
                if m:
                    t = parse_time(m.group(1))
                    try:
                        amt = int(m.group(2))
                    except Exception:
                        amt = None
                    if t and amt is not None:
                        pumped_records.append({'date': date, 'time': t, 'amount': amt})

        # formula
        if hasattr(row, 'formula') and pd.notna(getattr(row, 'formula', None)):
            for token in str(getattr(row, 'formula')).split():
                m = re.match(r"^(\d{1,2}(?::\d{2})?)-?(\d{1,4})$", token)
                if m:
                    t = parse_time(m.group(1))
                    try:
                        amt = int(m.group(2))
                    except Exception:
                        amt = None
                    if t and amt is not None:
                        formula_records.append({'date': date, 'time': t, 'amount': amt})

        # urine
        if hasattr(row, 'urine') and pd.notna(getattr(row, 'urine', None)):
            for token in str(getattr(row, 'urine')).split():
                t, note = _parse_diaper_token(token)
                if t:
                    urine_records.append({'date': date, 'time': t, 'note': note})

        # stool
        if hasattr(row, 'stool') and pd.notna(getattr(row, 'stool', None)):
            for token in str(getattr(row, 'stool')).split():
                t, note = _parse_diaper_token(token)
                if t:
                    stool_records.append({'date': date, 'time': t, 'note': note})

        # weight
        if hasattr(row, 'weight') and pd.notna(getattr(row, 'weight', None)):
            weight_records.append({'date': date, 'weight': getattr(row, 'weight')})

    # build count_records from parsed events per date
    # collect dates present
    dates = sorted({r['date'] for r in (breast_records + pumped_records + formula_records + urine_records + stool_records)})
    for d in dates:
        br = sum(1 for r in breast_records if r['date'] == d)
        pr = sum(1 for r in pumped_records if r['date'] == d)
        fr = sum(1 for r in formula_records if r['date'] == d)
        ur = sum(1 for r in urine_records if r['date'] == d)
        sr = sum(1 for r in stool_records if r['date'] == d)
        count_records.append({'date': d, 'breast': br, 'pumped': pr, 'formula': fr, 'urine': ur, 'stool': sr})

    return {
        'breast': pd.DataFrame(breast_records),
        'pumped': pd.DataFrame(pumped_records),
        'formula': pd.DataFrame(formula_records),
        'urine': pd.DataFrame(urine_records),
        'stool': pd.DataFrame(stool_records),
        'count': pd.DataFrame(count_records),
        'weight': pd.DataFrame(weight_records),
    }
