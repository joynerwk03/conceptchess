"""Karpathy-style session-2 progress graph from research/session2.json.

X = experiment number (every attempt counts), Y = validation eval loss.
Kept improvements are green dots on a running-best step line with labels;
discarded attempts are faint gray dots. Writes research/session2_graph.svg
and research/session2_report.html (graph + per-experiment explanations).

Usage: python -m research.plot2
"""

import html
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
ENTRIES = json.loads((HERE / "session2.json").read_text())
SVG = HERE / "session2_graph.svg"
HTML_OUT = HERE / "session2_report.html"

GREEN = "#1baf7a"
GRAY = "#c9c9c4"


def build_graph():
    xs = [e["n"] for e in ENTRIES]
    ys = [e["val_loss"] for e in ENTRIES]
    kept = [e["kept"] for e in ENTRIES]

    fig, ax = plt.subplots(figsize=(12, 6), dpi=110)
    # adopted-state line: every kept experiment moves it (the strength-gated
    # override at exp 24 legitimately steps it UP)
    bx = [e["n"] for e in ENTRIES if e["kept"]]
    by = [e["val_loss"] for e in ENTRIES if e["kept"]]
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
            ax.annotate(e["desc"], (e["n"], e["val_loss"]),
                        textcoords="offset points", xytext=(6, 8),
                        fontsize=7.2, color="#128a5f", rotation=28,
                        rotation_mode="anchor", ha="left")

    n_kept = sum(kept)
    ax.set_title(f"Autoresearch Progress: {len(ENTRIES)} Experiments, "
                 f"{n_kept} Kept Improvements", fontsize=13)
    ax.set_xlabel("Experiment #")
    ax.set_ylabel("Validation eval loss (lower is better)")
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
                 f'<td class="num">{e["val_loss"]:.6f}</td>'
                 f'<td class="num">{e["train_loss"]:.6f}</td>'
                 f'<td><span class="badge {badge[0]}">{badge[1]}</span></td></tr>')
    n_kept = sum(e["kept"] for e in ENTRIES)
    first = ENTRIES[0]["val_loss"]
    last = [e["val_loss"] for e in ENTRIES if e["kept"]][-1]
    HTML_OUT.write_text(TEMPLATE
                        .replace("{{SVG}}", svg)
                        .replace("{{ROWS}}", rows)
                        .replace("{{SUMMARY}}",
                                 f"{len(ENTRIES)} experiments, {n_kept} kept · "
                                 f"validation eval loss {first:.6f} → {last:.6f} "
                                 f"({100 * (first - last) / first:.1f}% better) · "
                                 f"metric: MSE between win-prob of our static eval and "
                                 f"Stockfish depth-12, on a held-out 734-position set · "
                                 f"final state strength-gated by match play (see #24, #31)"))
    print(f"wrote {HTML_OUT}")


TEMPLATE = """<title>ConceptChess — session 2: eval-loss autoresearch</title>
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
  <h1>ConceptChess — session 2: evaluation-accuracy autoresearch</h1>
  <p class="sub">{{SUMMARY}}</p>
  <div class="figwrap">{{SVG}}</div>
  <h2>Every experiment</h2>
  <table class="exps">
    <thead><tr><th>#</th><th>Experiment</th><th>Val loss</th><th>Train loss</th><th>Verdict</th></tr></thead>
    <tbody>{{ROWS}}</tbody>
  </table>
</div>
"""


if __name__ == "__main__":
    build_graph()
    build_html()
