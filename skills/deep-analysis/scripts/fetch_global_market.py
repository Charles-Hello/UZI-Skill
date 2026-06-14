"""Dimension 26 · 全球市场联动 — 美股/港股/中概股行情+期权链.

Data sources:
  - ths_api_global.py → GlobalMarketAPI
    • get_us_quotes()           — 美股实时行情 (腾讯/新浪/东财)
    • get_hk_quotes()           — 港股实时行情
    • get_china_adr_quotes()    — 中概股行情
    • get_option_chain()        — ETF期权链
    • get_sector_list()         — A股行业板块涨跌
    • get_etf_quotes()          — 全市场ETF行情
    • get_sector_capital_flow_eastmoney() — 行业资金流排名
  - ths_api_client.py → THSClient
    • get_hk_hot_stocks()       — 港股热门
    • get_us_hot_stocks()       — 美股热门
    • get_comparable_stocks()   — 可比公司 (含港/美)

Provides:
  关联美股/港股标的行情, 中概股整体表现, 行业ETF联动,
  50ETF期权 PCR (put-call ratio), 市场风险偏好.
"""
import json
import sys
import os

_THS_HOOK_DIR = r"C:\Users\a1140\Desktop\ths_hook"
if _THS_HOOK_DIR not in sys.path:
    sys.path.insert(0, _THS_HOOK_DIR)

from lib.market_router import parse_ticker


def _safe(fn, default=None):
    try:
        return fn()
    except Exception as e:
        return default if default is not None else {"error": str(e)}


def main(ticker: str) -> dict:
    ti = parse_ticker(ticker)
    code = ti.code

    us_benchmarks = []
    hk_benchmarks = []
    china_adr = []
    comparable_global = {}
    option_pcr = {}
    sector_flow = []
    source_parts = []

    # --- GlobalMarketAPI ---
    try:
        from ths_api_global import GlobalMarketAPI
        gapi = GlobalMarketAPI(timeout=8)

        # US benchmark stocks
        us_raw = _safe(
            lambda: gapi.get_us_quotes(["NVDA", "AAPL", "TSLA", "BABA", "PDD"]),
            []
        )
        if us_raw:
            us_benchmarks = [
                {
                    "symbol": q.get("symbol", ""),
                    "name": q.get("name", ""),
                    "price": q.get("price"),
                    "change_pct": q.get("change_pct"),
                    "pe": q.get("pe"),
                    "market_cap": q.get("market_cap_usd", q.get("market_cap", 0)),
                }
                for q in us_raw
            ]
            source_parts.append("global:us_quotes")

        # HK benchmark stocks
        hk_raw = _safe(
            lambda: gapi.get_hk_quotes(["00700", "09988", "01024", "03690", "02318"]),
            []
        )
        if hk_raw:
            hk_benchmarks = [
                {
                    "code": q.get("code", ""),
                    "name": q.get("name", ""),
                    "price": q.get("price"),
                    "change_pct": q.get("change_pct"),
                    "pe": q.get("pe"),
                }
                for q in hk_raw
            ]
            source_parts.append("global:hk_quotes")

        # China ADR overview
        adr_raw = _safe(lambda: gapi.get_china_adr_quotes(), [])
        if adr_raw:
            adr_up = sum(1 for q in adr_raw if q.get("change_pct", 0) > 0)
            adr_down = sum(1 for q in adr_raw if q.get("change_pct", 0) < 0)
            adr_avg_chg = (
                sum(q.get("change_pct", 0) for q in adr_raw) / len(adr_raw)
                if adr_raw else 0
            )
            china_adr = {
                "total": len(adr_raw),
                "up_count": adr_up,
                "down_count": adr_down,
                "avg_change_pct": round(adr_avg_chg, 2),
                "top_gainers": sorted(adr_raw, key=lambda x: x.get("change_pct", 0), reverse=True)[:3],
                "top_losers": sorted(adr_raw, key=lambda x: x.get("change_pct", 0))[:3],
            }
            source_parts.append("global:china_adr")

        # 50ETF Option chain PCR (put-call ratio)
        try:
            from datetime import date
            today = date.today()
            month_str = today.strftime("%y%m")
            chain = _safe(lambda: gapi.get_option_chain("510050", month_str), {})
            if chain and (chain.get("call_count", 0) + chain.get("put_count", 0)) > 0:
                call_oi = sum(c.get("open_interest", 0) for c in chain.get("calls", []))
                put_oi = sum(p.get("open_interest", 0) for p in chain.get("puts", []))
                pcr = round(put_oi / call_oi, 3) if call_oi > 0 else 0

                if pcr > 1.2:
                    pcr_label = "看空情绪浓厚 (PCR>1.2)"
                elif pcr > 0.8:
                    pcr_label = "中性"
                else:
                    pcr_label = "看多情绪 (PCR<0.8)"

                option_pcr = {
                    "month": month_str,
                    "call_count": chain.get("call_count", 0),
                    "put_count": chain.get("put_count", 0),
                    "call_oi_total": call_oi,
                    "put_oi_total": put_oi,
                    "pcr": pcr,
                    "pcr_label": pcr_label,
                }
                source_parts.append("global:option_pcr")
        except Exception:
            pass

        # Sector capital flow (top 10 by net inflow)
        sf_raw = _safe(lambda: gapi.get_sector_capital_flow_eastmoney("industry"), [])
        if sf_raw:
            sector_flow = [
                {
                    "name": s.get("name", ""),
                    "change_pct": s.get("change_pct"),
                    "net_inflow": s.get("net_inflow", 0),
                    "net_inflow_pct": s.get("net_inflow_pct"),
                }
                for s in sf_raw[:10]
            ]
            source_parts.append("global:sector_flow")

    except ImportError:
        pass

    # --- THSClient: comparable stocks (global) ---
    try:
        from ths_api_client import THSClient
        client = THSClient(timeout=8)

        comp_raw = _safe(lambda: client.get_comparable_stocks(code), {})
        if comp_raw and comp_raw.get("stockCodes"):
            all_codes = comp_raw.get("stockCodes", [])
            hk_peers = [c for c in all_codes if c.startswith("HK")]
            us_peers = [c for c in all_codes if not c.startswith("HK") and not c[0].isdigit()]
            comparable_global = {
                "industry": comp_raw.get("field", ""),
                "hk_peers": hk_peers[:5],
                "us_peers": us_peers[:5],
                "total_peers": len(all_codes),
            }
            source_parts.append("ths:comparables")
    except ImportError:
        pass

    return {
        "ticker": ti.full,
        "data": {
            "us_benchmarks": us_benchmarks,
            "hk_benchmarks": hk_benchmarks,
            "china_adr": china_adr,
            "comparable_global": comparable_global,
            "option_pcr_50etf": option_pcr,
            "sector_capital_flow_top10": sector_flow,
        },
        "source": " + ".join(source_parts) if source_parts else "none",
        "fallback": not bool(source_parts),
    }


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "002938"
    print(json.dumps(main(arg), ensure_ascii=False, indent=2, default=str))
