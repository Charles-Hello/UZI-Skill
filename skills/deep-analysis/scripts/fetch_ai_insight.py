"""Dimension 25 · AI智能研判 — 同花顺AI选股+AI观点打分.

Data sources:
  - ths_api_client.py → THSClient
    • get_draw_lots_rank()     — AI抽签选股排行 (含 AI 理由)
    • get_stock_popularity()   — 个股人气排名
    • get_hot_stocks()         — 热度排行
  - ths_api_extended.py → THSExtendedClient
    • get_ai_stock_highlights() — AI要点分析 (结论/情感/影响/分析)
    • get_stock_reports()       — 个股研报列表
    • get_stock_news()          — 个股新闻
    • get_stock_concepts()      — 概念匹配

Provides:
  THS AI 对本股的多维观点 (正面/负面 + 影响度), AI推荐查询,
  人气排名, 是否在 AI 抽签选股名单中, 最新研报摘要.
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
            "data": {"_note": "AI insight only supports A-share"},
            "source": "skip",
            "fallback": False,
        }

    ai_points = {}
    popularity = {}
    draw_lots = {}
    reports = []
    concepts = []
    source_parts = []

    # --- THSExtendedClient: AI highlights ---
    try:
        from ths_api_extended import THSExtendedClient
        ext = THSExtendedClient(timeout=12)

        # AI stock highlights (main AI analysis)
        ai_raw = _safe(lambda: ext.get_ai_stock_highlights(code), {})
        if ai_raw and (ai_raw.get("points") or ai_raw.get("company_summary")):
            stock_info = ai_raw.get("stock", {})
            points_raw = ai_raw.get("points", [])
            positive_pts = [p for p in points_raw if p.get("sentiment") == 1]
            negative_pts = [p for p in points_raw if p.get("sentiment") != 1]

            ai_points = {
                "stock_name": stock_info.get("name", ""),
                "company_summary": ai_raw.get("company_summary", "")[:500],
                "total_points": len(points_raw),
                "positive_count": len(positive_pts),
                "negative_count": len(negative_pts),
                "positive_points": [
                    {
                        "conclusion": p.get("conclusion", "")[:200],
                        "impact": p.get("impact", ""),
                        "tag": p.get("tag_name", ""),
                    }
                    for p in positive_pts[:5]
                ],
                "negative_points": [
                    {
                        "conclusion": p.get("conclusion", "")[:200],
                        "impact": p.get("impact", ""),
                        "tag": p.get("tag_name", ""),
                    }
                    for p in negative_pts[:5]
                ],
                "recommended_queries": [
                    q.get("query", "") for q in ai_raw.get("recommend_query", [])[:5]
                ],
            }
            source_parts.append("ths_extended:ai_point")

        # Stock research reports
        rpt_raw = _safe(lambda: ext.get_stock_reports(code), {})
        if rpt_raw and rpt_raw.get("reportList"):
            reports = [
                {
                    "title": r.get("title", "")[:100],
                    "source": r.get("source", ""),
                    "author": r.get("author", ""),
                    "publish_time": r.get("publishTime", ""),
                }
                for r in rpt_raw.get("reportList", [])[:10]
            ]
            source_parts.append("ths_extended:reports")

        # Stock concepts
        concepts_raw = _safe(lambda: ext.get_stock_concepts(code), [])
        if concepts_raw:
            concepts = [
                {
                    "name": c.get("name", ""),
                    "explain": c.get("simple_explain", "")[:100],
                }
                for c in concepts_raw[:10]
            ]
            source_parts.append("ths_extended:concepts")
    except ImportError:
        pass

    # --- THSClient: popularity + AI picks ---
    try:
        from ths_api_client import THSClient
        client = THSClient(timeout=10)

        # Stock popularity ranking
        pop_raw = _safe(lambda: client.get_stock_popularity(code), {})
        if pop_raw and pop_raw.get("rank"):
            popularity = {
                "rank": pop_raw.get("rank"),
                "total": pop_raw.get("rank_amount"),
                "rank_change": pop_raw.get("rank_change"),
            }
            source_parts.append("ths:popularity")

        # AI draw lots (check if this stock is picked)
        dl_raw = _safe(lambda: client.get_draw_lots_rank(), {})
        if dl_raw and dl_raw.get("data"):
            tabs = dl_raw.get("data", {}).get("tab_list", [])
            in_picks = False
            pick_info = {}
            all_picks = []

            for tab in tabs:
                tab_name = tab.get("tab_name", "")
                for pick in tab.get("tab_data", []):
                    pick_entry = {
                        "code": pick.get("stock_code", ""),
                        "name": pick.get("stock_name", ""),
                        "reason": pick.get("reason", "")[:100],
                        "tab": tab_name,
                    }
                    all_picks.append(pick_entry)
                    if str(pick.get("stock_code", "")) == code:
                        in_picks = True
                        pick_info = pick_entry

            draw_lots = {
                "this_stock_picked": in_picks,
                "this_stock_pick_info": pick_info,
                "total_picks_today": len(all_picks),
                "all_tabs": [t.get("tab_name", "") for t in tabs],
                "sample_picks": all_picks[:10],
            }
            source_parts.append("ths:draw_lots")
    except ImportError:
        pass

    # --- Derive AI sentiment score (0-100) ---
    pos = ai_points.get("positive_count", 0)
    neg = ai_points.get("negative_count", 0)
    total = pos + neg
    if total > 0:
        ai_sentiment_score = round(pos / total * 100, 0)
    else:
        ai_sentiment_score = 50  # neutral

    if ai_sentiment_score >= 70:
        ai_label = "AI看多"
    elif ai_sentiment_score <= 30:
        ai_label = "AI看空"
    else:
        ai_label = "AI中性"

    return {
        "ticker": ti.full,
        "data": {
            "ai_analysis": ai_points,
            "ai_sentiment_score": ai_sentiment_score,
            "ai_label": ai_label,
            "popularity": popularity,
            "draw_lots": draw_lots,
            "research_reports": reports,
            "concepts": concepts,
        },
        "source": " + ".join(source_parts) if source_parts else "none",
        "fallback": not bool(source_parts),
    }


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "002938"
    print(json.dumps(main(arg), ensure_ascii=False, indent=2, default=str))
