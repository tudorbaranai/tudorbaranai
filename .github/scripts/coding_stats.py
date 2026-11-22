"""Draw the "when I commit" card for the profile README.

Counts public commits by time of day and writes two SVGs (dark and light
theme) with plain-text bars. Run by .github/workflows/profile-assets.yml;
the images go to the `output` branch, so README history stays clean.

Environment:
  GITHUB_TOKEN  token for the GitHub API (the Actions token is enough)
  GH_USER       GitHub username
  TIMEZONE      zone used to place commits in the day (default Europe/Bucharest)
  OUT_DIR       where to write the SVGs (default dist)
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
USER = os.environ.get("GH_USER", "tudorbaranai")
TZ = ZoneInfo(os.environ.get("TIMEZONE", "Europe/Bucharest"))
OUT_DIR = os.environ.get("OUT_DIR") or "dist"

BAR_LEN = 21
PARTIALS = ["", "▏", "▎", "▍", "▌", "▋", "▊", "▉"]
COLORS = {"dark": "#f0f6fc", "light": "#1f2328"}


def get(path, params):
    url = f"{API}{path}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-stats",
        **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def commit_hours():
    """Local hour of every public commit authored by USER (search API caps at 1000)."""
    seen, hours = set(), []
    for page in range(1, 11):
        items = get("/search/commits", {
            "q": f"author:{USER}", "sort": "author-date", "order": "desc",
            "per_page": 100, "page": page,
        }).get("items", [])
        for item in items:
            if item["sha"] in seen:
                continue
            seen.add(item["sha"])
            stamp = item["commit"]["author"]["date"].replace("Z", "+00:00")
            hours.append(datetime.fromisoformat(stamp).astimezone(TZ).hour)
        if len(items) < 100:
            break
    return hours


def bar(share):
    units = share * BAR_LEN
    full = int(units)
    part = PARTIALS[int((units - full) * 8)] if full < BAR_LEN else ""
    return ("█" * full + part).ljust(BAR_LEN, "░")


def lines(hours):
    parts = Counter(
        "Morning" if 6 <= h < 12 else "Daytime" if 12 <= h < 18
        else "Evening" if 18 <= h < 24 else "Night"
        for h in hours
    )
    total = len(hours) or 1
    return [
        f"{name:<9}{parts[name]:>4} commits  {bar(parts[name] / total)}  {parts[name] / total * 100:5.1f}%"
        for name in ("Morning", "Daytime", "Evening", "Night")
    ]


def render(rows, color):
    row_h, pad, char_w = 22, 12, 8.6
    width = round(len(rows[0]) * char_w + pad * 2)
    height = row_h * len(rows) + pad * 2 - 6
    text = "\n".join(
        f'<text x="{pad}" y="{pad + 14 + i * row_h}">{escape(r)}</text>' for i, r in enumerate(rows)
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<style>text {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "DejaVu Sans Mono", monospace; font-size: 14px; fill: {color}; white-space: pre; }}</style>
<g xml:space="preserve">
{text}
</g>
</svg>
'''


def main():
    hours = commit_hours()
    print(f"{len(hours)} commits", file=sys.stderr)
    rows = lines(hours)
    print("\n".join(rows), file=sys.stderr)
    os.makedirs(OUT_DIR, exist_ok=True)
    for theme, name in (("dark", "coding-stats-dark.svg"), ("light", "coding-stats.svg")):
        with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as f:
            f.write(render(rows, COLORS[theme]))


if __name__ == "__main__":
    main()
