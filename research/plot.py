"""Generate research/report.html from research/metrics.json.

Self-contained (inline CSS/SVG/JS), theme-aware progress report: KPI row with
the latest numbers, one small-multiple line chart per tracked metric over
experiment number, and a per-experiment explanation table.

Usage: python -m research.plot
"""

import html
import json
from pathlib import Path

HERE = Path(__file__).parent
METRICS = HERE / "metrics.json"
OUT = HERE / "report.html"

# metric key -> (title, unit label, better direction, format)
CHARTS = [
    ("avg_depth_2s", "Average search depth", "plies @ 2s/position", "up", "{:.2f}"),
    ("avg_nps", "Search speed", "nodes/second", "up", "{:,.0f}"),
    ("tactics_pct_1s", "Tactics accuracy", "% solved @ 1s/move", "up", "{:.1f}%"),
    ("nodes_to_depth6", "Search efficiency", "nodes to depth 6 (lower is better)", "down", "{:,.0f}"),
]

KPIS = [
    ("avg_depth_2s", "Avg depth @ 2s", "{:.2f}"),
    ("avg_nps", "Nodes / second", "{:,.0f}"),
    ("tactics_pct_1s", "Tactics solved", "{:.1f}%"),
    ("elo_vs_v0", "Elo vs v0", "{:+.0f}"),
]


def fmt(spec, v):
    return spec.format(v) if v is not None else "—"


def chart_svg(entries, key, title, unit, better, spec):
    pts = [(e["experiment"], e["metrics"][key]) for e in entries
           if e["metrics"].get(key) is not None]
    if len(pts) < 2:
        return ""
    W, H = 380, 200
    ml, mr, mt, mb = 52, 14, 14, 30
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, x1 = min(e["experiment"] for e in entries), max(e["experiment"] for e in entries)
    lo, hi = min(ys), max(ys)
    pad = (hi - lo) * 0.15 or abs(hi) * 0.1 or 1
    lo, hi = lo - pad, hi + pad

    def X(x):
        return ml + (x - x0) / max(1, x1 - x0) * (W - ml - mr)

    def Y(y):
        return mt + (hi - y) / (hi - lo) * (H - mt - mb)

    path = " ".join(f"{'M' if i == 0 else 'L'}{X(x):.1f},{Y(y):.1f}"
                    for i, (x, y) in enumerate(pts))
    # y ticks: 3 clean values
    ticks = [lo + pad, (lo + hi) / 2, hi - pad]
    grid = "".join(
        f'<line x1="{ml}" x2="{W - mr}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" class="grid"/>'
        f'<text x="{ml - 6}" y="{Y(t):.1f}" class="tick" text-anchor="end" dy="0.32em">'
        f'{html.escape(_short(t))}</text>'
        for t in ticks)
    xt = "".join(
        f'<text x="{X(e["experiment"]):.1f}" y="{H - 8}" class="tick" text-anchor="middle">'
        f'{e["experiment"]}</text>' for e in entries)
    by_x = {e["experiment"]: e for e in entries}
    dots = ""
    for x, y in pts:
        e = by_x[x]
        rejected = e["verdict"] == "REJECTED"
        cls = "dot rejected" if rejected else "dot"
        tip = (f"#{x} {e['title']} — {e['verdict']}&#10;{key}: {fmt(spec, y)}")
        dots += (f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="5" class="{cls}"'
                 f' data-tip="{html.escape(tip)}"/>')
    last_x, last_y = pts[-1]
    end_label = (f'<text x="{X(last_x) - 8:.1f}" y="{Y(last_y) - 10:.1f}" class="endlabel"'
                 f' text-anchor="end">{fmt(spec, last_y)}</text>')
    return f"""
<figure class="chart">
  <figcaption><strong>{html.escape(title)}</strong>
    <span class="unit">{html.escape(unit)}</span></figcaption>
  <svg viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(title)} by experiment">
    {grid}{xt}
    <path d="{path}" class="line"/>
    {dots}{end_label}
    <text x="{(ml + W - mr) / 2:.0f}" y="{H - 8}" class="tick axis-title"
          text-anchor="middle" dy="12"></text>
  </svg>
</figure>"""


