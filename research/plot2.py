"""Karpathy-style session progress graphs from research/session{N}.json.

X = experiment number (every attempt counts), Y = the session's metric.
Kept improvements are green dots on an adopted-state step line with labels;
discarded attempts are faint gray dots. Writes research/session{N}_graph.svg
and research/session{N}_report.html (graph + per-experiment explanations).

Usage: python -m research.plot2 [session]     # default 2
"""

import html
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
SESSION = int(sys.argv[1]) if len(sys.argv) > 1 else 2
CFG = {
    2: {"metric": "val_loss", "train": "train_loss", "fmt": "{:.6f}",
        "val_h": "Val loss", "train_h": "Train loss",
        "ylabel": "Validation eval loss (lower is better)",
        "title": "session 2: evaluation-accuracy autoresearch",
        "blurb": "metric: MSE between win-prob of our static eval and Stockfish "
                 "depth-12, on a held-out 734-position set · final state "
                 "strength-gated by match play (see #24, #31)"},
    3: {"metric": "val_rank", "train": "train_rank", "fmt": "{:.2f}%",
        "val_h": "Val rank", "train_h": "Train rank",
        "ylabel": "Validation rank agreement % (higher is better)",
        "title": "session 3: move-ranking autoresearch",
        "blurb": "metric: % of positions where the static eval ranks Stockfish's "
                 "best move first among its top-3 (margin ≥ 30cp), held-out val "
                 "split · validated against match-measured strength of 4 engine "
                 "states · weight changes additionally match-gated"},
}[SESSION]
ENTRIES = json.loads((HERE / f"session{SESSION}.json").read_text())
SVG = HERE / f"session{SESSION}_graph.svg"
HTML_OUT = HERE / f"session{SESSION}_report.html"

GREEN = "#1baf7a"
GRAY = "#c9c9c4"


