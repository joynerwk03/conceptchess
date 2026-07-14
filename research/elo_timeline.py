"""Estimated Elo over the project, on one consistent scale.

Two states are ladder-anchored directly (MLE over multi-level Stockfish
matches, research/data/ladder_anchors.json); the others are placed by
chaining match-measured head-to-head deltas off the session-1 anchor.
Absolute numbers inherit Stockfish's UCI_Elo calibration at 0.3s/move —
a consistent scale, not FIDE ratings. Sources for every number: LOG.md.

Usage: python -m research.elo_timeline
"""

import html
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
ANCHORS = json.loads((HERE / "data" / "ladder_anchors.json").read_text())
SVG = HERE / "elo_timeline.svg"
HTML_OUT = HERE / "elo_report.html"
GREEN = "#1baf7a"

S1, S1_LO, S1_HI = ANCHORS["session1"]["mle"]
CUR, CUR_LO, CUR_HI = ANCHORS["current"]["mle"]
S5, S5_LO, S5_HI = ANCHORS["session5"]["mle"]
S6, S6_LO, S6_HI = ANCHORS["session6"]["mle"]
CC, CC_LO, CC_HI = ANCHORS["compiled"]["mle"]
CHAIN_ERR = 220  # ± for delta-chained points (10-20 game matches)

POINTS = [
    # v0: 20-game match vs session-1 gave s1 -168
    {"label": "v0 initial build", "exps": 0, "elo": S1 - 168,
     "lo": S1 - 168 - CHAIN_ERR, "hi": S1 - 168 + CHAIN_ERR, "kind": "chained"},
    # session 1: ladder-anchored (20 games vs SF1500/1700)
    {"label": "session 1 — search (LMR, PVS, futility)", "exps": 9,
     "elo": S1, "lo": S1_LO, "hi": S1_HI, "kind": "measured"},
    # session 2 final (exp-13): 10-game match vs s1: 55% (+35)
    {"label": "session 2 — concepts, faithful tuning lesson", "exps": 41,
     "elo": S1 + 35, "lo": S1 + 35 - CHAIN_ERR, "hi": S1 + 35 + CHAIN_ERR,
     "kind": "chained"},
    # session 3: threats gate 55% vs pre-threats (+35 more)
    {"label": "session 3 — rank metric, threats, contrastive", "exps": 52,
     "elo": S1 + 70, "lo": S1 + 70 - CHAIN_ERR, "hi": S1 + 70 + CHAIN_ERR,
     "kind": "chained"},
    # session 4: ladder-anchored (60 games vs SF1320-1800)
    {"label": "session 4 — ladder anchor (60 games)", "exps": 63,
     "elo": CUR, "lo": CUR_LO, "hi": CUR_HI, "kind": "measured"},
    # session 5: search sprint, ladder-anchored (40 games vs SF1700-2000)
    {"label": "session 5 — search sprint (SEE, LMR, checks)", "exps": 71,
     "elo": S5, "lo": S5_LO, "hi": S5_HI, "kind": "measured"},
    # session 6: opening book, ladder-anchored (40 games vs SF1800-2100)
    {"label": "session 6 — opening book (pruning dead-ends)", "exps": 78,
     "elo": S6, "lo": S6_LO, "hi": S6_HI, "kind": "measured"},
    # sessions 7-8: endgame fix + plateau (no strength change)
    {"label": "sessions 7-8 — endgame fix, pure-Python plateau", "exps": 88,
     "elo": S6, "lo": S6-180, "hi": S6+180, "kind": "chained"},
    # compiled core: C engine, ladder-anchored (30 games vs SF2200-2600)
    {"label": "COMPILED CORE — C engine (43x movegen)", "exps": 92,
     "elo": CC, "lo": CC_LO, "hi": CC_HI, "kind": "measured"},
]


