#!/usr/bin/env python3
"""Answer a visitor's question from data/profile.json. No LLM, no API keys.

A small BM25 retriever ranks the resume chunks against the question and the best
matches are returned as a Markdown comment. The question comes from the environment
(ISSUE_TITLE / ISSUE_BODY) and is never interpolated into a shell command.
"""

from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from pathlib import Path

STOP = set(
    "a an and are as at be by can could did do does for from has have he her his how i in is it its me my of on or "
    "she should tell that the their them they this to was we were what when where which who whom whose why will with "
    "would you your about please matheus silvano pereira him know got get tell".split()
)
DATA = Path(__file__).resolve().parent.parent / "data" / "profile.json"
FALLBACK = (
    "I could not find a good match for that in the resume. Try asking about **RAG**, **telephony bots**, "
    "**FastAPI**, **Smart Pricing**, **Mooose**, **education**, **skills** or **contact**."
)


def tokens(text: str) -> list[str]:
    out = []
    for word in re.findall(r"[a-z0-9+#]+", text.lower()):
        if word in STOP or len(word) < 2:
            continue
        for suffix in ("ing", "ed", "es", "s"):
            if len(word) > len(suffix) + 3 and word.endswith(suffix):
                word = word[: -len(suffix)]
                break
        out.append(word)
    return out


def rank(question: str, chunks: list[dict]) -> list[tuple[float, dict]]:
    docs = [tokens(c["title"] * 2 + " " + c["tags"] * 2 + " " + c["text"]) for c in chunks]
    avg = sum(len(d) for d in docs) / len(docs)
    df = Counter(t for d in docs for t in set(d))
    query = set(tokens(question))
    scored = []
    for chunk, doc in zip(chunks, docs):
        tf = Counter(doc)
        score = 0.0
        for term in query:
            if term not in tf:
                continue
            idf = math.log(1 + (len(docs) - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * tf[term] * 2.2 / (tf[term] + 1.2 * (0.25 + 0.75 * len(doc) / avg))
        scored.append((score, chunk))
    return sorted(scored, key=lambda item: -item[0])


def clean(text: str) -> str:
    text = re.sub(r"^\s*ask\s*:\s*", "", text.strip(), flags=re.I)
    text = text.replace("@", "@​").replace("`", "'")
    return " ".join(text.split())[:300]


def main() -> None:
    title = os.environ.get("ISSUE_TITLE", "")
    body = os.environ.get("ISSUE_BODY", "")
    question = clean(title) if len(clean(title)) >= 3 else clean(body)
    chunks = json.loads(DATA.read_text(encoding="utf-8"))["chunks"]
    ranked = [(s, c) for s, c in rank(question, chunks) if s > 0.5]
    ranked = [(s, c) for s, c in ranked if s >= 0.6 * ranked[0][0]][:2] if ranked else []

    lines = [f"> {question}", ""]
    if ranked:
        for _, chunk in ranked:
            lines += [f"### {chunk['title']}", chunk["text"], ""]
    else:
        lines += [FALLBACK, ""]
    lines += [
        "---",
        "<sub>🤖 Answered by a tiny BM25 retriever over my resume — no LLM, no API keys. "
        "Source: [`scripts/answer_question.py`](../blob/main/scripts/answer_question.py). "
        "For anything else, [email me](mailto:matheussilvano2005@gmail.com).</sub>",
    ]
    print("\n".join(lines))


if __name__ == "__main__":
    main()
