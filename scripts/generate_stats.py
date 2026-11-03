#!/usr/bin/env python3
"""Generate profile stats as self-hosted SVGs (no third-party widget services).

Reads public data from the GitHub REST API and writes:
  assets/stats.svg          - headline numbers
  assets/top-languages.svg  - language share by bytes across own, non-fork repos

Usage: GITHUB_TOKEN=... python scripts/generate_stats.py [username]
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

USER = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GITHUB_ACTOR", "matheussilvano")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = Path(__file__).resolve().parent.parent / "assets"

LANG_COLORS = {
    "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#3178c6", "HTML": "#e34c26",
    "CSS": "#563d7c", "Shell": "#89e051", "R": "#198CE7", "Jupyter Notebook": "#DA5B0B",
    "Go": "#00ADD8", "Assembly": "#6E4C13", "Lua": "#000080", "SCSS": "#c6538c",
}
OTHER_COLOR = "#8b949e"
# Team/hackathon repos with classmates: real work, but not open source contributions.
EXCLUDE_REPOS = {"eduoliveirachaves/web-frontend", "CarmoSnP/front-end-hackathon"}
# Languages that mostly describe markup/boilerplate rather than skill.
IGNORED = {"Jupyter Notebook"}


def api(path: str, **params):
    url = f"https://api.github.com{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "profile-stats"})
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def all_repos():
    page, repos = 1, []
    while True:
        batch = api(f"/users/{USER}/repos", per_page=100, page=page, type="owner")
        repos += batch
        if len(batch) < 100:
            return repos
        page += 1


def search_count(query: str) -> int:
    return api("/search/issues", q=query, per_page=1)["total_count"]


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


STYLE = """
  <style>
    .bg{fill:#ffffff;stroke:#d0d7de}.t{fill:#1f2328}.m{fill:#656d76}.trk{fill:#eaeef2}
    @media (prefers-color-scheme: dark){.bg{fill:#0d1117;stroke:#30363d}.t{fill:#e6edf3}.m{fill:#8b949e}.trk{fill:#21262d}}
    text{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif}
  </style>"""


def stats_svg(items: list[tuple[str, str]]) -> str:
    w, h = 420, 40 + 30 * len(items) + 14
    rows = []
    for i, (label, value) in enumerate(items):
        y = 62 + 30 * i
        rows.append(f'<text class="m" x="24" y="{y}" font-size="14">{esc(label)}</text>')
        rows.append(f'<text class="t" x="{w - 24}" y="{y}" font-size="14" font-weight="600" text-anchor="end">{esc(value)}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" '
            f'aria-label="GitHub stats for {USER}">{STYLE}\n  <rect class="bg" x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="8"/>\n'
            f'  <text class="t" x="24" y="32" font-size="16" font-weight="600">GitHub stats</text>\n  ' + "\n  ".join(rows) + "\n</svg>\n")


def languages_svg(shares: list[tuple[str, float]]) -> str:
    w, h = 420, 40 + 30 * len(shares) + 14
    rows = []
    for i, (lang, pct) in enumerate(shares):
        y = 62 + 30 * i
        color = LANG_COLORS.get(lang, OTHER_COLOR)
        bar = max(2.0, 150 * pct / 100)
        rows.append(f'<text class="t" x="24" y="{y}" font-size="13">{esc(lang)}</text>')
        rows.append(f'<rect class="trk" x="150" y="{y - 10}" width="190" height="10" rx="5"/>')
        rows.append(f'<rect x="150" y="{y - 10}" width="{bar * 190 / 150:.1f}" height="10" rx="5" fill="{color}"/>')
        rows.append(f'<text class="m" x="{w - 24}" y="{y}" font-size="13" text-anchor="end">{pct:.1f}%</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" '
            f'aria-label="Top languages for {USER}">{STYLE}\n  <rect class="bg" x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="8"/>\n'
            f'  <text class="t" x="24" y="32" font-size="16" font-weight="600">Top languages</text>\n  ' + "\n  ".join(rows) + "\n</svg>\n")


def constellation_svg(prs: list[dict]) -> str:
    """A night sky: one cluster per repository, one star per pull request.

    Filled stars are merged PRs, hollow pulsing stars are open ones. Positions are
    derived from hashes, so the same PR always lands on the same spot.
    """
    import hashlib
    import math

    w, h = 840, 360
    by_repo: dict[str, list[dict]] = {}
    for pr in prs:
        by_repo.setdefault(pr["repo"], []).append(pr)

    def unit(seed: str, salt: str) -> float:
        return int(hashlib.sha256(f"{salt}:{seed}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" '
        f'aria-label="Constellation of open source pull requests by {USER}">',
        "<style>text{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}"
        ".tw{animation:tw 3.2s ease-in-out infinite}.pu{animation:pu 2s ease-in-out infinite;transform-box:fill-box;transform-origin:center}"
        "@keyframes tw{0%,100%{opacity:.35}50%{opacity:1}}@keyframes pu{0%,100%{transform:scale(.8);opacity:.6}50%{transform:scale(1.35);opacity:1}}"
        "@media (prefers-reduced-motion: reduce){.tw,.pu{animation:none}}</style>",
        '<defs><radialGradient id="sky" cx="50%" cy="0%" r="110%"><stop offset="0" stop-color="#1b2540"/><stop offset="1" stop-color="#070b14"/></radialGradient></defs>',
        f'<rect width="{w}" height="{h}" rx="10" fill="url(#sky)"/>',
    ]
    for i in range(70):  # background dust
        x, y = unit(str(i), "dx") * w, unit(str(i), "dy") * h
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{0.4 + unit(str(i), "dr") * 0.9:.2f}" fill="#9fb3d9" opacity="{0.15 + unit(str(i), "do") * 0.35:.2f}"/>')

    repos = sorted(by_repo)
    n = max(len(repos), 1)
    for ri, repo in enumerate(repos):
        cx = w * (ri + 0.5) / n
        cy = h / 2 + (unit(repo, "cy") - 0.5) * 90
        stars = []
        for pr in by_repo[repo]:
            ang = unit(pr["url"], "a") * 2 * math.pi
            rad = 28 + unit(pr["url"], "r") * min(70, w / n / 2 - 24)
            stars.append((cx + math.cos(ang) * rad, cy + math.sin(ang) * rad * 0.8, pr))
        pts = [(cx, cy)] + [(x, y) for x, y, _ in stars]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#6f86b8" stroke-opacity=".5" stroke-width="1"/>')
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3.5" fill="#ffd479" class="tw"/>')
        for x, y, pr in stars:
            title = esc(f'{pr["repo"]}#{pr["number"]}: {pr["title"]} ({pr["state"]})')
            if pr["state"] == "merged":
                parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="#7ee787" class="tw" style="animation-delay:{unit(pr["url"], "d") * 3:.1f}s"><title>{title}</title></circle>')
            else:
                parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="none" stroke="#58a6ff" stroke-width="1.6" class="pu"><title>{title}</title></circle>')
        parts.append(f'<text x="{cx:.1f}" y="{min(h - 14, cy + 112):.1f}" font-size="11" fill="#c9d1d9" text-anchor="middle">{esc(repo.split("/")[1])}</text>')

    merged = sum(1 for p in prs if p["state"] == "merged")
    parts.append(f'<text x="20" y="28" font-size="13" fill="#e6edf3">open source constellation</text>')
    parts.append(f'<text x="20" y="46" font-size="11" fill="#8b949e">{merged} merged · {len(prs) - merged} open · {len(repos)} projects — one star per pull request</text>')
    parts.append(f'<circle cx="{w - 200}" cy="{h - 22}" r="4" fill="#7ee787"/><text x="{w - 190}" y="{h - 18}" font-size="11" fill="#8b949e">merged</text>')
    parts.append(f'<circle cx="{w - 120}" cy="{h - 22}" r="4" fill="none" stroke="#58a6ff" stroke-width="1.5"/><text x="{w - 110}" y="{h - 18}" font-size="11" fill="#8b949e">open</text>')
    parts.append("</svg>\n")
    return "\n".join(parts)


def pr_table(prs: list[dict], limit: int = 12) -> str:
    rows = ["| | Project | Pull request |", "|---|---|---|"]
    for pr in prs[:limit]:
        icon = "✅" if pr["state"] == "merged" else "🟢"
        rows.append(f'| {icon} | [{pr["repo"]}](https://github.com/{pr["repo"]}) | [{esc(pr["title"])}]({pr["url"]}) |')
    return "\n".join(rows)


def inject(readme: Path, marker: str, content: str) -> None:
    text = readme.read_text(encoding="utf-8")
    start, end = f"<!-- {marker}:START -->", f"<!-- {marker}:END -->"
    if start not in text or end not in text:
        return
    head, rest = text.split(start, 1)
    _, tail = rest.split(end, 1)
    readme.write_text(f"{head}{start}\n{content}\n{end}{tail}", encoding="utf-8")


def external_prs() -> list[dict]:
    items = api("/search/issues", q=f"author:{USER} is:pr is:public -user:{USER}", sort="created", order="desc", per_page=100)["items"]
    prs = []
    for it in items:
        if it["state"] == "closed" and not it["pull_request"].get("merged_at"):
            continue  # closed without merging: not shown
        repo = it["repository_url"].split("/repos/")[1]
        if repo in EXCLUDE_REPOS:
            continue
        prs.append({
            "repo": repo,
            "number": it["number"],
            "title": it["title"],
            "url": it["html_url"],
            "state": "merged" if it["pull_request"].get("merged_at") else "open",
        })
    return prs


def main() -> None:
    OUT.mkdir(exist_ok=True)
    profile = api(f"/users/{USER}")
    repos = all_repos()
    own = [r for r in repos if not r["fork"]]

    langs: Counter[str] = Counter()
    for repo in own:
        for lang, size in api(f"/repos/{USER}/{repo['name']}/languages").items():
            if lang not in IGNORED:
                langs[lang] += size
    total = sum(langs.values()) or 1
    top = langs.most_common(6)
    shares = [(lang, 100 * size / total) for lang, size in top]
    rest = 100 - sum(p for _, p in shares)
    if rest >= 0.5:
        shares.append(("Other", rest))

    merged_all = search_count(f"author:{USER} is:pr is:merged is:public")
    prs = external_prs()
    merged_external = sum(1 for p in prs if p["state"] == "merged")
    external_repos = {p["repo"] for p in prs if p["state"] == "merged"}
    stars = sum(r["stargazers_count"] for r in own)

    items = [
        ("Public repositories", str(profile["public_repos"])),
        ("Stars earned", str(stars)),
        ("Followers", str(profile["followers"])),
        ("Merged pull requests", str(merged_all)),
        ("Merged open source PRs", f"{merged_external} in {len(external_repos)} " + ("project" if len(external_repos) == 1 else "projects")),
    ]
    (OUT / "stats.svg").write_text(stats_svg(items), encoding="utf-8")
    (OUT / "top-languages.svg").write_text(languages_svg(shares), encoding="utf-8")
    (OUT / "constellation.svg").write_text(constellation_svg(prs), encoding="utf-8")
    inject(OUT.parent / "README.md", "PRS", pr_table(prs))
    print("prs:", [(p["repo"], p["number"], p["state"]) for p in prs])
    print("stats:", items)
    print("languages:", [(l, round(p, 1)) for l, p in shares])


if __name__ == "__main__":
    main()
