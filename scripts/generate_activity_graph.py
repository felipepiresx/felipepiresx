#!/usr/bin/env python3
"""Generate activity-graph.svg: last 31 days of contributions as a line chart.

Replaces github-readme-activity-graph.vercel.app (kept dying with
"Can't fetch any contribution"). Data comes from the GitHub GraphQL API
via the gh CLI, so it works locally and in Actions with GITHUB_TOKEN.
"""

import json
import subprocess
import sys
from pathlib import Path

USERNAME = "felipepiresx"
DAYS = 31

WIDTH, HEIGHT = 1200, 450
MARGIN_L, MARGIN_R, MARGIN_T, MARGIN_B = 70, 40, 80, 75

BG = "#161b22"
TEXT = "#9be9a8"
LINE = "#39d353"
POINT = "#ffffff"
AREA = "#006d32"
GRID = "#39d35322"
TITLE = "Contribution Activity"

QUERY = (
    'query { user(login: "%s") { contributionsCollection { contributionCalendar '
    "{ weeks { contributionDays { date contributionCount } } } } } }" % USERNAME
)


def fetch_days():
    out = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={QUERY}"],
        capture_output=True, text=True, check=True,
    ).stdout
    cal = json.loads(out)["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    return days[-DAYS:]


def smooth_path(pts, y_top, y_bottom):
    """Catmull-Rom spline rendered as cubic beziers, clamped to the plot area
    so the curve never dips below the zero baseline."""
    if len(pts) < 3:
        return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)

    def clamp(y):
        return max(y_top, min(y_bottom, y))

    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(len(pts) - 1):
        p0 = pts[i - 1] if i > 0 else pts[i]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < len(pts) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, clamp(p1[1] + (p2[1] - p0[1]) / 6))
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, clamp(p2[1] - (p3[1] - p1[1]) / 6))
        d += (f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f}"
              f" {p2[0]:.1f},{p2[1]:.1f}")
    return d


def nice_ceiling(n):
    if n <= 5:
        return 5
    for step in (10, 20, 25, 50, 100, 200, 500):
        if n <= step:
            return step
    return ((n // 100) + 1) * 100


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def main():
    days = fetch_days()
    counts = [d["contributionCount"] for d in days]
    y_max = nice_ceiling(max(counts))

    plot_w = WIDTH - MARGIN_L - MARGIN_R
    plot_h = HEIGHT - MARGIN_T - MARGIN_B
    step_x = plot_w / (DAYS - 1)

    pts = []
    for i, c in enumerate(counts):
        x = MARGIN_L + i * step_x
        y = MARGIN_T + plot_h * (1 - c / y_max)
        pts.append((x, y))

    line_d = smooth_path(pts, MARGIN_T, MARGIN_T + plot_h)
    area_d = (line_d + f" L{pts[-1][0]:.1f},{MARGIN_T + plot_h:.1f}"
              f" L{pts[0][0]:.1f},{MARGIN_T + plot_h:.1f} Z")

    grid, ylabels = [], []
    n_grid = 5
    for g in range(n_grid + 1):
        y = MARGIN_T + plot_h * g / n_grid
        val = round(y_max * (1 - g / n_grid))
        grid.append(f'<line x1="{MARGIN_L}" y1="{y:.1f}" x2="{WIDTH - MARGIN_R}" '
                    f'y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        ylabels.append(f'<text x="{MARGIN_L - 12}" y="{y + 4:.1f}" fill="{TEXT}" '
                       f'font-size="13" text-anchor="end">{val}</text>')

    xlabels = []
    for i, d in enumerate(days):
        yy, mm, dd = d["date"].split("-")
        label = f"{int(dd)} {MONTHS[int(mm) - 1]}" if (i == 0 or dd == "01") else str(int(dd))
        x = MARGIN_L + i * step_x
        xlabels.append(f'<text x="{x:.1f}" y="{MARGIN_T + plot_h + 24:.1f}" fill="{TEXT}" '
                       f'font-size="12" text-anchor="middle">{label}</text>')

    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="{POINT}"/>' for x, y in pts
    )

    svg = f'''<svg width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" xmlns="http://www.w3.org/2000/svg">
  <style>text {{ font-family: 'Segoe UI', Ubuntu, sans-serif; font-weight: 600; }}</style>
  <defs>
    <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{AREA}" stop-opacity="0.65"/>
      <stop offset="100%" stop-color="{AREA}" stop-opacity="0.05"/>
    </linearGradient>
  </defs>
  <rect width="{WIDTH}" height="{HEIGHT}" rx="10" fill="{BG}"/>
  <text x="{WIDTH / 2}" y="45" fill="{TEXT}" font-size="22" text-anchor="middle">{TITLE}</text>
  {"".join(grid)}
  {"".join(ylabels)}
  {"".join(xlabels)}
  <path d="{area_d}" fill="url(#area)"/>
  <path d="{line_d}" fill="none" stroke="{LINE}" stroke-width="2.5"
        stroke-linecap="round" stroke-linejoin="round"/>
  {dots}
</svg>
'''
    out = Path(__file__).resolve().parent.parent / "activity-graph.svg"
    out.write_text(svg, encoding="utf-8")
    print(f"wrote {out} (max {max(counts)}/day over last {DAYS} days)", file=sys.stderr)


if __name__ == "__main__":
    main()
