"""Dimension 28 · 大盘环境 — 大盘趋势/涨跌家数/板块异动/大盘事件.

Data sources:
  - ths_api_client.py → THSClient
    • get_macro_liquidity()     — 宏观流动性 (市值/换手/M1/PE/PB/DR007)
    • get_dapan_trend()         — 大盘大小盘走势对比
    • get_market_events()       — 近期大盘事件 (涨跌停数/成交额/指数涨跌)
    • get_market_change_news()  — 盘中板块/股票异动
    • get_dpyd_analysis()       — 大盘异动时间线 (板块/资金)
    • get_hot_blocks()          — 当前热门概念/板块
    • get_trading_date()        — 最新交易日

Provides:
  宏观流动性评分, 大小盘风格, 涨跌家数/涨停跌停统计,
  热门板块, 市场事件时间线, 当日板块异动提醒.
"""
import json
import sys
import os
from datetime import date, timedelta

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

    macro = {}
    dapan_trend = {}
    market_events = []
    hot_blocks = []
    dpyd = []
    market_change = {}
    source_parts = []

    try:
        from ths_api_client import THSClient
        client = THSClient(timeout=10)

        # 1. Macro liquidity indicators
        macro_raw = _safe(lambda: client.get_macro_liquidity(), {})
        if macro_raw:
            score = macro_raw.get("score")
            hs_mv = macro_raw.get("hs_market_value", 0)
            hs_to = macro_raw.get("hs_turnover", 0)
            sh_pe = macro_raw.get("sh_pe")
            sh_pb = macro_raw.get("sh_pb")
            m1 = macro_raw.get("M1")
            dr007 = macro_raw.get("DR007")

            # Interpret score
            if score is not None:
                if score >= 70:
                    liquidity_label = "宽裕"
                elif score >= 40:
                    liquidity_label = "中性"
                else:
                    liquidity_label = "紧张"
            else:
                liquidity_label = "未知"

            macro = {
                "date": macro_raw.get("date", ""),
                "score": score,
                "liquidity_label": liquidity_label,
                "market_value_trillion": round(hs_mv / 1e12, 2) if hs_mv else None,
                "turnover_billion": round(hs_to / 1e9, 2) if hs_to else None,
                "sh_pe": sh_pe,
                "sh_pb": sh_pb,
                "m1": m1,
                "dr007": dr007,
                "info": macro_raw.get("info", ""),
            }
            source_parts.append("ths:macro_liquidity")

        # 2. Large/mid/small cap trend comparison
        trend_raw = _safe(lambda: client.get_dapan_trend(), {})
        if trend_raw and trend_raw.get("data"):
            dapan_trend = {"available": True, "source": "ths:dapan_trend"}
            source_parts.append("ths:dapan_trend")

        # 3. Market events (recent 5 trading days)
        today = date.today()
        start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        events_raw = _safe(lambda: client.get_market_events(start), {})
        if events_raw:
            data_items = events_raw.get("data", {}).get("data", [])
            if data_items:
                market_events = [
                    {
                        "date": ev.get("date", ""),
                        "limit_up": ev.get("limitupNum", 0),
                        "limit_down": ev.get("limitdownNum", 0),
                        "ssec_close_pct": ev.get("ssecCloseGain", 0),
                        "volume": ev.get("volume", 0),
                        "turnover": ev.get("turnover", 0),
                    }
                    for ev in data_items[:5]
                ]
                source_parts.append("ths:market_events")

        # 4. Hot concept blocks
        blocks_raw = _safe(lambda: client.get_hot_blocks(), [])
        if blocks_raw:
            hot_blocks = blocks_raw[:15]
            source_parts.append("ths:hot_blocks")

        # 5. Intraday sector/stock movement analysis
        dpyd_raw = _safe(lambda: client.get_dpyd_analysis(), [])
        if dpyd_raw and isinstance(dpyd_raw, list):
            dpyd = dpyd_raw[:20]  # top 20 events
            source_parts.append("ths:dpyd")

        # 6. Market change news (板块异动)
        change_raw = _safe(lambda: client.get_market_change_news(), {})
        if change_raw and change_raw.get("data"):
            mc_items = change_raw.get("data", [])
            if isinstance(mc_items, list):
                market_change = {
                    "total_events": len(mc_items),
                    "recent": mc_items[:10],
                }
            elif isinstance(mc_items, dict):
                market_change = mc_items
            source_parts.append("ths:market_change")

    except ImportError:
        pass

    # --- Derive market environment summary ---
    if market_events:
        latest = market_events[0]
        ssec_pct = latest.get("ssec_close_pct", 0)
        lu = latest.get("limit_up", 0)
        ld = latest.get("limit_down", 0)

        if ssec_pct > 1:
            index_label = "大涨"
        elif ssec_pct > 0:
            index_label = "小涨"
        elif ssec_pct > -1:
            index_label = "小跌"
        else:
            index_label = "大跌"

        if lu > ld * 3:
            breadth_label = "普涨"
        elif ld > lu * 3:
            breadth_label = "普跌"
        elif lu > ld:
            breadth_label = "涨多跌少"
        else:
            breadth_label = "跌多涨少"

        env_label = f"{index_label} · {breadth_label}"
    else:
        env_label = "数据不足"

    return {
        "ticker": ti.full,
        "data": {
            "macro_liquidity": macro,
            "dapan_trend": dapan_trend,
            "market_events": market_events,
            "market_env_label": env_label,
            "hot_blocks": hot_blocks,
            "dpyd_analysis": dpyd[:10] if isinstance(dpyd, list) else [],
            "market_change": market_change,
        },
        "source": " + ".join(source_parts) if source_parts else "none",
        "fallback": not bool(source_parts),
    }


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "002938"
    print(json.dumps(main(arg), ensure_ascii=False, indent=2, default=str))