def build():
    fig, ax = plt.subplots(figsize=(10.5, 5.8), dpi=110)
    xs = [p["exps"] for p in POINTS]
    ys = [p["elo"] for p in POINTS]
    ax.plot(xs, ys, color=GREEN, lw=2, zorder=2)
    for p in POINTS:
        measured = p["kind"] == "measured"
        ax.errorbar([p["exps"]], [p["elo"]],
                    yerr=[[p["elo"] - p["lo"]], [p["hi"] - p["elo"]]],
                    fmt="o", markersize=9 if measured else 7,
                    color=GREEN, markerfacecolor=GREEN if measured else "white",
                    markeredgecolor=GREEN, capsize=4, ecolor="#9dd8c0", zorder=3)
        ax.annotate(f'{p["label"]}\n≈{p["elo"]}', (p["exps"], p["elo"]),
                    textcoords="offset points",
                    xytext=(10, -26 if p["kind"] == "measured" else 10),
                    fontsize=8.3, color="#128a5f")
    ax.set_title("ConceptChess — estimated Elo over the autoresearch project",
                 fontsize=13)
    ax.set_xlabel("Cumulative experiments run")
    ax.set_ylabel("Estimated Elo (Stockfish UCI_Elo scale @ 0.3s/move)")
    ax.grid(True, color="#eeeeea", lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    # legend proxies
    from matplotlib.lines import Line2D
    ax.legend(handles=[
        Line2D([], [], marker="o", color=GREEN, ls="", markersize=9,
               label="ladder-anchored (direct MLE)"),
        Line2D([], [], marker="o", color=GREEN, markerfacecolor="white",
               ls="", markersize=7, label="chained from match deltas"),
    ], loc="lower right", fontsize=9)
    fig.tight_layout()
    fig.savefig(SVG, format="svg")
    print(f"wrote {SVG}")


def build_html():
    svg = SVG.read_text()
    svg = svg[svg.index("<svg"):]
    rows = ""
    for name, data in (("session 1", ANCHORS["session1"]),
                       ("session 4", ANCHORS["current"]),
                       ("session 5", ANCHORS["session5"]),
                       ("session 6", ANCHORS["session6"]),
                       ("compiled core (current)", ANCHORS["compiled"])):
        for opp, (w, d, l) in sorted(data["results"].items()):
            rows += (f"<tr><td>{name}</td><td>Stockfish {opp}</td>"
                     f"<td class='num'>+{w} ={d} −{l}</td>"
                     f"<td class='num'>{100 * (w + 0.5 * d) / (w + d + l):.0f}%</td></tr>")
    HTML_OUT.write_text(TEMPLATE.replace("{{SVG}}", svg).replace("{{ROWS}}", rows)
                        .replace("{{CUR}}", f"{CC} (95% {CC_LO}–{CC_HI})"))
    print(f"wrote {HTML_OUT}")


TEMPLATE = """<title>ConceptChess — Elo over time</title>
<style>
.elo-root { --surface:#fcfcfb; --text:#0b0b0b; --muted:#52514e; --border:#e2e1dc;
  max-width: 1050px; margin: 0 auto; padding: 26px 20px 60px;
  background: var(--surface); color: var(--text);
  font-family: -apple-system, "Segoe UI", Roboto, sans-serif; }
@media (prefers-color-scheme: dark) { .elo-root {
  --surface:#1a1a19; --text:#fff; --muted:#c3c2b7; --border:#33332f; } }
:root[data-theme="dark"] .elo-root { --surface:#1a1a19; --text:#fff;
  --muted:#c3c2b7; --border:#33332f; }
:root[data-theme="light"] .elo-root { --surface:#fcfcfb; --text:#0b0b0b;
  --muted:#52514e; --border:#e2e1dc; }
.elo-root h1 { font-size: 21px; margin: 0 0 4px; }
.elo-root .sub { color: var(--muted); font-size: 13.5px; margin: 0 0 18px; max-width: 80ch; }
.figwrap { background: #fff; border: 1px solid var(--border); border-radius: 10px;
  padding: 10px; overflow-x: auto; }
.figwrap svg { max-width: 100%; height: auto; display: block; margin: 0 auto; }
.elo-root h2 { font-size: 16px; margin: 24px 0 8px; }
table { border-collapse: collapse; font-size: 13.5px; min-width: 480px; }
th { text-align: left; color: var(--muted); font-size: 11.5px; text-transform: uppercase;
     letter-spacing: .05em; padding: 6px 10px; border-bottom: 1px solid var(--border); }
td { padding: 6px 10px; border-bottom: 1px solid var(--border); }
td.num { font-variant-numeric: tabular-nums; }
</style>
<div class="elo-root">
  <h1>ConceptChess — estimated Elo over time</h1>
  <p class="sub">Current engine: <strong>{{CUR}}</strong> on the Stockfish UCI_Elo
  scale at 0.3s/move (compiled C core; 30 ladder games vs SF 2200–2600). Filled points are direct ladder anchors;
  hollow points are chained from head-to-head match deltas recorded in LOG.md.
  Caveats: UCI_Elo calibration at fast time controls compresses level differences,
  and 10-game matches carry ~±200 Elo of noise — treat the scale as internally
  consistent rather than comparable to human ratings.</p>
  <div class="figwrap">{{SVG}}</div>
  <h2>Ladder match data</h2>
  <table>
    <thead><tr><th>Engine state</th><th>Opponent</th><th>Result</th><th>Score</th></tr></thead>
    <tbody>{{ROWS}}</tbody>
  </table>
</div>
"""


if __name__ == "__main__":
    build()
    build_html()
