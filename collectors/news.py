# -*- coding: utf-8 -*-
"""Collect news via RSS (feedparser), with relevance filtering and cross-source hotness."""
import re
import calendar
from datetime import datetime

import feedparser


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
    text = re.sub(r"<[^>]+>", "", text)          # strip HTML tags
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def is_relevant(item, keywords):
    """Keep an item if its title/summary contains at least one relevance keyword."""
    if not keywords:
        return True
    text = (item.get("title", "") + " " + item.get("summary", "")).lower()
    return any(kw in text for kw in keywords)


# Common stopwords (VI + EN) to ignore when measuring cross-source overlap
_STOP = {
    "được", "những", "trong", "không", "người", "cũng", "này", "đã", "và", "của",
    "cho", "với", "một", "các", "khi", "thì", "là", "có", "để", "trên", "sau",
    "the", "and", "for", "that", "this", "with", "from", "have", "has", "will",
    "you", "your", "are", "was", "but", "not", "his", "her", "they", "what",
    "how", "why", "can", "new", "now", "who", "its", "about", "than",
}
_TOKEN_RE = re.compile(r"[0-9a-zà-ỹ]+", re.IGNORECASE)


def _terms(item):
    """Significant lowercase terms of an item (len >= 4, not a stopword)."""
    text = (item.get("title", "") + " " + (item.get("summary") or "")).lower()
    return {w for w in _TOKEN_RE.findall(text) if len(w) >= 4 and w not in _STOP}


def annotate_hotness(items, min_shared=2):
    """Set item['hot'] = number of OTHER items covering the SAME story.

    Two items are considered the same story if they share >= min_shared
    *distinctive* terms. Distinctive = appears in at least 2 items (so it can be
    shared) but not in too many (generic domain words like 'kinh', 'market' are
    dropped), so hotness reflects real cross-source coverage, not common words.
    """
    n = len(items)
    term_sets = [_terms(it) for it in items]

    # document frequency of each term
    df = {}
    for ts in term_sets:
        for t in ts:
            df[t] = df.get(t, 0) + 1
    # Keep only RARE terms (appear in 2..4 items): sharing these signals the same
    # specific story/entity, not just common finance vocabulary.
    max_df = max(2, min(4, int(n * 0.15)))
    distinctive = {t for t, c in df.items() if 2 <= c <= max_df}

    key_sets = [ts & distinctive for ts in term_sets]
    for i, it in enumerate(items):
        hot = sum(1 for j in range(n)
                  if i != j and len(key_sets[i] & key_sets[j]) >= min_shared)
        it["hot"] = hot
    return items


def collect(feeds_by_topic, per_feed=8, relevance_keywords=None):
    """feeds_by_topic: dict {topic: [(source_name, url), ...]}
    relevance_keywords: if given, keep only finance/market-relevant items."""
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
                items.append({"title": f"[Feed error {source}: {ex}]",
                              "link": "", "summary": "", "published": None,
                              "source": source})
        # newest first
        items.sort(key=lambda x: x["published"] or "", reverse=True)
        out[topic] = items
    return out


if __name__ == "__main__":
    import json
    from config import NEWS_FEEDS, NEWS_PER_FEED
    print(json.dumps(collect(NEWS_FEEDS, NEWS_PER_FEED), indent=2, ensure_ascii=False))
