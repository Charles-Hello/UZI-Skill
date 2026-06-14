"""Dimension 22 · 实时盘口深度分析 — 五档盘口委比/委差/量比/内外盘.

Data sources:
  - ths_api_realtime.py → THSRealtimeAPI (primary)
    • get_order_book()        — 五档买卖盘口
    • get_realtime_snapshot() — 委比/委差/量比/内外盘/资金流
  - ths_api_capital.py → THSCapitalClient (supplement)
    • get_orderbook()         — 五档盘口 (fallback)
    • get_realtime_header()   — 实时行情头

Provides:
  买一~买五/卖一~卖五 价格+挂单量, 委比(%), 委差(股), 量比,
  外盘(主动买)vs内盘(主动卖), 内外盘比, 盘口压力方向判断.
"""
import json
import sys
import os

# ---------------------------------------------------------------------------
# Import THS tools
# ---------------------------------------------------------------------------
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
            "data": {"_note": "orderbook analysis only supports A-share"},
            "source": "skip",
            "fallback": False,
        }

    orderbook = {}
    snapshot = {}
    source_used = "none"

    # --- Primary: THSRealtimeAPI ---
    try:
        from ths_api_realtime import THSRealtimeAPI
        api = THSRealtimeAPI(timeout=10)

        ob_raw = _safe(lambda: api.get_order_book(code, source="ths"), {})
        snap_raw = _safe(lambda: api.get_realtime_snapshot(code, source="ths"), {})

        if ob_raw and ob_raw.get("bids"):
            orderbook = ob_raw
            source_used = "ths_realtime"

        if snap_raw and snap_raw.get("price"):
            snapshot = snap_raw
            if source_used == "none":
                source_used = "ths_realtime"
    except ImportError:
        pass

    # --- Fallback: THSCapitalClient ---
    if not orderbook.get("bids"):
        try:
            from ths_api_capital import THSCapitalClient
            cap = THSCapitalClient(timeout=10)
            ob_raw = _safe(lambda: cap.get_orderbook(code), {})
            if ob_raw and ob_raw.get("bids"):
                orderbook = ob_raw
                source_used = "ths_capital"
        except ImportError:
            pass

    # --- Fallback: EM source via THSRealtimeAPI ---
    if not orderbook.get("bids"):
        try:
            from ths_api_realtime import THSRealtimeAPI
            api = THSRealtimeAPI(timeout=10)
            ob_raw = _safe(lambda: api.get_order_book(code, source="em"), {})
            snap_raw2 = _safe(lambda: api.get_realtime_snapshot(code, source="em"), {})
            if ob_raw and ob_raw.get("bids"):
                orderbook = ob_raw
                source_used = "em"
            if snap_raw2 and snap_raw2.get("price") and not snapshot.get("price"):
                snapshot = snap_raw2
        except ImportError:
            pass

    # --- Compute derived metrics ---
    bids = orderbook.get("bids", [])
    asks = orderbook.get("asks", [])

    total_bid_vol = sum(b.get("volume", 0) for b in bids)
    total_ask_vol = sum(a.get("volume", 0) for a in asks)
    weibi = snapshot.get("weibi")
    weicha = snapshot.get("weicha")

    # If snapshot doesn't have weibi, compute from orderbook
    if weibi is None and (total_bid_vol + total_ask_vol) > 0:
        weibi = round((total_bid_vol - total_ask_vol) / (total_bid_vol + total_ask_vol) * 100, 2)
    if weicha is None:
        weicha = total_bid_vol - total_ask_vol

    liangbi = snapshot.get("liangbi")
    outer_vol = snapshot.get("outer_vol", 0)
    inner_vol = snapshot.get("inner_vol", 0)
    outer_inner_ratio = round(outer_vol / inner_vol, 3) if inner_vol > 0 else None

    # Pressure direction
    if weibi is not None:
        if weibi > 30:
            pressure = "买盘占优 (多方控盘)"
        elif weibi < -30:
            pressure = "卖盘占优 (空方压制)"
        else:
            pressure = "买卖平衡"
    else:
        pressure = "数据不足"

    # Capital flow from snapshot
    capital_flow = snapshot.get("capital_flow", {})

    return {
        "ticker": ti.full,
        "data": {
            "bids": bids,
            "asks": asks,
            "total_bid_vol": total_bid_vol,
            "total_ask_vol": total_ask_vol,
            "weibi": weibi,
            "weicha": weicha,
            "liangbi": liangbi,
            "outer_vol": outer_vol,
            "inner_vol": inner_vol,
            "outer_inner_ratio": outer_inner_ratio,
            "pressure_direction": pressure,
            "price": snapshot.get("price"),
            "change_pct": snapshot.get("change_pct"),
            "turnover_rate": snapshot.get("turnover_rate"),
            "amplitude": snapshot.get("amplitude"),
            "pe": snapshot.get("pe"),
            "capital_flow": capital_flow,
            "update_time": snapshot.get("update_time", ""),
        },
        "source": f"ths_hook:{source_used} (orderbook+snapshot)",
        "fallback": False,
    }


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "002938"
    print(json.dumps(main(arg), ensure_ascii=False, indent=2, default=str))
