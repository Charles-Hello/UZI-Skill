"""Best-effort event and historical LHB enrichment for preselected stocks."""
from __future__ import annotations

from datetime import datetime, time
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from .models import StockSnapshot


def _wrapped_data(payload: Any) -> dict:
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload if isinstance(payload, dict) else {}


def evidence_time(value: Any) -> datetime | None:
    try:
        text = str(value).strip()
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if len(text) == 10:
            # A date alone does not prove availability before the intraday cutoff.
            parsed = datetime.combine(parsed.date(), time.max)
        return parsed.replace(tzinfo=ZoneInfo("Asia/Shanghai")) if parsed.tzinfo is None else parsed
    except (ValueError, TypeError):
        return None


def filter_evidence(evidence: list[dict], cutoff: str) -> tuple[list[dict], list[str]]:
    boundary = evidence_time(cutoff)
    kept, gaps = [], []
    for item in evidence:
        published = evidence_time(item.get("published_at"))
        if boundary is None or published is None or published > boundary:
            gaps.append("evidence_time_unverified")
            continue
        if item.get("kind") == "lhb" and published.date() >= boundary.date():
            continue
        kept.append(item)
    return kept, sorted(set(gaps))


def is_business_evidence(item: dict) -> bool:
    if (item.get("kind") != "event" or item.get("grade") not in ("A", "B")
            or item.get("business_fact_verified") is not True
            or item.get("business_fact") not in ("order", "certification", "production", "earnings_contribution")
            or not item.get("source") or not item.get("title")):
        return False
    try:
        url = urlparse(str(item.get("url") or ""))
        return url.scheme in ("https", "http") and bool(url.netloc)
    except ValueError:
        return False


def enrich_stock(stock: StockSnapshot) -> tuple[list[dict], list[str]]:
    evidence: list[dict] = []
    gaps: list[str] = []
    try:
        import fetch_events

        payload = fetch_events.main(stock.code)
        data = _wrapped_data(payload)
        source = payload.get("source", "fetch_events") if isinstance(payload, dict) else "fetch_events"
        events = data.get("event_timeline") or data.get("recent_news") or []
        for item in events[:8]:
            if isinstance(item, dict):
                title = item.get("event") or item.get("title") or item.get("headline") or item.get("summary")
                published = item.get("date") or item.get("published_at") or item.get("time")
            else:
                title, published = str(item), None
            if title:
                evidence.append({
                    "kind": "event",
                    "grade": "C",
                    "business_fact_verified": False,
                    "title": str(title),
                    "published_at": published,
                    "observed_at": stock.observed_at,
                    "source": source,
                })
    except Exception as exc:
        gaps.append(f"events:{type(exc).__name__}")

    if stock.market == "A":
        try:
            import fetch_lhb

            payload = fetch_lhb.main(stock.code)
            data = _wrapped_data(payload)
            records = data.get("lhb_records") or []
            for record in records[:10]:
                if not isinstance(record, dict):
                    continue
                record_date = str(record.get("date") or record.get("上榜日期") or "")[:10]
                evidence.append({
                    "kind": "lhb",
                    "grade": "B",
                    "title": f"历史龙虎榜 {record_date or '日期缺失'}",
                    "published_at": record_date or None,
                    "observed_at": stock.observed_at,
                    "source": payload.get("source", "fetch_lhb") if isinstance(payload, dict) else "fetch_lhb",
                    "attribution_confidence": "style_only",
                })
        except Exception as exc:
            gaps.append(f"lhb:{type(exc).__name__}")
    evidence, time_gaps = filter_evidence(evidence, stock.observed_at)
    return evidence, sorted(set(gaps + time_gaps))
