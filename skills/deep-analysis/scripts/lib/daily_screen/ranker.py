"""Hard gates, evidence confidence and actionability decisions."""
from __future__ import annotations

from .models import ScreenCandidate, StockSnapshot
from .personas import evaluate_f_personas, evaluate_serenity
from .events import filter_evidence


def preselect(stocks: list[StockSnapshot], limit: int = 40) -> list[StockSnapshot]:
    def score(stock: StockSnapshot) -> float:
        liquidity = min(stock.amount / 10e8, 4)
        strength = max(-3, min(stock.change_pct, 10))
        activity = min((stock.turnover_rate or 0) / 3, 3)
        return strength * 2 + liquidity + activity

    return sorted(stocks, key=score, reverse=True)[:limit]


def build_candidate(stock: StockSnapshot, theme: dict, evidence: list[dict], gaps: list[str]) -> ScreenCandidate:
    evidence, time_gaps = filter_evidence(evidence, stock.observed_at)
    gaps = list(gaps) + time_gaps
    verdicts = evaluate_f_personas(stock, theme, evidence)
    serenity = evaluate_serenity(stock, theme, evidence)
    active_f = [item for item in verdicts if item.eligible]
    bullish = [item for item in active_f if item.signal == "bullish"]
    bearish = [item for item in active_f if item.signal == "bearish"]

    quality_fields = [stock.price, stock.amount, stock.change_pct, stock.observed_at, stock.source]
    data_quality = sum(value not in (None, "") for value in quality_fields) / len(quality_fields) * 25
    theme_score = 0.0
    if theme.get("theme_rank"):
        theme_score += max(0, 15 - (theme["theme_rank"] - 1) * 2)
    theme_score += min(10, (theme.get("breadth_pct") or 0) / 10)
    event_score = min(20, sum(8 if item.get("grade") == "A" else 5 if item.get("grade") == "B" else 2 for item in evidence if item.get("kind") == "event"))
    tape_score = min(20, max(0, stock.change_pct + 5) + min(8, stock.amount / 2e8))
    if stock.high and stock.price >= stock.high * 0.985:
        tape_score = min(20, tape_score + 3)
    role_score = min(10, len(bullish) * 1.2 + (4 if serenity.signal == "bullish" else 1 if serenity.signal == "neutral" else 0))
    confidence = round(min(100, data_quality + theme_score + event_score + tape_score + role_score), 1)

    risk_flags = []
    # The spot provider supplies no order book, VWAP or executable-price proof.
    # A high rule score must not substitute for these missing observations.
    gaps.append("intraday_execution_unverified")
    if not theme:
        gaps.append("industry_context_missing")
    if stock.change_pct >= 8:
        risk_flags.append("短时涨幅偏大，追价风险高")
    if bearish and len(bearish) > len(bullish):
        risk_flags.append("F 组反对人数高于看多人数")
    if not any(item.get("kind") == "event" for item in evidence):
        gaps.append("event_evidence_missing")

    leader = (theme.get("leader_rank") or 999) <= 2
    if gaps or confidence < 70:
        action = "watch_only"
    elif stock.change_pct >= 7:
        action = "wait_pullback"
    elif leader and stock.change_pct >= 3 and (bullish or serenity.signal == "bullish"):
        action = "buyable"
    elif leader:
        action = "wait_reseal"
    else:
        action = "watch_only"

    supporters = [item.name for item in bullish[:4]]
    if serenity.signal == "bullish":
        supporters.append("Serenity")
    support_text = "、".join(supporters) if supporters else "暂无强看多角色"
    why_now = (
        f"行业横截面第 {theme.get('theme_rank', '—')}，个股板块内第 {theme.get('leader_rank', '—')}；"
        f"涨幅 {stock.change_pct:+.2f}%，成交额 {stock.amount / 1e8:.1f} 亿；{support_text}。"
    )
    entry = bullish[0].entry_condition if bullish else serenity.entry_condition
    invalidation = bearish[0].invalidation if bearish else (
        bullish[0].invalidation if bullish else "跌破上午承接位且板块宽度继续下降"
    )
    return ScreenCandidate(
        snapshot=stock,
        research_confidence=confidence,
        action=action,
        why_now=why_now,
        entry_condition=entry,
        invalidation=invalidation,
        theme_rank=theme.get("theme_rank"),
        leader_rank=theme.get("leader_rank"),
        theme_breadth_pct=theme.get("breadth_pct"),
        persona_verdicts=verdicts,
        serenity=serenity,
        evidence=evidence,
        data_gaps=sorted(set(gaps)),
        risk_flags=risk_flags,
    )


def rank_candidates(candidates: list[ScreenCandidate], top_n: int = 10, min_confidence: float = 70) -> tuple[list[ScreenCandidate], list[ScreenCandidate]]:
    ordered = sorted(candidates, key=lambda item: (item.research_confidence, item.snapshot.amount), reverse=True)
    picks = [item for item in ordered if item.research_confidence >= min_confidence and item.action not in ("avoid",)][:top_n]
    picked_codes = {item.snapshot.code for item in picks}
    rejected = [item for item in ordered if item.snapshot.code not in picked_codes]
    return picks, rejected
