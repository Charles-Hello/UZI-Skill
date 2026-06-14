"""Dimension 27 · 30项技术指标全集 — MA/EMA/SAR/DMI/CCI/OBV/ATR/WR/BIAS/VCP等.

Data sources:
  - ths_indicators.py → compute_all_indicators()
    30 indicators from local K-line binary files:
    趋势类: MA, EMA, MACD, SAR, DMI, TRIX, BBI
    震荡类: KDJ, RSI, WR, CCI, ROC, MTM, BIAS
    量价类: OBV, VR, ARBR, CR, PSY, EMV
    波动类: BOLL, ATR, STD
    资金/筹码: EXPMA, DMA, MIKE, 筹码集中度
    综合评估: Weinstein Stage, VCP, 趋势强度评分

  与 D2(fetch_kline.py) 的区别:
    D2 = 6个基础指标 (MA/MACD/RSI/筹码/VCP/Stage) via akshare
    D27 = 30个完整指标 via THS本地K线二进制数据, 含背离/交叉/超买超卖信号
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


def _market_dir(code: str) -> str:
    """Determine THS history directory from stock code."""
    if code.startswith(("6", "5", "9")):
        return "shase"
    elif code.startswith(("0", "3")):
        return "szse"
    elif code.startswith(("8", "4")):
        return "bjse"
    return "shase"


def main(ticker: str) -> dict:
    ti = parse_ticker(ticker)
    code = ti.code

    if ti.market != "A":
        return {
            "ticker": ti.full,
            "data": {"_note": "full technicals only supports A-share (local K-line)"},
            "source": "skip",
            "fallback": False,
        }

    indicators = {}
    summary = {}
    source_used = "none"

    # --- Primary: ths_indicators (local K-line) ---
    try:
        from ths_indicators import compute_all_indicators
        market_dir = _market_dir(code)
        result = compute_all_indicators(code, market=market_dir)

        if result and not result.get("error"):
            raw_indicators = result.get("indicators", {})
            indicators = raw_indicators
            source_used = "ths_indicators:local_kline"

            # Compute aggregate signal counts
            buy_count = 0
            sell_count = 0
            neutral_count = 0

            for name, ind in raw_indicators.items():
                signal = ind.get("signal", "")
                if "买入" in signal:
                    buy_count += 1
                elif "卖出" in signal:
                    sell_count += 1
                else:
                    neutral_count += 1

            total = buy_count + sell_count + neutral_count
            if total > 0:
                bull_pct = round(buy_count / total * 100, 0)
            else:
                bull_pct = 50

            if buy_count > sell_count * 2:
                overall = "强烈看多"
            elif buy_count > sell_count:
                overall = "偏多"
            elif sell_count > buy_count * 2:
                overall = "强烈看空"
            elif sell_count > buy_count:
                overall = "偏空"
            else:
                overall = "中性"

            summary = {
                "kline_count": result.get("kline_count", 0),
                "date_range": result.get("date_range", ""),
                "latest_close": result.get("latest_close"),
                "buy_signals": buy_count,
                "sell_signals": sell_count,
                "neutral_signals": neutral_count,
                "bull_pct": bull_pct,
                "overall": overall,
            }
        elif result and result.get("error"):
            indicators = {"error": result["error"]}
    except ImportError as e:
        indicators = {"error": f"ths_indicators import failed: {e}"}

    # --- Fallback: THSCapitalClient MACD/KDJ/RSI/BOLL from HTTP ---
    if source_used == "none":
        try:
            from ths_api_capital import THSCapitalClient
            cap = THSCapitalClient(timeout=10)

            macd = _safe(lambda: cap.compute_macd(code), {})
            kdj = _safe(lambda: cap.compute_kdj(code), {})
            rsi = _safe(lambda: cap.compute_rsi(code), {})
            boll = _safe(lambda: cap.compute_boll(code), {})

            indicators = {
                "MACD": {
                    "name": "MACD",
                    "DIF": macd.get("bars", [{}])[-1].get("dif") if macd.get("bars") else None,
                    "DEA": macd.get("bars", [{}])[-1].get("dea") if macd.get("bars") else None,
                    "MACD": macd.get("bars", [{}])[-1].get("macd_hist") if macd.get("bars") else None,
                    "signal": "from HTTP (limited)",
                },
                "KDJ": {
                    "name": "KDJ",
                    "K": kdj.get("bars", [{}])[-1].get("k") if kdj.get("bars") else None,
                    "D": kdj.get("bars", [{}])[-1].get("d") if kdj.get("bars") else None,
                    "J": kdj.get("bars", [{}])[-1].get("j") if kdj.get("bars") else None,
                    "signal": "from HTTP (limited)",
                },
                "RSI": {
                    "name": "RSI",
                    "values": {"RSI14": rsi.get("bars", [{}])[-1].get("rsi") if rsi.get("bars") else None},
                    "signal": "from HTTP (limited)",
                },
                "BOLL": {
                    "name": "BOLL",
                    "UPPER": boll.get("bars", [{}])[-1].get("upper") if boll.get("bars") else None,
                    "MID": boll.get("bars", [{}])[-1].get("middle") if boll.get("bars") else None,
                    "LOWER": boll.get("bars", [{}])[-1].get("lower") if boll.get("bars") else None,
                    "signal": "from HTTP (limited)",
                },
            }
            summary = {
                "kline_count": len(macd.get("bars", [])),
                "buy_signals": 0,
                "sell_signals": 0,
                "neutral_signals": 4,
                "overall": "HTTP fallback (仅4项指标)",
            }
            source_used = "ths_api_capital:http_compute"
        except ImportError:
            pass

    return {
        "ticker": ti.full,
        "data": {
            "indicators": indicators,
            "summary": summary,
        },
        "source": source_used,
        "fallback": source_used == "none",
    }


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "002938"
    result = main(arg)
    # Print compact: show summary + each indicator's signal only
    data = result.get("data", {})
    summary = data.get("summary", {})
    print(f"=== {result['ticker']} · Full Technicals ===")
    print(f"Source: {result['source']}")
    print(f"K-lines: {summary.get('kline_count', '?')}")
    print(f"Overall: {summary.get('overall', '?')}")
    print(f"Buy: {summary.get('buy_signals', '?')} | Sell: {summary.get('sell_signals', '?')} | Neutral: {summary.get('neutral_signals', '?')}")
    print()
    indicators = data.get("indicators", {})
    if isinstance(indicators, dict) and not indicators.get("error"):
        for name, ind in indicators.items():
            if isinstance(ind, dict):
                signal = ind.get("signal", "N/A")
                print(f"  {name:<12} {signal}")
    elif indicators.get("error"):
        print(f"  ERROR: {indicators['error']}")
    print()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