def _short(v):
    if abs(v) >= 10000:
        return f"{v / 1000:.0f}k"
    if abs(v) >= 100:
        return f"{v:.0f}"
    return f"{v:.1f}"


def build():
    entries = json.loads(METRICS.read_text())
    entries.sort(key=lambda e: e["experiment"])
    latest = {}
    for e in entries:
        if e["verdict"] != "REJECTED":
            for k, v in e["metrics"].items():
                if v is not None:
                    latest[k] = v

    kpis = ""
    for key, label, spec in KPIS:
        if key in latest:
            kpis += (f'<div class="tile"><div class="klabel">{html.escape(label)}</div>'
                     f'<div class="kvalue">{fmt(spec, latest[key])}</div></div>')

    charts = "".join(chart_svg(entries, *c) for c in CHARTS)

    rows = ""
    for e in reversed(entries):
        v = e["verdict"]
        badge = {"ACCEPTED": "b-ok", "REJECTED": "b-no", "BASELINE": "b-base"}.get(v, "b-base")
        rev = f'<code>{e["rev"]}</code>' if e.get("rev") else "—"
        rows += (f'<tr><td class="num">{e["experiment"]}</td>'
                 f'<td><strong>{html.escape(e["title"])}</strong><br>'
                 f'<span class="expl">{html.escape(e["explanation"])}</span></td>'
                 f'<td><span class="badge {badge}">{v}</span></td>'
                 f'<td>{rev}</td></tr>')

    n_acc = sum(1 for e in entries if e["verdict"] == "ACCEPTED")
    n_rej = sum(1 for e in entries if e["verdict"] == "REJECTED")
    OUT.write_text(TEMPLATE
                   .replace("{{KPIS}}", kpis)
                   .replace("{{CHARTS}}", charts)
                   .replace("{{ROWS}}", rows)
                   .replace("{{COUNTS}}", f"{len(entries)} experiments — "
                                          f"{n_acc} accepted, {n_rej} rejected")
                   .replace("{{DATE}}", entries[-1]["date"]))
    print(f"wrote {OUT}")


