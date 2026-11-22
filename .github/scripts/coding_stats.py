"""Draw a "coding habits" card for the profile README.

Reads public commits and repo languages from the GitHub API and writes two
SVG files (dark and light theme). Run by .github/workflows/profile-assets.yml;
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
OUT_DIR = os.environ.get("OUT_DIR", "dist")

ACCENT = "#00C02E"
THEMES = {
    "dark": {"text": "#e6edf3", "muted": "#8b949e", "track": "#21262d", "border": "#30363d"},
    "light": {"text": "#1f2328", "muted": "#59636e", "track": "#eaeef2", "border": "#d0d7de"},
}

IGNORED_LANGUAGES = {"HTML", "CSS", "Batchfile", "Makefile", "Dockerfile", "Shell"}


def get(path, params=None):
    url = f"{API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-stats",
        **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def commit_times():
    """Local datetimes of every public commit authored by USER (search API caps at 1000)."""
    seen, times = set(), []
    for page in range(1, 11):
        data = get("/search/commits", {
            "q": f"author:{USER}", "sort": "author-date", "order": "desc",
            "per_page": 100, "page": page,
        })
        items = data.get("items", [])
        for item in items:
            sha = item["sha"]
            if sha in seen:
                continue
            seen.add(sha)
            stamp = item["commit"]["author"]["date"].replace("Z", "+00:00")
            times.append(datetime.fromisoformat(stamp).astimezone(TZ))
        if len(items) < 100:
            break
    return times


def languages():
    totals = Counter()
    repos = get(f"/users/{USER}/repos", {"type": "owner", "per_page": 100})
    for repo in repos:
        if repo["fork"] or repo["name"].lower() == USER.lower():
            continue
        for lang, size in get(f"/repos/{USER}/{repo['name']}/languages").items():
            if lang not in IGNORED_LANGUAGES:
                totals[lang] += size
    return totals


def build_sections(times, langs):
    parts = Counter()
    for t in times:
        h = t.hour
        parts["Morning" if 6 <= h < 12 else "Daytime" if 12 <= h < 18
              else "Evening" if 18 <= h < 24 else "Night"] += 1
    day_rows = [("🌞", "Morning"), ("🌆", "Daytime"), ("🌃", "Evening"), ("🌙", "Night")]
    early = parts["Morning"] + parts["Daytime"] >= parts["Evening"] + parts["Night"]

    weekdays = Counter(t.strftime("%A") for t in times)
    week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    best_day = max(week, key=lambda d: weekdays[d]) if times else "—"

    total = len(times) or 1
    lang_total = sum(langs.values()) or 1
    return [
        ("I'm an early 🐤" if early else "I'm a night 🦉",
         [(f"{e} {name}", f"{parts[name]} commits", parts[name] / total) for e, name in day_rows]),
        (f"📅 I'm most productive on {best_day}",
         [(d, f"{weekdays[d]} commits", weekdays[d] / total) for d in week]),
        ("💬 Languages I write in",
         [(lang, "", size / lang_total) for lang, size in langs.most_common(5)]),
    ]


def render(sections, theme):
    c = THEMES[theme]
    width, pad, row, gap = 520, 24, 22, 18
    label_x, count_x, bar_x, bar_w = pad, 170, 270, 170
    y = pad
    body = []
    delay = 0.0
    for title, rows in sections:
        y += 16
        body.append(f'<text x="{pad}" y="{y}" class="title">{escape(title)}</text>')
        y += 10
        for label, count, share in rows:
            y += row
            fill = max(share * bar_w, 2 if share else 0)
            body.append(f'<text x="{label_x}" y="{y}" class="label">{escape(label)}</text>')
            if count:
                body.append(f'<text x="{count_x}" y="{y}" class="muted">{escape(count)}</text>')
            body.append(f'<rect x="{bar_x}" y="{y - 10}" width="{bar_w}" height="10" rx="3" fill="{c["track"]}"/>')
            body.append(f'<rect x="{bar_x}" y="{y - 10}" width="{fill:.1f}" height="10" rx="3" '
                        f'fill="{ACCENT}" class="bar" style="animation-delay:{delay:.2f}s"/>')
            body.append(f'<text x="{width - pad}" y="{y}" class="muted" text-anchor="end">{share * 100:.1f}%</text>')
            delay += 0.05
        y += gap
    height = y + pad - gap + 6
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<style>
  text {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 13px; fill: {c["text"]}; }}
  .title {{ font-weight: 700; font-size: 14px; fill: {ACCENT}; }}
  .muted {{ fill: {c["muted"]}; }}
  .bar {{ transform-box: fill-box; transform-origin: left; animation: grow .8s ease-out both; }}
  @keyframes grow {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
</style>
<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" fill="none" stroke="{c["border"]}"/>
{chr(10).join(body)}
</svg>
'''


def main():
    times = commit_times()
    langs = languages()
    print(f"{len(times)} commits, {len(langs)} languages", file=sys.stderr)
    sections = build_sections(times, langs)
    os.makedirs(OUT_DIR, exist_ok=True)
    for theme, name in (("dark", "coding-stats-dark.svg"), ("light", "coding-stats.svg")):
        with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as f:
            f.write(render(sections, theme))


if __name__ == "__main__":
    main()
