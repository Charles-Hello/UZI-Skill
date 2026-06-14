"""THS (TongHuaShun) data provider for UZI-Skill deep-analysis framework.

Drop-in provider that bridges reverse-engineered THS local files + HTTP APIs
into the same field-name schema used by data_sources.py.

Data sources:
  - ths_data_bridge.py  (local: 5000+ stocks, industry, stockname)
  - ths_data_parsers.py (local: hd1.0 binary K-line, stockspirit, industry.ini)
  - ths_api_client.py   (HTTP: real-time quote, hot stocks, limit-up, macro, AI picks)

All three live at C:\\Users\\a1140\\Desktop\\ths_hook\\.
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from typing import Optional

# ---------------------------------------------------------------------------
# Import THS tools from ths_hook directory
# ---------------------------------------------------------------------------
_THS_HOOK_DIR = r"C:\Users\a1140\Desktop\ths_hook"
if _THS_HOOK_DIR not in sys.path:
    sys.path.insert(0, _THS_HOOK_DIR)

_bridge = None      # THSDataBridge instance (lazy)
_client = None      # THSClient instance (lazy)
_parsers = None     # ths_data_parsers module ref (lazy)
_import_err = None  # str if import failed

try:
    from ths_data_bridge import THSDataBridge
    from ths_api_client import THSClient
    import ths_data_parsers as _parsers_mod
    _parsers = _parsers_mod
except ImportError as e:
    _import_err = str(e)
    THSDataBridge = None  # type: ignore
    THSClient = None      # type: ignore


def _get_bridge() -> "THSDataBridge | None":
    """Lazy-init the data bridge (no THS process connection needed)."""
    global _bridge
    if _bridge is not None:
        return _bridge
    if THSDataBridge is None:
        return None
    try:
        _bridge = THSDataBridge(connect_ths=False)
        return _bridge
    except Exception:
        return None


def _get_client() -> "THSClient | None":
    """Lazy-init the HTTP API client."""
    global _client
    if _client is not None:
        return _client
    if THSClient is None:
        return None
    try:
        _client = THSClient(timeout=12)
        return _client
    except Exception:
        return None


def _safe_float(v) -> Optional[float]:
    if v is None or v == "" or v == "-":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ===================================================================
# THS root directory for local file access
# ===================================================================
_THS_ROOT = r"C:\同花顺软件\同花顺"


def _day_file_path(code: str) -> Optional[str]:
    """Locate the .day file for a stock code. Returns path or None."""
    code6 = str(code).strip().zfill(6)
    # Determine market directory
    if code6.startswith(("6", "5", "9", "1")):
        market_dir = "shase"
    elif code6.startswith(("0", "2", "3")):
        market_dir = "sznse"
    elif code6.startswith(("8", "4")):
        market_dir = "stb"
    else:
        market_dir = "shase"

    path = os.path.join(_THS_ROOT, "history", market_dir, "day", f"{code6}.day")
    if os.path.exists(path):
        return path

    # Fallback: try index encoding (1A0001 for 000001 index etc.)
    for mdir in ("shase", "sznse", "newindx", "stb", "fxindx"):
        path2 = os.path.join(_THS_ROOT, "history", mdir, "day", f"{code6}.day")
        if os.path.exists(path2):
            return path2

    return None


def _a_share_suffix(code: str) -> str:
    """Determine exchange suffix for a 6-digit A-share code."""
    if code.startswith(("83", "87", "88", "92")):
        return "BJ"
    if code.startswith(("6", "5", "9", "68", "10", "11")):
        return "SH"
    return "SZ"


# ===================================================================
# 1. ths_fetch_basic(ti) -> dict
#    Matches data_sources.fetch_basic() field names
# ===================================================================
def ths_fetch_basic(ti) -> dict:
    """Stock basic info from THS local files + THS API.

    Returns dict with same field names as data_sources.fetch_basic():
      code, name, industry, price, change_pct, market_cap, market_cap_raw,
      pe_ttm, pb, open, prev_close, high, low, ...

    Args:
        ti: TickerInfo object (has .code, .full, .market) or plain str code.
    """
    code = ti.code if hasattr(ti, "code") else str(ti).strip().zfill(6)
    full = ti.full if hasattr(ti, "full") else f"{code}.{_a_share_suffix(code)}"
    out: dict = {"code": full}

    # --- Local data: name, industry ---
    bridge = _get_bridge()
    if bridge is not None:
        try:
            name = bridge.get_stock_name(code)
            if name:
                out["name"] = name
            industry = bridge.get_industry(code)
            if industry:
                out["industry"] = industry
            info = bridge.get_stock_info(code)
            if info:
                out["market_label"] = info.market
        except Exception as e:
            out["_ths_bridge_err"] = str(e)[:120]

    # --- API data: real-time quote ---
    client = _get_client()
    if client is not None:
        # get_quote for price
        try:
            quotes = client.get_quote(code)
            if quotes:
                q = quotes[0]
                out["price"] = q.get("price")
        except Exception as e:
            out["_ths_quote_err"] = str(e)[:120]

        # get_simple_f10 for PE/PB/market_cap
        try:
            f10 = client.get_simple_f10(code)
            if f10 and isinstance(f10, dict):
                data = f10.get("data", f10)
                if isinstance(data, dict):
                    # F10 fields vary; try common keys
                    pe = _safe_float(data.get("pe") or data.get("peTTM"))
                    pb = _safe_float(data.get("pb") or data.get("pbMRQ"))
                    mcap = _safe_float(data.get("total_market_cap") or data.get("totalMarketCap"))
                    if pe is not None:
                        out["pe_ttm"] = round(pe, 2)
                    if pb is not None:
                        out["pb"] = round(pb, 2)
                    if mcap is not None:
                        out["market_cap_raw"] = mcap
                        out["market_cap"] = f"{round(mcap / 1e8, 1)}亿"
                    # Industry from F10 as fallback
                    if not out.get("industry"):
                        ind = data.get("industry") or data.get("hyName")
                        if ind:
                            out["industry"] = ind
        except Exception as e:
            out["_ths_f10_err"] = str(e)[:120]

        # get_basic_info for extra fields
        try:
            basic = client.get_basic_info(code)
            if basic and isinstance(basic, dict):
                bdata = basic.get("data", basic)
                if isinstance(bdata, dict):
                    if not out.get("name"):
                        out["name"] = bdata.get("name") or bdata.get("short_name")
                    if not out.get("industry"):
                        out["industry"] = bdata.get("industry")
        except Exception:
            pass

        # get_stock_popularity for rank info (bonus, not in standard schema)
        try:
            pop = client.get_stock_popularity(code)
            if pop and isinstance(pop, dict):
                out["popularity_rank"] = pop.get("rank")
                out["popularity_rank_total"] = pop.get("rank_amount")
                out["popularity_rank_change"] = pop.get("rank_change")
        except Exception:
            pass

    out["_source"] = "ths_provider"
    return out


# ===================================================================
# 2. ths_fetch_kline(ti, period, start, adjust) -> list[dict]
#    K-line from THS local binary .day files (hd1.0 format)
# ===================================================================
def ths_fetch_kline(ti, period: str = "daily", start: str = "20240101",
                    adjust: str = "qfq") -> list[dict]:
    """K-line data from THS local binary files.

    Parses history/shase/day/*.day or history/sznse/day/*.day in hd1.0 format.

    Returns list of dicts matching UZI-Skill kline format:
      {date, open, high, low, close, volume, amount}

    Note: THS local files are NOT adjusted (no qfq/hfq). The 'adjust' param
    is accepted for interface compatibility but ignored (raw prices returned).
    """
    code = ti.code if hasattr(ti, "code") else str(ti).strip().zfill(6)

    if _parsers is None:
        return [{"_kline_fetch_error": f"ths_data_parsers not available: {_import_err}"}]

    path = _day_file_path(code)
    if path is None:
        return [{"_kline_fetch_error": f"No .day file found for {code}"}]

    try:
        klines = _parsers.parse_day_file(path)
    except Exception as e:
        return [{"_kline_fetch_error": f"parse error: {e}"}]

    if not klines:
        return [{"_kline_fetch_error": f"Empty .day file for {code}"}]

    # Filter by start date
    start_int = int(start) if start else 0
    result = []
    for k in klines:
        date_val = k.get("date")
        if date_val is None:
            continue
        if isinstance(date_val, int) and date_val < start_int:
            continue

        # Format date as YYYY-MM-DD string for consistency with UZI-Skill
        if isinstance(date_val, int):
            ds = str(date_val)
            date_str = f"{ds[:4]}-{ds[4:6]}-{ds[6:8]}"
        else:
            date_str = str(date_val)

        result.append({
            "日期": date_str,
            "开盘": k.get("open"),
            "最高": k.get("high"),
            "最低": k.get("low"),
            "收盘": k.get("close"),
            "成交量": k.get("volume"),
            "成交额": k.get("amount"),
        })

    if not result:
        return [{"_kline_fetch_error": f"No data after start={start} for {code}"}]

    return result


# ===================================================================
# 3. ths_fetch_hot_rank(ti) -> dict
#    From THS API hot_stocks() and popularity_rank()
# ===================================================================
def ths_fetch_hot_rank(ti) -> dict:
    """Hot rank data for a stock from THS APIs.

    Returns:
      rank: int (position in hot list, None if not in top N)
      rank_total: int (total stocks ranked)
      rank_change: int (rank change from yesterday)
      rate: float (heat value)
      hot_list_position: int (position in hot_stocks list, None if absent)
    """
    code = ti.code if hasattr(ti, "code") else str(ti).strip().zfill(6)
    out: dict = {}

    client = _get_client()
    if client is None:
        return out

    # --- Popularity rank ---
    try:
        pop = client.get_stock_popularity(code)
        if pop and isinstance(pop, dict):
            out["rank"] = pop.get("rank")
            out["rank_total"] = pop.get("rank_amount")
            out["rank_change"] = pop.get("rank_change")
    except Exception as e:
        out["_pop_err"] = str(e)[:80]

    # --- Hot stocks list (check if stock is in top 50) ---
    try:
        hot_list = client.get_hot_stocks(limit=100)
        if hot_list:
            for item in hot_list:
                if str(item.get("code", "")).strip() == code:
                    out["hot_list_position"] = item.get("order")
                    out["rate"] = _safe_float(item.get("rate"))
                    out["is_surge"] = item.get("isSurge")
                    out["is_continue"] = item.get("isContinue")
                    break
    except Exception as e:
        out["_hot_err"] = str(e)[:80]

    # --- Popularity rank top 100 (check if stock is in it) ---
    try:
        pop_top = client.get_popularity_rank()
        if pop_top:
            for item in pop_top:
                if str(item.get("code", "")).strip() == code:
                    out["pop_rank_position"] = item.get("rank")
                    out["pop_rank_change"] = item.get("rank_change")
                    break
    except Exception as e:
        out["_pop_top_err"] = str(e)[:80]

    return out


# ===================================================================
# 4. ths_fetch_industry_info(ti) -> dict
#    From THS local industry.ini + stockspirit.ini + API concept_tree()
# ===================================================================
def ths_fetch_industry_info(ti) -> dict:
    """Industry and concept info for a stock.

    Returns:
      industry_name: str (Shenwan L3 industry name)
      industry_code: str (e.g. 881xxx)
      industry_stocks: list[str] (peer stocks in same industry)
      industry_stock_count: int
      concepts: list[dict] (matching concept blocks from API)
      stockspirit_sectors: list[str] (sector names containing this stock)
    """
    code = ti.code if hasattr(ti, "code") else str(ti).strip().zfill(6)
    out: dict = {}

    # --- Local: industry.ini via bridge ---
    bridge = _get_bridge()
    if bridge is not None:
        try:
            industry_name = bridge.get_industry(code)
            if industry_name:
                out["industry_name"] = industry_name
            detail = bridge.get_industry_detail(code)
            if detail:
                out["industry_code"] = detail.code
                out["industry_stocks"] = detail.stocks[:20]  # cap to 20 for brevity
                out["industry_stock_count"] = len(detail.stocks)
        except Exception as e:
            out["_bridge_industry_err"] = str(e)[:80]

    # --- Local: stockspirit.ini (concept/sector name -> code mapping) ---
    if _parsers is not None:
        try:
            spirit = _parsers.parse_stockspirit()
            if spirit:
                # stockspirit maps sector_name -> sector_code
                # We can't directly look up a stock, but we store the full mapping
                # for downstream enrichment
                out["_stockspirit_total_sectors"] = len(spirit)
        except Exception:
            pass

        # Also check industry.ini directly for richer data
        try:
            ind_map = _parsers.parse_industry()
            # Find which industries contain this code
            sectors_for_stock = []
            for ind_code, stocks in ind_map.items():
                if code in stocks:
                    sectors_for_stock.append(ind_code)
            if sectors_for_stock:
                out["member_of_sectors"] = sectors_for_stock
        except Exception:
            pass

    # --- API: concept_fit (matching concepts for this stock) ---
    client = _get_client()
    if client is not None:
        try:
            concepts = client.get_concept_fit(code)
            if concepts:
                out["concepts"] = concepts[:10]  # cap to 10
                out["concept_count"] = len(concepts)
        except Exception as e:
            out["_concept_err"] = str(e)[:80]

        # --- API: comparable stocks ---
        try:
            comp = client.get_comparable_stocks(code)
            if comp and isinstance(comp, dict):
                out["comparable_field"] = comp.get("field")
                out["comparable_stocks"] = comp.get("stockCodes", [])[:10]
        except Exception as e:
            out["_comparable_err"] = str(e)[:80]

    return out


# ===================================================================
# 5. ths_fetch_macro() -> dict
#    From THS API macro_liquidity() (market-wide indicators)
# ===================================================================
def ths_fetch_macro() -> dict:
    """Macro liquidity indicators from THS API.

    Returns:
      date: str (YYYY-MM-DD)
      score: float (overall liquidity score 0-100)
      hs_market_value: float (total A-share market value)
      hs_turnover: float (total turnover)
      M1: float (M1 money supply YoY)
      sh_pe: float (Shanghai PE ratio)
      sh_pb: float (Shanghai PB ratio)
      DR007: float (7-day repo rate)
      info: str (commentary)
    """
    client = _get_client()
    if client is None:
        return {}

    try:
        ml = client.get_macro_liquidity()
        if not ml or not isinstance(ml, dict):
            return {}

        out = {
            "date": ml.get("date"),
            "score": _safe_float(ml.get("score")),
            "hs_market_value": _safe_float(ml.get("hs_market_value")),
            "hs_turnover": _safe_float(ml.get("hs_turnover")),
            "M1": _safe_float(ml.get("M1")),
            "sh_pe": _safe_float(ml.get("sh_pe")),
            "sh_pb": _safe_float(ml.get("sh_pb")),
            "DR007": _safe_float(ml.get("DR007")),
            "info": ml.get("info"),
        }

        # Human-readable formatting
        mv = out.get("hs_market_value")
        if mv:
            out["hs_market_value_display"] = f"{mv / 1e12:.2f}万亿"
        to = out.get("hs_turnover")
        if to:
            out["hs_turnover_display"] = f"{to / 1e9:.2f}十亿"

        return out
    except Exception as e:
        return {"_macro_err": str(e)[:120]}


# ===================================================================
# 6. ths_fetch_limit_stats() -> dict
#    NEW DATA: limit-up/down stats not available in UZI-Skill
# ===================================================================
def ths_fetch_limit_stats() -> dict:
    """Limit-up/down statistics from THS API.

    This is NEW data not available in the original UZI-Skill framework.

    Returns:
      limit_up_list: list[dict] (stocks that hit limit-up today)
      limit_up_count: int
      limit_down_count: int
      continuous_limit_up: list[dict] (stocks with consecutive limit-up streaks)
      minute_counts: dict (intraday limit-up/down timeline)
    """
    client = _get_client()
    if client is None:
        return {}

    out: dict = {}

    # --- Limit-up list ---
    try:
        lu = client.get_limit_up_list()
        if lu:
            out["limit_up_list"] = lu[:30]  # top 30
            out["limit_up_count"] = len(lu)
    except Exception as e:
        out["_lu_err"] = str(e)[:80]

    # --- Limit-down list ---
    try:
        ld = client.get_limit_down_list()
        if ld:
            out["limit_down_list"] = ld[:30]
            out["limit_down_count"] = len(ld)
    except Exception as e:
        out["_ld_err"] = str(e)[:80]

    # --- Continuous limit-up (consecutive board stocks) ---
    try:
        cl = client.get_continuous_limit_up()
        if cl:
            out["continuous_limit_up"] = cl[:20]
            out["continuous_count"] = len(cl)
            # Find max streak — 'continuous' field is a string like "2连板" or "5天3板"
            max_streak = 0
            for item in cl:
                cont_str = str(item.get("continuous", ""))
                # Extract leading digits: "2连板" -> 2, "5天3板" -> 5
                m = re.match(r"(\d+)", cont_str)
                if m:
                    streak = int(m.group(1))
                    if streak > max_streak:
                        max_streak = streak
            out["max_consecutive_boards"] = max_streak if max_streak > 0 else None
    except Exception as e:
        out["_cl_err"] = str(e)[:80]

    # --- Minute-by-minute limit-up/down counts ---
    try:
        stats = client.get_limit_up_stats()
        if stats and isinstance(stats, dict):
            data = stats.get("data", {})
            if data:
                # Summarize: first slot, last slot, total slots
                slots = list(data.items())
                if slots:
                    last_time, last_val = slots[-1]
                    out["minute_counts_latest"] = {
                        "time": last_time,
                        "limit_up_total": last_val.get("zt"),
                        "limit_up_sealed": last_val.get("yzzt"),
                        "limit_up_broken": last_val.get("fyzzt"),
                    }
                    out["minute_counts_slots"] = len(slots)
    except Exception as e:
        out["_stats_err"] = str(e)[:80]

    return out


# ===================================================================
# 7. ths_fetch_ai_analysis(code) -> dict
#    NEW DATA: AI stock picks from THS draw-lots ranking
# ===================================================================
def ths_fetch_ai_analysis(code: str) -> dict:
    """AI-powered stock analysis from THS draw-lots/AI pick ranking.

    This is NEW data not available in the original UZI-Skill framework.

    Args:
        code: 6-digit stock code (e.g. "600000")

    Returns:
      found: bool (whether the stock appears in today's AI picks)
      tab_name: str (theme category if found)
      reason: str (AI reasoning for the pick)
      all_themes: list[str] (all available AI theme categories)
      all_picks: list[dict] (all picks across themes, for context)
    """
    code = str(code).strip().zfill(6)
    client = _get_client()
    if client is None:
        return {}

    try:
        dl = client.get_draw_lots_rank()
        if not dl or not isinstance(dl, dict):
            return {}

        tabs = dl.get("data", {}).get("tab_list", [])
        if not tabs:
            return {}

        out: dict = {
            "found": False,
            "all_themes": [t.get("tab_name", "") for t in tabs],
            "all_picks": [],
        }

        for tab in tabs:
            tab_name = tab.get("tab_name", "")
            picks = tab.get("tab_data", [])
            for pick in picks:
                pick_entry = {
                    "code": pick.get("stock_code", ""),
                    "name": pick.get("stock_name", ""),
                    "reason": pick.get("reason", ""),
                    "theme": tab_name,
                }
                out["all_picks"].append(pick_entry)

                if str(pick.get("stock_code", "")).strip() == code:
                    out["found"] = True
                    out["tab_name"] = tab_name
                    out["reason"] = pick.get("reason", "")
                    out["stock_name"] = pick.get("stock_name", "")

        # Cap all_picks to 30 for output size
        out["all_picks"] = out["all_picks"][:30]
        return out

    except Exception as e:
        return {"_ai_err": str(e)[:120]}


# ===================================================================
# 8. ths_resolve_name(name) -> str
#    From THS local stocknametable.txt fuzzy match
# ===================================================================
def ths_resolve_name(name: str) -> str:
    """Resolve a Chinese stock name to its 6-digit code using THS local data.

    Uses THSDataBridge.search_stocks() for fuzzy matching against the full
    stocknametable.txt + stockname files.

    Args:
        name: Chinese stock name (e.g. "浦发银行", "茅台")

    Returns:
        6-digit stock code (e.g. "600000") or empty string if not found.
    """
    name = name.strip()
    if not name:
        return ""

    bridge = _get_bridge()
    if bridge is None:
        return ""

    try:
        # Exact match first via nametable
        for code, names in bridge._nametable_cache.items():
            for n in names:
                if n == name:
                    return code

        # Search (substring match on name and code)
        results = bridge.search_stocks(name)
        if results:
            # Prefer exact name match
            for s in results:
                if s.name == name:
                    return s.code
            # Otherwise return first result (best substring match)
            return results[0].code

        return ""
    except Exception:
        return ""


# ===================================================================
# Convenience: check availability
# ===================================================================
# ===================================================================
# 9. ths_fetch_financials(ti) -> dict
#    Wraps FinancialClient from ths_api_financials.py
# ===================================================================
_fin_client = None  # FinancialClient (lazy)
_fin_import_err = None

try:
    from ths_api_financials import FinancialClient as _FinancialClient
except ImportError as e:
    _FinancialClient = None
    _fin_import_err = str(e)


def _get_fin_client():
    global _fin_client
    if _fin_client is not None:
        return _fin_client
    if _FinancialClient is None:
        return None
    try:
        _fin_client = _FinancialClient(timeout=20)
        return _fin_client
    except Exception:
        return None


def ths_fetch_financials(ti) -> dict:
    """Financial statements from Eastmoney datacenter (via ths_api_financials).

    Returns dict matching data_sources.fetch_financials() schema:
      {abstract: [...], indicator: [...], balance_sheet: [...],
       income_statement: [...], cashflow: [...], dividend_history: [...]}
    """
    code = ti.code if hasattr(ti, "code") else str(ti).strip().zfill(6)
    market = ti.market if hasattr(ti, "market") else "A"
    fc = _get_fin_client()
    if fc is None:
        return {}

    out: dict = {}
    try:
        if market == "A":
            # Main indicators (ROE, margins, EPS, etc.) -> maps to "indicator"
            indicators = fc.get_main_indicators(code, periods=20)
            if indicators:
                # Flatten to the same shape as akshare's stock_financial_analysis_indicator
                indicator_rows = []
                for r in indicators:
                    indicator_rows.append({
                        "报告期": (r.get("REPORT_DATE") or "")[:10],
                        "类型": r.get("REPORT_TYPE"),
                        "ROE加权": r.get("ROEJQ"),
                        "ROE扣非": r.get("ROEKCJQ"),
                        "毛利率": r.get("XSMLL"),
                        "净利率": r.get("XSJLL"),
                        "基本EPS": r.get("EPSJB"),
                        "每股净资产": r.get("BPS"),
                        "资产负债率": r.get("ZCFZL"),
                        "流动比率": r.get("LD"),
                        "速动比率": r.get("SD"),
                        "每股经营现金流": r.get("MGJYXJJE"),
                        "FCFF": r.get("FCFF_FORWARD"),
                        "营收": r.get("TOTALOPERATEREVE"),
                        "归母净利润": r.get("PARENTNETPROFIT"),
                        "营收同比": r.get("TOTALOPERATEREVETZ"),
                        "净利润同比": r.get("PARENTNETPROFITTZ"),
                    })
                out["indicator"] = indicator_rows

            # Financial summary for abstract-like data
            try:
                summary = fc.get_financial_summary(code, market="a", years=5)
                if summary and summary.get("annual_data"):
                    out["abstract"] = summary["annual_data"]
                if summary and summary.get("dividend_history"):
                    out["dividend_history"] = summary["dividend_history"]
            except Exception:
                pass

            # Balance sheet
            try:
                bs = fc.get_balance_sheet(code, periods=8)
                if bs:
                    out["balance_sheet"] = bs[:8]
            except Exception:
                pass

            # Income statement
            try:
                inc = fc.get_income_statement(code, periods=8)
                if inc:
                    out["income_statement"] = inc[:8]
            except Exception:
                pass

            # Cash flow
            try:
                cf = fc.get_cashflow(code, periods=8)
                if cf:
                    out["cashflow"] = cf[:8]
            except Exception:
                pass

        elif market == "H":
            hk_data = fc.get_hk_main_indicators(code, periods=20)
            if hk_data:
                out["indicator"] = hk_data[:20]
            try:
                summary = fc.get_financial_summary(code, market="hk", years=5)
                if summary and summary.get("annual_data"):
                    out["abstract"] = summary["annual_data"]
            except Exception:
                pass

        elif market == "U":
            us_data = fc.get_us_main_indicators(code, periods=20)
            if us_data:
                out["indicator"] = us_data[:20]
            try:
                summary = fc.get_financial_summary(code, market="us", years=5)
                if summary and summary.get("annual_data"):
                    out["abstract"] = summary["annual_data"]
            except Exception:
                pass

    except Exception as e:
        out["_ths_fin_err"] = f"{type(e).__name__}: {str(e)[:120]}"

    if out.get("indicator") or out.get("abstract"):
        out["_source"] = "ths_financials"
    return out


# ===================================================================
# 10. ths_fetch_news(ti) -> list[dict]
#     Wraps THSExtendedClient for stock-specific news
# ===================================================================
_ext_client = None  # THSExtendedClient (lazy)
_ext_import_err = None

try:
    from ths_api_extended import THSExtendedClient as _THSExtendedClient
except ImportError as e:
    _THSExtendedClient = None
    _ext_import_err = str(e)


def _get_ext_client():
    global _ext_client
    if _ext_client is not None:
        return _ext_client
    if _THSExtendedClient is None:
        return None
    try:
        _ext_client = _THSExtendedClient(timeout=15)
        return _ext_client
    except Exception:
        return None


def ths_fetch_news(ti, limit: int = 30) -> list:
    """Stock-specific news from THS stockpage + basicapi.

    Returns list of dicts matching data_sources.fetch_news() schema:
      [{title, source, publishTime/date, summary, url}, ...]
    """
    code = ti.code if hasattr(ti, "code") else str(ti).strip().zfill(6)
    ext = _get_ext_client()
    if ext is None:
        return []

    results = []
    # Primary: stockpage news API (richer, with summary)
    try:
        news_data = ext.get_stock_news(code)
        news_list = news_data.get("newsList", [])
        for n in news_list[:limit]:
            results.append({
                "新闻标题": n.get("title", ""),
                "新闻内容": n.get("summary", ""),
                "发布时间": n.get("publishTime", ""),
                "文章来源": n.get("source", ""),
                "新闻链接": n.get("jumpUrl", ""),
                "_source": "ths_stockpage",
            })
    except Exception:
        pass

    # Fallback: basicapi news (more items, different format)
    if len(results) < 5:
        try:
            news2 = ext.get_stock_news_basicapi(code, limit=limit)
            items2 = news2.get("data", [])
            existing_titles = {r.get("新闻标题", "") for r in results}
            for n in items2:
                title = n.get("title", "")
                if title and title not in existing_titles:
                    results.append({
                        "新闻标题": title,
                        "新闻内容": "",
                        "发布时间": n.get("date", "") or n.get("time", ""),
                        "文章来源": n.get("source", ""),
                        "新闻链接": n.get("pc_url", "") or n.get("mobile_url", ""),
                        "_source": "ths_basicapi",
                    })
                    existing_titles.add(title)
        except Exception:
            pass

    return results[:limit]


# ===================================================================
# 11. ths_fetch_research(ti) -> list[dict]
#     Wraps THSExtendedClient for research reports
# ===================================================================
def ths_fetch_research(ti, limit: int = 20) -> list:
    """Research reports from THS stockpage API.

    Returns list of dicts matching data_sources.fetch_research_reports() schema.
    """
    code = ti.code if hasattr(ti, "code") else str(ti).strip().zfill(6)
    ext = _get_ext_client()
    if ext is None:
        return []

    try:
        report_data = ext.get_stock_reports(code)
        report_list = report_data.get("reportList", [])
        results = []
        for r in report_list[:limit]:
            results.append({
                "报告标题": r.get("title", ""),
                "机构": r.get("source", ""),
                "作者": r.get("author", ""),
                "发布日期": r.get("publishTime", ""),
                "摘要": r.get("summary", ""),
                "链接": r.get("jumpUrl", ""),
                "_source": "ths_stockpage",
            })
        return results
    except Exception:
        return []


# ===================================================================
# 12. ths_fetch_capital_flow(ti) -> dict
#     Wraps THSCapitalClient + THSRealtimeAPI for capital flow data
# ===================================================================
_cap_client = None  # THSCapitalClient (lazy)
_cap_import_err = None

try:
    from ths_api_capital import THSCapitalClient as _THSCapitalClient
except ImportError as e:
    _THSCapitalClient = None
    _cap_import_err = str(e)


def _get_cap_client():
    global _cap_client
    if _cap_client is not None:
        return _cap_client
    if _THSCapitalClient is None:
        return None
    try:
        _cap_client = _THSCapitalClient(timeout=15)
        return _cap_client
    except Exception:
        return None


_rt_api = None  # THSRealtimeAPI (lazy)
_rt_import_err = None

try:
    from ths_api_realtime import THSRealtimeAPI as _THSRealtimeAPI
except ImportError as e:
    _THSRealtimeAPI = None
    _rt_import_err = str(e)


def _get_rt_api():
    global _rt_api
    if _rt_api is not None:
        return _rt_api
    if _THSRealtimeAPI is None:
        return None
    try:
        _rt_api = _THSRealtimeAPI(timeout=15)
        return _rt_api
    except Exception:
        return None


def ths_fetch_capital_flow(ti) -> dict:
    """Capital flow data from THS APIs (intraday + daily).

    Returns dict with:
      flow_history: list[dict] (daily capital flow, maps to northbound schema)
      intraday_summary: dict (today's super_large/large/medium/small net)
      main_force: dict (main force inflow/outflow/net)
      sector: dict (sector context)
    """
    code = ti.code if hasattr(ti, "code") else str(ti).strip().zfill(6)
    out: dict = {}

    # -- THSCapitalClient: intraday money flow + realtime summary --
    cap = _get_cap_client()
    if cap is not None:
        # Intraday money flow summary
        try:
            mf = cap.get_intraday_moneyflow(code)
            if mf and mf.get("summary"):
                out["intraday_summary"] = mf["summary"]
                out["intraday_date"] = mf.get("date", "")
        except Exception:
            pass

        # Realtime capital flow with sector context
        try:
            rcf = cap.get_realtime_capital_flow(code)
            if rcf:
                out["main_force"] = rcf.get("main_force", {})
                out["flow_breakdown"] = rcf.get("flow_breakdown", {})
                out["sector"] = rcf.get("sector", {})
                out["market_top_inflow"] = rcf.get("market_top_inflow", [])
                out["market_top_outflow"] = rcf.get("market_top_outflow", [])
        except Exception:
            pass

    # -- THSRealtimeAPI: daily capital flow (maps to northbound/flow_history) --
    rt = _get_rt_api()
    if rt is not None:
        try:
            daily = rt.get_capital_flow_daily(code, days=60)
            if daily and daily.get("data"):
                out["flow_history"] = daily["data"]
        except Exception:
            pass

    if out:
        out["_source"] = "ths_capital"
    return out


# ===================================================================
# 13. ths_fetch_concepts(ti) -> list[dict]
#     Wraps THSExtendedClient concept + concept_fit API
# ===================================================================
def ths_fetch_concepts(ti) -> list:
    """Concept/theme blocks for a stock from THS APIs.

    Returns list of dicts: [{name, explain, category, ...}, ...]
    """
    code = ti.code if hasattr(ti, "code") else str(ti).strip().zfill(6)
    ext = _get_ext_client()
    if ext is None:
        return []

    results = []
    # THSExtendedClient.get_stock_concepts (concept blocks with explanations)
    try:
        concepts = ext.get_stock_concepts(code)
        if concepts:
            for c in concepts:
                results.append({
                    "name": c.get("name", ""),
                    "explain": c.get("simple_explain", "") or c.get("explain", ""),
                    "category": c.get("category", ""),
                    "level": c.get("level", ""),
                    "_source": "ths_concept",
                })
    except Exception:
        pass

    # Also try concept_fit from the ths_api_client (if available)
    client = _get_client()
    if client is not None:
        try:
            fit = client.get_concept_fit(code)
            if fit:
                existing_names = {r.get("name", "") for r in results}
                for c in fit:
                    name = c.get("name", "") if isinstance(c, dict) else str(c)
                    if name and name not in existing_names:
                        results.append({
                            "name": name,
                            "explain": c.get("reason", "") if isinstance(c, dict) else "",
                            "category": "concept_fit",
                            "_source": "ths_concept_fit",
                        })
                        existing_names.add(name)
        except Exception:
            pass

    return results


# ===================================================================
# 14. ths_fetch_comparable(ti) -> dict
#     Wraps THSExtendedClient comparable stocks API
# ===================================================================
def ths_fetch_comparable(ti) -> dict:
    """Find comparable/peer stocks via THS AI API.

    Returns dict: {field: str, stocks: list[str], a_shares: list, hk: list, us: list}
    """
    code = ti.code if hasattr(ti, "code") else str(ti).strip().zfill(6)
    ext = _get_ext_client()
    if ext is None:
        return {}

    try:
        comp = ext.get_comparable_stocks(code)
        if not comp:
            return {}
        all_codes = comp.get("stockCodes", [])
        a_shares = [c for c in all_codes if c[0:1].isdigit() and len(c) == 6]
        hk = [c for c in all_codes if c.startswith("HK")]
        us = [c for c in all_codes if not c.startswith("HK") and not (c[0:1].isdigit() and len(c) == 6)]
        return {
            "field": comp.get("field", ""),
            "stocks": all_codes,
            "a_shares": a_shares,
            "hk": hk,
            "us": us,
            "_source": "ths_comparable",
        }
    except Exception:
        return {}


# ===================================================================
# Convenience: check availability
# ===================================================================
def ths_available() -> bool:
    """Return True if THS tools are importable and bridge can initialize."""
    return _import_err is None and _get_bridge() is not None


def ths_status() -> dict:
    """Diagnostic status dict for troubleshooting."""
    return {
        "import_ok": _import_err is None,
        "import_error": _import_err,
        "bridge_ok": _get_bridge() is not None,
        "client_ok": _get_client() is not None,
        "parsers_ok": _parsers is not None,
        "ext_client_ok": _get_ext_client() is not None,
        "fin_client_ok": _get_fin_client() is not None,
        "cap_client_ok": _get_cap_client() is not None,
        "rt_api_ok": _get_rt_api() is not None,
        "ths_root_exists": os.path.isdir(_THS_ROOT),
        "history_dir_exists": os.path.isdir(os.path.join(_THS_ROOT, "history")),
    }
