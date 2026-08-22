# -*- coding: utf-8 -*-
"""Thu thap tin tuc qua RSS (feedparser)."""
import feedparser
from datetime import datetime
import calendar


def _published(entry):
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            try:
                return datetime.utcfromtimestamp(calendar.timegm(t)).isoformat() + "Z"
            except Exception:
                pass
    return None


def _clean(text, limit=280):
    if not text:
        return ""
    import re
    text = re.sub(r"<[^>]+>", "", text)          # bo the HTML
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def is_relevant(item, keywords):
    """Tin duoc giu neu tieu de/tom tat chua it nhat 1 tu khoa lien quan."""
    if not keywords:
        return True
    text = (item.get("title", "") + " " + item.get("summary", "")).lower()
    return any(kw in text for kw in keywords)


def collect(feeds_by_topic, per_feed=8, relevance_keywords=None):
    """feeds_by_topic: dict {topic: [(ten_nguon, url), ...]}
    relevance_keywords: neu co, chi giu tin lien quan tai chinh/thi truong."""
    out = {}
    for topic, feeds in feeds_by_topic.items():
        items = []
        for source, url in feeds:
            try:
                d = feedparser.parse(url)
                for e in d.entries[:per_feed]:
                    item = {
                        "title": _clean(e.get("title", ""), 200),
                        "link": e.get("link", ""),
                        "summary": _clean(e.get("summary", ""), 280),
                        "published": _published(e),
                        "source": source,
                    }
                    if is_relevant(item, relevance_keywords):
                        items.append(item)
            except Exception as ex:
                items.append({"title": f"[Loi doc feed {source}: {ex}]",
                              "link": "", "summary": "", "published": None,
                              "source": source})
        # sap xep moi nhat truoc
        items.sort(key=lambda x: x["published"] or "", reverse=True)
        out[topic] = items
    return out


if __name__ == "__main__":
    import json
    from config import NEWS_FEEDS, NEWS_PER_FEED
    print(json.dumps(collect(NEWS_FEEDS, NEWS_PER_FEED), indent=2, ensure_ascii=False))
