#!/usr/bin/env python3
"""Generate activity-graph.svg: last 31 days of contributions as a line chart.

Faithful replica of github-readme-activity-graph.vercel.app output (the public
instance kept dying with "Can't fetch any contribution"), matching its
chartist-based rendering: 1200x420 card, dashed grid, animated 4px line,
white points, flat area fill. Data comes from the GitHub GraphQL API via the
gh CLI, so it works locally and in Actions with GITHUB_TOKEN.
"""

import json
import math
import subprocess
import sys
from pathlib import Path

USERNAME = "felipepiresx"
DAYS = 31

# geometry from the original service: 1200 x 420 canvas,
# chartPadding {top:80, right:50, bottom:20, left:20},
# axisY offset 70 (label gutter), axisX offset 50
WIDTH, HEIGHT = 1200, 420
PLOT_L, PLOT_R, PLOT_T, PLOT_B = 90, 1150, 80, 350
RADIUS = 10

BG = "#161b22"
COLOR = "#9be9a8"   # labels, grid, title
LINE = "#39d353"
POINT = "#ffffff"
AREA = "#006d32"
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


def chartist_bounds(y_max, axis_len, min_space=20):
    """Chartist-style tick step: integer steps of 1/2/5 x 10^n, at least
    min_space px apart, axis max rounded up to a multiple of the step."""
    max_ticks = max(1, axis_len // min_space)
    step = 1
    while True:
        for s in (step, step * 2, step * 5):
            if math.ceil(y_max / s) <= max_ticks:
                top = max(s, math.ceil(y_max / s) * s)
                return s, top
        step *= 10


def smooth_path(pts, y_top, y_bottom):
    """Catmull-Rom spline as cubic beziers (chartist cardinal, tension 0),
    clamped to the plot area so the curve never dips below the baseline."""
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


def main():
    days = fetch_days()
    counts = [d["contributionCount"] for d in days]
    step, y_top_val = chartist_bounds(max(max(counts), 1), PLOT_B - PLOT_T)

    plot_w = PLOT_R - PLOT_L
    plot_h = PLOT_B - PLOT_T
    step_x = plot_w / (DAYS - 1)

    pts = []
    for i, c in enumerate(counts):
        x = PLOT_L + i * step_x
        y = PLOT_B - plot_h * c / y_top_val
        pts.append((x, y))

    line_d = smooth_path(pts, PLOT_T, PLOT_B)
    area_d = (line_d + f" L{pts[-1][0]:.1f},{PLOT_B}"
              f" L{pts[0][0]:.1f},{PLOT_B} Z")

    grid, labels = [], []
    for v in range(0, y_top_val + 1, step):
        y = PLOT_B - plot_h * v / y_top_val
        grid.append(f'<line x1="{PLOT_L}" y1="{y:.1f}" x2="{PLOT_R}" y2="{y:.1f}" class="ct-grid"/>')
        labels.append(f'<text x="{PLOT_L - 10}" y="{y + 4.5:.1f}" class="ct-label" '
                      f'text-anchor="end">{v}</text>')
    for i, d in enumerate(days):
        x = PLOT_L + i * step_x
        grid.append(f'<line x1="{x:.1f}" y1="{PLOT_T}" x2="{x:.1f}" y2="{PLOT_B}" class="ct-grid"/>')
        labels.append(f'<text x="{x - 4.5:.1f}" y="{PLOT_B + 17}" class="ct-label" '
                      f'text-anchor="start">{int(d["date"].split("-")[2])}</text>')

    # axis titles, positioned as node-chartist renders them
    labels.append(f'<text x="{PLOT_L + plot_w / 2}" y="{PLOT_B + 50}" class="ct-label" '
                  f'text-anchor="middle" dominant-baseline="text-after-edge">Days</text>')
    labels.append(f'<text x="20" y="{PLOT_T + plot_h / 2}" class="ct-label" text-anchor="middle" '
                  f'dominant-baseline="hanging" transform="rotate(-90, 20, {PLOT_T + plot_h / 2})">'
                  f'Contributions</text>')

    dots = "".join(
        f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x + 0.01:.2f}" y2="{y:.1f}" class="ct-point"/>'
        for x, y in pts
    )

    svg = f'''<svg width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="0" rx="{RADIUS}" height="100%" width="100%" fill="{BG}"/>
  <style>
    svg {{
      font: 600 18px 'Segoe UI', Ubuntu, Sans-Serif;
      user-select: none;
    }}
    .title {{
      font: 600 20px 'Segoe UI', Ubuntu, Sans-Serif;
      fill: {COLOR};
    }}
    .ct-label {{
      fill: {COLOR};
      font-size: .75rem;
      line-height: 1;
    }}
    .ct-grid {{
      stroke: {COLOR};
      stroke-width: 1px;
      stroke-opacity: 0.3;
      stroke-dasharray: 2px;
    }}
    .ct-point {{
      stroke-width: 10px;
      stroke-linecap: round;
      stroke: {POINT};
      animation: blink 1s ease-in-out forwards;
    }}
    .ct-line {{
      fill: none;
      stroke-width: 4px;
      stroke-dasharray: 5000;
      stroke-dashoffset: 5000;
      stroke: {LINE};
      animation: dash 5s ease-in-out forwards;
    }}
    .ct-area {{
      stroke: none;
      fill: {AREA};
      fill-opacity: 0.1;
    }}
    @keyframes blink {{
      from {{ opacity: 0; transform: translateX(-20px); }}
      to {{ opacity: 1; transform: translateX(0); }}
    }}
    @keyframes dash {{
      to {{ stroke-dashoffset: 0; }}
    }}
  </style>
  <text x="{WIDTH / 2}" y="40" class="title" text-anchor="middle">{TITLE}</text>
  {"".join(grid)}
  {"".join(labels)}
  <path d="{area_d}" class="ct-area"/>
  <path d="{line_d}" class="ct-line"/>
  {dots}
</svg>
'''
    out = Path(__file__).resolve().parent.parent / "activity-graph.svg"
    out.write_text(svg, encoding="utf-8")
    print(f"wrote {out} (max {max(counts)}/day, y axis to {y_top_val} step {step})",
          file=sys.stderr)


if __name__ == "__main__":
    main()