TEMPLATE = """<title>ConceptChess — research progress</title>
<style>
.viz-root {
  --surface-1: #fcfcfb; --text-primary: #0b0b0b; --text-secondary: #52514e;
  --text-muted: #7a7974; --series-1: #2a78d6; --grid: #e7e6e2;
  --panel: #ffffff; --border: #e2e1dc; --ok: #008300; --no: #b3261e;
  max-width: 900px; margin: 0 auto; padding: 28px 20px 60px;
  background: var(--surface-1); color: var(--text-primary);
  font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
}
@media (prefers-color-scheme: dark) { .viz-root {
  --surface-1: #1a1a19; --text-primary: #ffffff; --text-secondary: #c3c2b7;
  --text-muted: #8f8e86; --series-1: #3987e5; --grid: #2e2e2c;
  --panel: #222221; --border: #33332f; --ok: #58b658; --no: #e66767; } }
:root[data-theme="dark"] .viz-root {
  --surface-1: #1a1a19; --text-primary: #ffffff; --text-secondary: #c3c2b7;
  --text-muted: #8f8e86; --series-1: #3987e5; --grid: #2e2e2c;
  --panel: #222221; --border: #33332f; --ok: #58b658; --no: #e66767; }
:root[data-theme="light"] .viz-root {
  --surface-1: #fcfcfb; --text-primary: #0b0b0b; --text-secondary: #52514e;
  --text-muted: #7a7974; --series-1: #2a78d6; --grid: #e7e6e2;
  --panel: #ffffff; --border: #e2e1dc; --ok: #008300; --no: #b3261e; }
.viz-root h1 { font-size: 22px; margin: 0 0 2px; }
.viz-root .sub { color: var(--text-secondary); margin: 0 0 22px; font-size: 14px; }
.kpis { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 26px; }
.tile { background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
        padding: 12px 18px; min-width: 130px; }
.klabel { font-size: 12px; color: var(--text-secondary); }
.kvalue { font-size: 26px; font-weight: 600; margin-top: 2px; }
.grid-charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
               gap: 18px; margin-bottom: 30px; }
.chart { margin: 0; background: var(--panel); border: 1px solid var(--border);
         border-radius: 10px; padding: 12px 12px 4px; }
.chart figcaption { font-size: 13.5px; margin: 2px 4px 6px; }
.chart .unit { color: var(--text-muted); font-size: 12px; margin-left: 6px; }
.chart svg { width: 100%; height: auto; display: block; }
.line { fill: none; stroke: var(--series-1); stroke-width: 2;
        stroke-linejoin: round; stroke-linecap: round; }
.grid { stroke: var(--grid); stroke-width: 1; }
.tick { fill: var(--text-muted); font-size: 10px; font-variant-numeric: tabular-nums; }
.endlabel { fill: var(--text-secondary); font-size: 11px; font-weight: 600; }
.dot { fill: var(--series-1); stroke: var(--panel); stroke-width: 2; cursor: pointer; }
.dot.rejected { fill: var(--panel); stroke: var(--text-muted); }
table.exps { width: 100%; border-collapse: collapse; font-size: 13.5px; }
table.exps th { text-align: left; color: var(--text-secondary); font-size: 12px;
    text-transform: uppercase; letter-spacing: .05em; padding: 6px 8px;
    border-bottom: 1px solid var(--border); }
table.exps td { padding: 10px 8px; border-bottom: 1px solid var(--border);
    vertical-align: top; }
table.exps td.num { color: var(--text-muted); font-variant-numeric: tabular-nums; }
table.exps strong, table.exps code { color: var(--text-primary); }
.expl { color: var(--text-secondary); }
.badge { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 10px;
         white-space: nowrap; }
.b-ok { color: var(--ok); border: 1px solid var(--ok); }
.b-no { color: var(--no); border: 1px solid var(--no); }
.b-base { color: var(--text-muted); border: 1px solid var(--text-muted); }
#tip { position: fixed; display: none; background: var(--panel); color: var(--text-primary);
       border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px;
       font-size: 12px; white-space: pre-line; pointer-events: none; z-index: 5;
       box-shadow: 0 4px 14px rgba(0,0,0,.18); max-width: 280px; }
</style>
<div class="viz-root">
  <h1>ConceptChess — research progress</h1>
  <p class="sub">{{COUNTS}} · updated {{DATE}} · metrics measured after each experiment
     (rejected experiments shown as hollow points; they left the engine unchanged)</p>
  <div class="kpis">{{KPIS}}</div>
  <div class="grid-charts">{{CHARTS}}</div>
  <h1 style="font-size:17px">Experiments &amp; explanations</h1>
  <table class="exps">
    <thead><tr><th>#</th><th>Experiment</th><th>Verdict</th><th>Commit</th></tr></thead>
    <tbody>{{ROWS}}</tbody>
  </table>
  <div id="tip"></div>
</div>
<script>
const tip = document.getElementById("tip");
document.querySelectorAll(".dot").forEach(d => {
  d.addEventListener("mousemove", ev => {
    tip.textContent = d.dataset.tip;
    tip.style.display = "block";
    tip.style.left = Math.min(ev.clientX + 14, innerWidth - 300) + "px";
    tip.style.top = (ev.clientY + 14) + "px";
  });
  d.addEventListener("mouseleave", () => tip.style.display = "none");
});
</script>
"""


if __name__ == "__main__":
    build()
