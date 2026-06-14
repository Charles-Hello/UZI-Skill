"""Dimension 23 · 资金博弈 — 超级/大/中/散户四档分钟级资金流.

Data sources:
  - ths_api_realtime.py → THSRealtimeAPI
    • get_capital_flow()       — 分钟级资金流 (超大/大/中/小单)
    • get_capital_flow_daily() — 日级资金流 (近 N 日)
  - ths_api_capital.py → THSCapitalClient
    • get_intraday_moneyflow()     — 分钟级资金分解
    • get_capital_flow_line()      — 分时主力资金线
    • get_realtime_capital_flow()  — 实时资金+板块排名
    • get_main_force_control()     — 主力控盘度
    • get_minute_large_orders()    — 分钟级大单追踪

Provides:
  超大单/大单/中单/小单 分钟级累计 + 净流入, 主力控盘度,
  大单事件 top10, 日级资金趋势, 板块内资金排名.
  与 D12(fetch_capital_flow.py) 的区别:
    D12 = 北向/融资/股东/主力 (宏观面, 来自 akshare)
    D23 = 实时盘中四档资金博弈 (微观面, 来自 THS 逆向 API)
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

    if ti.market != "A":
        return {
            "ticker": ti.full,
            "data": {"_note": "capital game analysis only supports A-share"},
            "source": "skip",
            "fallback": False,
        }

    intraday_flow = {}
    daily_flow = {}
    capital_line = {}
    main_control = {}
    large_orders = {}
    sector_flow = {}
    source_parts = []

    # --- THSRealtimeAPI: intraday + daily capital flow ---
    try:
        from ths_api_realtime import THSRealtimeAPI
        api = THSRealtimeAPI(timeout=10)

        intraday_raw = _safe(lambda: api.get_capital_flow(code, source="ths"), {})
        if intraday_raw and intraday_raw.get("summary"):
            intraday_flow = {
                "date": intraday_raw.get("date", ""),
                "data_points": intraday_raw.get("data_points", 0),
                "summary": intraday_raw.get("summary", {}),
                # Keep only last 30 minutes for compactness
                "last_30_min": intraday_raw.get("data", [])[-30:],
            }
            source_parts.append("ths_realtime:moneyflow")

        daily_raw = _safe(lambda: api.get_capital_flow_daily(code, days=20), {})
        if daily_raw and daily_raw.get("data"):
            daily_flow = {
                "data": daily_raw.get("data", []),
            }
            source_parts.append("em:fflow_daykline")
    except ImportError:
        pass

    # --- THSCapitalClient: detailed capital analysis ---
    try:
        from ths_api_capital import THSCapitalClient
        cap = THSCapitalClient(timeout=10)

        # Realtime capital flow + sector ranking
        sector_raw = _safe(lambda: cap.get_realtime_capital_flow(code), {})
        if sector_raw and sector_raw.get("main_force"):
            sector_flow = {
                "main_force": sector_raw.get("main_force", {}),
                "flow_breakdown": sector_raw.get("flow_breakdown", {}),
                "sector_name": sector_raw.get("sector", {}).get("name", ""),
                "sector_total_flow": sector_raw.get("sector", {}).get("total_flow", 0),
                "sector_stocks": sector_raw.get("sector", {}).get("stocks", [])[:10],
                "market_top_inflow": sector_raw.get("market_top_inflow", [])[:5],
                "market_top_outflow": sector_raw.get("market_top_outflow", [])[:5],
            }
            source_parts.append("ths_capital:realFunds")

        # Capital flow line (minute-level cumulative)
        line_raw = _safe(lambda: cap.get_capital_flow_line(code), {})
        if line_raw and line_raw.get("minutes"):
            capital_line = {
                "main_force_net_wan": line_raw.get("main_force_net", 0),
                "diff": line_raw.get("diff", {}),
                "minute_count": len(line_raw.get("minutes", [])),
                # Last 30 minutes of cumulative data
                "last_30_min": line_raw.get("minutes", [])[-30:],
            }
            source_parts.append("ths_capital:lineFunds")

        # Main force control ratio
        control_raw = _safe(lambda: cap.get_main_force_control(code), {})
        if control_raw and control_raw.get("control_ratio_pct") is not None:
            main_control = {
                "control_ratio_pct": control_raw.get("control_ratio_pct", 0),
                "main_buy_ratio_pct": control_raw.get("main_buy_ratio_pct", 0),
                "super_large_net": control_raw.get("super_large_net", 0),
                "large_net": control_raw.get("large_net", 0),
                "medium_net": control_raw.get("medium_net", 0),
                "small_net": control_raw.get("small_net", 0),
            }
            source_parts.append("ths_capital:control")

        # Minute large orders (top events)
        orders_raw = _safe(lambda: cap.get_minute_large_orders(code), {})
        if orders_raw and orders_raw.get("top_events"):
            large_orders = {
                "date": orders_raw.get("date", ""),
                "total_minutes": len(orders_raw.get("minutes", [])),
                "top_events": orders_raw.get("top_events", [])[:10],
            }
            source_parts.append("ths_capital:large_orders")
    except ImportError:
        pass

    # --- Derive summary labels ---
    summary = intraday_flow.get("summary", {})
    main_net = summary.get("main_net", 0)
    if main_net > 0:
        flow_label = f"主力净流入 {main_net / 1e8:+.2f}亿" if abs(main_net) >= 1e8 else f"主力净流入 {main_net / 1e4:+.1f}万"
    elif main_net < 0:
        flow_label = f"主力净流出 {main_net / 1e8:+.2f}亿" if abs(main_net) >= 1e8 else f"主力净流出 {main_net / 1e4:+.1f}万"
    else:
        flow_label = "主力净流入 0"

    # Daily trend (last 5 days)
    daily_data = daily_flow.get("data", [])
    daily_trend = "—"
    if len(daily_data) >= 3:
        recent_3 = [d.get("main_net", 0) for d in daily_data[-3:]]
        if all(v > 0 for v in recent_3):
            daily_trend = "连续3日净流入"
        elif all(v < 0 for v in recent_3):
            daily_trend = "连续3日净流出"
        else:
            daily_trend = "资金波动"

    return {
        "ticker": ti.full,
        "data": {
            "intraday_flow": intraday_flow,
            "daily_flow": daily_flow,
            "capital_line": capital_line,
            "main_control": main_control,
            "large_orders": large_orders,
            "sector_flow": sector_flow,
            "flow_label": flow_label,
            "daily_trend": daily_trend,
        },
        "source": " + ".join(source_parts) if source_parts else "none",
        "fallback": not bool(source_parts),
    }


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "002938"
    print(json.dumps(main(arg), ensure_ascii=False, indent=2, default=str))
