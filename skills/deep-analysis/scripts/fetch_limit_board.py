"""Dimension 24 · 涨停/连板生态 — 涨停列表/连板排行/涨停分钟曲线.

Data sources:
  - ths_api_client.py → THSClient
    • get_limit_up_list()             — 今日涨停股列表
    • get_limit_down_list()           — 今日跌停股列表
    • get_continuous_limit_up()       — 连板股排行
    • get_limit_up_stats()            — 涨跌停分钟走势曲线
    • get_limit_up_history_interval() — 区间涨停统计
    • get_limit_price()               — 个股涨跌停价

Provides:
  今日涨停/跌停列表, 连板排行, 涨停分钟数据, 本股是否涨/跌停,
  市场涨停/跌停总数与情绪温度计, 涨停原因分析.
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
            "data": {"_note": "limit board analysis only supports A-share"},
            "source": "skip",
            "fallback": False,
        }

    limit_up_list = []
    limit_down_list = []
    continuous_list = []
    limit_stats = {}
    limit_price = {}
    this_stock_status = "未涨跌停"
    this_stock_info = {}
    source_parts = []

    try:
        from ths_api_client import THSClient
        client = THSClient(timeout=10)

        # 1. Limit-up list
        lu_raw = _safe(lambda: client.get_limit_up_list(), [])
        if lu_raw:
            limit_up_list = lu_raw[:30]  # top 30
            source_parts.append("ths:limitUp")

            # Check if target stock is in limit-up list
            for item in lu_raw:
                if str(item.get("code", "")) == code:
                    this_stock_status = "涨停"
                    this_stock_info = {
                        "continuous": item.get("continuous", 0),
                        "reason": item.get("reason", ""),
                        "first_limit_up": item.get("firstLimitUp", ""),
                        "last_limit_up": item.get("lastLimitUp", ""),
                        "open_times": item.get("openTimes", 0),
                        "turnover_rate": item.get("turnoverRate", 0),
                    }
                    break

        # 2. Limit-down list
        ld_raw = _safe(lambda: client.get_limit_down_list(), [])
        if ld_raw:
            limit_down_list = ld_raw[:20]
            source_parts.append("ths:limitDown")

            # Check if target stock is in limit-down list
            for item in ld_raw:
                if str(item.get("code", "")) == code:
                    this_stock_status = "跌停"
                    this_stock_info = {
                        "reason": item.get("reason", ""),
                        "open_times": item.get("openTimes", 0),
                        "turnover_rate": item.get("turnoverRate", 0),
                    }
                    break

        # 3. Continuous limit-up (连板)
        cl_raw = _safe(lambda: client.get_continuous_limit_up(), [])
        if cl_raw:
            continuous_list = cl_raw[:20]
            source_parts.append("ths:continuous")

            # Check if target stock is in continuous list
            for item in cl_raw:
                if str(item.get("code", "")) == code and this_stock_status == "涨停":
                    this_stock_info["continuous"] = item.get("continuous", 0)
                    this_stock_info["start_date"] = item.get("startDate", "")
                    this_stock_info["end_date"] = item.get("endDate", "")

        # 4. Limit-up stats timeline (minute-by-minute)
        stats_raw = _safe(lambda: client.get_limit_up_stats(), {})
        if stats_raw and stats_raw.get("data"):
            ts_data = stats_raw.get("data", {})
            time_slots = list(ts_data.items())
            if time_slots:
                first = time_slots[0]
                last = time_slots[-1]
                limit_stats = {
                    "total_time_slots": len(time_slots),
                    "first_slot": {"time": first[0], **first[1]},
                    "last_slot": {"time": last[0], **last[1]},
                    # Sample every 30 minutes
                    "sampled": [
                        {"time": t[0], **t[1]}
                        for i, t in enumerate(time_slots)
                        if i % 30 == 0 or i == len(time_slots) - 1
                    ],
                }
                source_parts.append("ths:fyzzt")

        # 5. Limit price for this stock
        lp_raw = _safe(lambda: client.get_limit_price(code), {})
        if lp_raw and lp_raw.get("data"):
            for item in lp_raw.get("data", []):
                limit_price = {
                    "upper_limit": item.get("upper_price"),
                    "lower_limit": item.get("lower_price"),
                }
                break
            source_parts.append("ths:limitPrice")

    except ImportError:
        pass

    # --- Compute summary ---
    total_limit_up = len(limit_up_list)
    total_limit_down = len(limit_down_list)
    max_continuous = max((item.get("continuous", 0) for item in continuous_list), default=0)

    # Market sentiment gauge
    if total_limit_up > 0 and total_limit_down > 0:
        sentiment_ratio = total_limit_up / (total_limit_up + total_limit_down) * 100
    elif total_limit_up > 0:
        sentiment_ratio = 100.0
    else:
        sentiment_ratio = 0.0

    if sentiment_ratio > 75:
        market_mood = "强势 (涨停远多于跌停)"
    elif sentiment_ratio > 50:
        market_mood = "偏多"
    elif sentiment_ratio > 25:
        market_mood = "偏空"
    else:
        market_mood = "弱势 (跌停远多于涨停)"

    # Top reasons for limit-up
    reasons = {}
    for item in limit_up_list:
        reason = item.get("reason", "")
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1
    top_reasons = sorted(reasons.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "ticker": ti.full,
        "data": {
            "this_stock_status": this_stock_status,
            "this_stock_info": this_stock_info,
            "limit_price": limit_price,
            "total_limit_up": total_limit_up,
            "total_limit_down": total_limit_down,
            "limit_up_list": limit_up_list[:15],
            "limit_down_list": limit_down_list[:10],
            "continuous_leaders": continuous_list[:10],
            "max_continuous_boards": max_continuous,
            "limit_stats": limit_stats,
            "sentiment_ratio": round(sentiment_ratio, 1),
            "market_mood": market_mood,
            "top_reasons": [{"reason": r, "count": c} for r, c in top_reasons],
        },
        "source": " + ".join(source_parts) if source_parts else "none",
        "fallback": not bool(source_parts),
    }


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "002938"
    print(json.dumps(main(arg), ensure_ascii=False, indent=2, default=str))