def build_graph():
    xs = [e["n"] for e in ENTRIES]
    ys = [e[CFG["metric"]] for e in ENTRIES]
    kept = [e["kept"] for e in ENTRIES]

    fig, ax = plt.subplots(figsize=(12, 6), dpi=110)
    # adopted-state line: every kept experiment moves it (the strength-gated
    # override at exp 24 legitimately steps it UP)
    bx = [e["n"] for e in ENTRIES if e["kept"]]
    by = [e[CFG["metric"]] for e in ENTRIES if e["kept"]]
    ax.step(bx + [xs[-1]], by + [by[-1]], where="post", color=GREEN,
            lw=1.8, alpha=0.85, label="Adopted state", zorder=2)

    dx = [x for x, k in zip(xs, kept) if not k]
    dy = [y for y, k in zip(ys, kept) if not k]
    ax.scatter(dx, dy, s=14, color=GRAY, alpha=0.75, label="Discarded", zorder=3)
    kx = [x for x, k in zip(xs, kept) if k]
    ky = [y for y, k in zip(ys, kept) if k]
    ax.scatter(kx, ky, s=42, color=GREEN, edgecolors="white", linewidths=1.2,
               label="Kept", zorder=4)

    for e in ENTRIES:
        if e["kept"]:
            ax.annotate(e["desc"], (e["n"], e[CFG["metric"]]),
                        textcoords="offset points", xytext=(6, 8),
                        fontsize=7.2, color="#128a5f", rotation=28,
                        rotation_mode="anchor", ha="left")

    n_kept = sum(kept)
    ax.set_title(f"Autoresearch Progress: {len(ENTRIES)} Experiments, "
                 f"{n_kept} Kept Improvements", fontsize=13)
    ax.set_xlabel("Experiment #")
    ax.set_ylabel(CFG["ylabel"])
    ax.grid(True, color="#eeeeea", lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(loc="upper right", fontsize=9, framealpha=0.9)
    # headroom for rotated labels
    lo, hi = ax.get_ylim()
    ax.set_ylim(lo, hi + (hi - lo) * 0.12)
    fig.tight_layout()
    fig.savefig(SVG, format="svg")
    print(f"wrote {SVG}")


def build_html():
    svg = SVG.read_text()
    svg = svg[svg.index("<svg"):]
    rows = ""
    for e in reversed(ENTRIES):
        badge = ("b-ok", "KEPT") if e["kept"] else ("b-no", "DISCARDED")
        rows += (f'<tr><td class="num">{e["n"]}</td>'
                 f'<td>{html.escape(e["desc"])}</td>'
                 f'<td class="num">{CFG["fmt"].format(e[CFG["metric"]])}</td>'
                 f'<td class="num">{CFG["fmt"].format(e[CFG["train"]])}</td>'
                 f'<td><span class="badge {badge[0]}">{badge[1]}</span></td></tr>')
    n_kept = sum(e["kept"] for e in ENTRIES)
    first = ENTRIES[0][CFG["metric"]]
    last = [e[CFG["metric"]] for e in ENTRIES if e["kept"]][-1]
    HTML_OUT.write_text(TEMPLATE
                        .replace("{{TITLE}}", CFG["title"])
                        .replace("{{SVG}}", svg)
                        .replace("{{ROWS}}", rows)
                        .replace("{{VALH}}", CFG["val_h"])
                        .replace("{{TRAINH}}", CFG["train_h"])
                        .replace("{{SUMMARY}}",
                                 f"{len(ENTRIES)} experiments, {n_kept} kept · "
                                 f"{CFG['fmt'].format(first)} → {CFG['fmt'].format(last)} · "
                                 + CFG["blurb"]))
    print(f"wrote {HTML_OUT}")


TEMPLATE = """<title>ConceptChess — autoresearch session</title>
<style>
.s2-root { --surface:#fcfcfb; --text:#0b0b0b; --muted:#52514e; --border:#e2e1dc;
  --panel:#ffffff; --ok:#128a5f; --no:#b3261e;
  max-width: 1150px; margin: 0 auto; padding: 26px 20px 60px;
  background: var(--surface); color: var(--text);
  font-family: -apple-system, "Segoe UI", Roboto, sans-serif; }
@media (prefers-color-scheme: dark) { .s2-root {
  --surface:#1a1a19; --text:#fff; --muted:#c3c2b7; --border:#33332f;
  --panel:#222221; --ok:#4ecb96; --no:#e66767; } }
:root[data-theme="dark"] .s2-root { --surface:#1a1a19; --text:#fff; --muted:#c3c2b7;
  --border:#33332f; --panel:#222221; --ok:#4ecb96; --no:#e66767; }
:root[data-theme="light"] .s2-root { --surface:#fcfcfb; --text:#0b0b0b; --muted:#52514e;
  --border:#e2e1dc; --panel:#ffffff; --ok:#128a5f; --no:#b3261e; }
.s2-root h1 { font-size: 21px; margin: 0 0 4px; }
.s2-root .sub { color: var(--muted); font-size: 13.5px; margin: 0 0 18px; max-width: 75ch; }
.figwrap { background: #ffffff; border: 1px solid var(--border); border-radius: 10px;
  padding: 10px; overflow-x: auto; }
.figwrap svg { max-width: 100%; height: auto; display: block; margin: 0 auto; }
.s2-root h2 { font-size: 16px; margin: 26px 0 10px; }
table.exps { width: 100%; border-collapse: collapse; font-size: 13px; }
table.exps th { text-align: left; color: var(--muted); font-size: 11.5px;
  text-transform: uppercase; letter-spacing: .05em; padding: 6px 8px;
  border-bottom: 1px solid var(--border); }
table.exps td { padding: 7px 8px; border-bottom: 1px solid var(--border); }
td.num { font-variant-numeric: tabular-nums; color: var(--muted); }
.badge { font-size: 10.5px; font-weight: 700; padding: 2px 8px; border-radius: 10px;
  white-space: nowrap; }
.b-ok { color: var(--ok); border: 1px solid var(--ok); }
.b-no { color: var(--no); border: 1px solid var(--no); }
</style>
<div class="s2-root">
  <h1>ConceptChess — {{TITLE}}</h1>
  <p class="sub">{{SUMMARY}}</p>
  <div class="figwrap">{{SVG}}</div>
  <h2>Every experiment</h2>
  <table class="exps">
    <thead><tr><th>#</th><th>Experiment</th><th>{{VALH}}</th><th>{{TRAINH}}</th><th>Verdict</th></tr></thead>
    <tbody>{{ROWS}}</tbody>
  </table>
</div>
"""


if __name__ == "__main__":
    build_graph()
    build_html()
