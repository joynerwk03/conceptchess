"""Elo-attribution graphs for ConceptChess (through session 23, 2026-07-24).

Lives in the project (research/graphs/) — the durable record of Elo over time.
Data source: research/LOG.md + metrics.json + ladder_anchors.json.
Method: dataviz skill (form -> color-by-job -> validated palette -> thin marks,
direct labels). Static PNGs, light mode. Regenerate: python research/graphs/make_graphs.py

The timeline plots SINGLE-THREAD strength as the consistent metric; Lazy SMP is a
parallelism multiplier (now the play default) shown as a separate boost, not folded
into the per-node line. All deltas are pooled/confirmed match gates (winner's curse
trims single batches: threats +83->+47, initiative +64->+32, retune +58->neutral).

Palette (validated): search #2a78d6 (blue) / eval #008300 (green) /
speed #e87ba4 (magenta) / book #eda100 (yellow).
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from pathlib import Path

OUT = Path(__file__).parent
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e2e1dc"
C_SEARCH = "#2a78d6"
C_EVAL = "#008300"
C_SPEED = "#e87ba4"
C_BOOK = "#eda100"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "text.color": TEXT, "axes.edgecolor": MUTED,
    "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
    "font.size": 10.5, "axes.titlesize": 13,
})


def style(ax):
    ax.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


# ---------------------------------------------------------------- graph 1
# Full timeline: measured anchors (filled) + chained estimates (hollow).
TIMELINE = [
    # (cum experiments, elo, lo, hi, anchored?, label)
    (0,   1569, 1349, 1789, False, "v0 build"),
    (9,   1737, 1575, 1916, True,  "s1 search+speed"),
    (41,  1772, 1552, 1992, False, "s2 eval concepts"),
    (52,  1807, 1587, 2027, False, "s3 threats"),
    (63,  1773, 1668, 1886, True,  "s4 anchor"),
    (71,  1850, 1737, 1963, True,  "s5 search"),
    (78,  2018, 1905, 2134, True,  "s6 opening book"),
    (88,  2018, 1838, 2198, False, "s7–8 plateau"),
    (92,  2442, 2305, 2582, True,  "s9 C CORE"),
    (97,  2495, 2275, 2715, False, "s10 SEE order"),
    (103, 2529, 2388, 2666, True,  "s11 ordering"),
    (110, 2514, 2372, 2652, True,  "s11 speed batch"),
    (116, 2654, 2505, 2794, True,  "s12 rep fix + king race"),
    (121, 2666, 2446, 2886, False, "s13 passers"),
    (128, 2654, 2505, 2794, True,  "s14 king pressure + UHO gates"),
    (135, 2685, 2539, 2823, True,  "s15 improving + qsearch TT"),
    (150, 2743, 2603, 2880, True,  "s16 Texel-XL tuning"),
    (156, 2677, 2575, 2776, True,  "s17 flywheel (pooled 60g)"),
    (163, 2639, 2533, 2739, True,  "s18 mop-up (pooled 60g)"),
    (172, 2665, 2525, 2805, True,  "s20 single-thread base"),
    # s21-23: single-thread eval/search gains (pooled, chained onto ~2665)
    (178, 2688, 2548, 2828, False, "s21 aspiration +23"),
    (186, 2735, 2595, 2875, False, "s22 threats +47"),
    (193, 2767, 2627, 2907, False, "s22 initiative +32"),
    (205, 2767, 2627, 2907, False, "s23 SMP now default (retune neutral)"),
]

fig, ax = plt.subplots(figsize=(10.2, 5.6), dpi=220)
xs = [p[0] for p in TIMELINE]
ys = [p[1] for p in TIMELINE]
ax.plot(xs, ys, color=C_SEARCH, lw=2, zorder=2)
for x, y, lo, hi, anchored, label in TIMELINE:
    ax.errorbar([x], [y], yerr=[[y - lo], [hi - y]], fmt="o",
                markersize=9 if anchored else 7, color=C_SEARCH,
                markerfacecolor=C_SEARCH if anchored else SURFACE,
                markeredgecolor=C_SEARCH, capsize=3, ecolor="#b9d2f2", zorder=3)
# Label only milestone points (descriptive); the rest are unlabeled dots on
# the line — 18 sessions won't fit with full labels in the crowded top region.
MILESTONES = {
    0:   ("v0 build — 1569", (8, -4)),
    9:   ("s1 search + speed", (8, -16)),
    78:  ("s6 opening book — 2018", (8, -18)),
    92:  ("s9 COMPILED C CORE — 2442", (-30, 14)),
    116: ("s12 rep fix + king race", (-70, 16)),
    150: ("s16 Texel\ntuning — 2743", (-64, -40)),
    172: ("s20 Lazy SMP: +187 @8 threads → 2772,\nnow the PLAY DEFAULT (s23)", (-30, 26)),
    193: ("s21–23: aspiration + threats +\ninitiative = +102 single-thread → ~2767", (2, -46)),
}
for x, y, lo, hi, anchored, label in TIMELINE:
    if x in MILESTONES:
        text, (dx, dy) = MILESTONES[x]
        ax.annotate(text, (x, y), textcoords="offset points",
                    xytext=(dx, dy), fontsize=8.5, color="#128a5f", weight="bold")
ax.annotate("(filled = ladder-anchored; hollow = chained from head-to-head gates. "
            "Line is single-thread; Lazy SMP adds ~+150 on top and is now the play default.)",
            (0.5, 0.02), xycoords="axes fraction", ha="center",
            fontsize=7.6, color=MUTED)
ax.set_title("ConceptChess: Elo across ~205 experiments (23 sessions)")
ax.set_xlabel("Cumulative experiments")
ax.set_ylabel("Elo (Stockfish UCI_Elo scale, 0.3s/move)")
ax.legend(handles=[
    Line2D([], [], marker="o", color=C_SEARCH, ls="", markersize=9,
           label="ladder-anchored (30–60 games vs multi-level Stockfish)"),
    Line2D([], [], marker="o", color=C_SEARCH, markerfacecolor=SURFACE,
           ls="", markersize=7, label="chained from head-to-head gates"),
], loc="upper left", fontsize=8.5, framealpha=0)
style(ax)
fig.tight_layout()
fig.savefig(OUT / "1_elo_all_sessions.png")
plt.close(fig)

# ---------------------------------------------------------------- graphs 2+3
# Per-category experiment record: every gated change, accepted or rejected.
SEARCH_EVENTS = [
    # (label, elo kept, rejected?)
    ("s1 LMR+PVS+futility*", 168, False),
    ("s2 aspiration", 0, True),
    ("s5 SEE-q, LMR tiers, checks", 53, False),
    ("s6 RFP / LMP (x3)", 0, True),
    ("s8 aspiration retry", 0, True),
    ("s8 one-reply ext", 0, True),
    ("s10 SEE ordering", 53, False),
    ("s11 aggressive LMR", 0, True),
    ("s11 malus+countermove", 35, False),
    ("s11 null-move guard", 6, False),
    ("s12 repetition fix", 47, False),
    ("s12 50-move rule", 0, True),
    ("s14 CMH ordering", 0, True),
    ("s14 aspiration (3rd try)", 0, True),
    ("s15 improving heuristic", 53, False),
    ("s15 futility-by-improving", 0, True),
    ("s15 CMH via LMR", 0, True),
    ("s15 qsearch TT probe", 35, False),
    ("s16 history-LMR", 0, True),
    ("s16 TT two-bucket", 0, True),
    ("s18 50-move rule v2", 0, True),
    ("s19 singular ext", 0, True),
    ("s19 IIR", 0, True),
    ("s20 LAZY SMP (8 threads)", 187, False),
    ("s21 aspiration windows", 23, False),
    ("s21 log-LMR table", 0, True),
    ("s21 IID", 0, True),
    ("s21 continuation history", 0, True),
    ("s21 root-move ordering", 0, True),
    ("s21 bigger TT", 0, True),
    ("s23 history-LMR", 0, True),
    ("s23 SMP helper diversity", 0, True),
]
EVAL_EVENTS = [
    ("s2 five concepts kept", 35, False),
    ("s2 weight tuning vs SF", 0, True),
    ("s3 threats @0.1x", 35, False),
    ("s4 divergence terms (x3)", 0, True),
    ("s7 mating drive", 0, False),
    ("s12 king race", 110, False),
    ("s13 connected passers", 12, False),
    ("s13 rook behind passer", 0, True),
    ("s13 unstoppable passer", 0, True),
    ("s14 king-pressure gradient", 41, False),
    ("s14 Texel tuning (x2)", 0, True),
    ("s15 space", 0, True),
    ("s16 Texel-XL", 53, False),
    ("s17 flywheel spin 2", 23, False),
    ("s17 flywheel spin 3", 12, False),
    ("s18 mop-up (endgame)", 29, False),
    ("s18 knight outposts", 0, True),
    ("s22 threats", 47, False),
    ("s22 threats-initiative", 32, False),
    ("s22 pawn storm", 0, True),
    ("s22 pawn-push threat", 0, True),
    ("s22 bad bishop", 0, True),
    ("s22 pins", 0, True),
    ("s23 rook-behind (kept)", 0, False),
    ("s23 full Texel retune", 0, True),
]


def category_chart(events, color, title, fname, note=None):
    fig, ax = plt.subplots(figsize=(13.0, 5.8), dpi=220)
    cum = 0
    xs, ys = [0], [0]
    for i, (label, gain, rejected) in enumerate(events, start=1):
        cum += gain
        xs.append(i)
        ys.append(cum)
    ax.step(xs, ys, where="post", color=color, lw=2, zorder=2)
    cum = 0
    rej_seen = acc_seen = 0
    for i, (label, gain, rejected) in enumerate(events, start=1):
        cum += gain
        if rejected:
            ax.plot([i], [cum], marker="x", color=MUTED, markersize=7,
                    markeredgewidth=2, zorder=3)
            # compact single-line reject labels, 5-level stagger so dense runs
            # (e.g. the s21/s23 tail) don't overlap; the pattern of x's carries
            # "many rejected" without a paragraph on each point.
            dy = (-20, -34, -48, -62, -76)[rej_seen % 5]
            rej_seen += 1
            ax.annotate(f"{label} ✗", (i, cum), textcoords="offset points",
                        xytext=(0, dy), fontsize=6.6, color=MUTED, ha="center")
        else:
            ax.plot([i], [cum], marker="o", color=color, markersize=8, zorder=3)
            dy = (11, 36, 61)[acc_seen % 3]   # 3-level stagger for long accepted labels
            acc_seen += 1
            ax.annotate(f"{label}\n+{gain}" if gain else f"{label}\n±0",
                        (i, cum), textcoords="offset points",
                        xytext=(0, dy), fontsize=7.4, color=TEXT, ha="center", weight="bold")
    ax.set_title(title)
    ax.set_xlabel("Gated experiments (in order; ✗ = rejected & reverted)")
    ax.set_ylabel("Cumulative Elo from accepted changes")
    ax.set_xticks(range(0, len(events) + 1, 2))
    ax.set_ylim(-95, max(ys) * 1.32 + 40)
    if note:
        ax.text(0.99, 0.02, note, transform=ax.transAxes, fontsize=7.8,
                color=MUTED, ha="right")
    style(ax)
    fig.tight_layout()
    fig.savefig(OUT / fname)
    plt.close(fig)


category_chart(SEARCH_EVENTS, C_SEARCH,
               "Search: many rejected, then Lazy SMP dwarfed them all",
               "2_search_experiments.png",
               note="*s1 gated search + Python speed work together (+168 combined)")
category_chart(EVAL_EVENTS, C_EVAL,
               "Evaluation experiments: gradients + outcome tuning at scale",
               "3_eval_experiments.png",
               note="every value is a 47–60 game match gate at 0.3s/move")

# ---------------------------------------------------------------- graph 4
# Attribution waterfall: where the ~1200 Elo actually came from.
WATERFALL = [
    ("v0 baseline", 1569, None),
    ("s1 search (LMR, PVS,\nfutility)", 113, C_SEARCH),
    ("s1 Python speedups\n(+45% NPS)", 55, C_SPEED),
    ("s2–3 eval concepts", 70, C_EVAL),
    ("s5 search sprint", 53, C_SEARCH),
    ("s6 opening book", 147, C_BOOK),
    ("s9 C CORE port\n(~50x nodes/s)", 382, C_SPEED),
    ("s10–12 search\n(SEE, ordering, rep fix)", 141, C_SEARCH),
    ("s11 byte-identical\nspeed batch", 108, C_SPEED),
    ("s12–13 endgame eval\n(king race, passers)", 122, C_EVAL),
    ("s14 king-pressure\ngradient", 41, C_EVAL),
    ("s15 improving +\nqsearch TT", 88, C_SEARCH),
    ("s16–17 outcome-tuning\nflywheel (3 spins)", 88, C_EVAL),
    ("s18 endgame mop-up", 29, C_EVAL),
    ("s21 aspiration\nwindows", 23, C_SEARCH),
    ("s22 threats +\ninitiative", 79, C_EVAL),
]
fig, ax = plt.subplots(figsize=(10.6, 5.8), dpi=220)
running = 0
for i, (label, val, color) in enumerate(WATERFALL):
    if color is None:
        ax.bar(i, val, width=0.62, color=MUTED, alpha=0.35)
        ax.annotate(f"{val}", (i, val), textcoords="offset points", xytext=(0, 4),
                    ha="center", fontsize=8.6, color=TEXT)
        running = val
    else:
        ax.bar(i, val, width=0.62, bottom=running, color=color)
        ax.annotate(f"+{val}", (i, running + val), textcoords="offset points",
                    xytext=(0, 4), ha="center", fontsize=8.6, color=TEXT)
        running += val
ax.axhline(running, color=GRID, lw=1, ls="--", zorder=1)
ax.annotate(f"single-thread chain ≈{running} (winner\u0027s-curse upper bound).\n"
            "Lazy SMP - now the play default - adds ~+150 on top: ~2900 in real play",
            (2.6, running - 150), fontsize=8.3, color=MUTED)
ax.set_xticks(range(len(WATERFALL)))
ax.set_xticklabels([w[0].replace("\n", " ") for w in WATERFALL], fontsize=6.8,
                   color=MUTED, rotation=20, ha="right")
ax.set_ylabel("Elo (cumulative, single-thread)")
ax.set_title("Where the Elo came from: implementation speed vs search vs eval knowledge")
ax.set_ylim(1400, running + 200)
ax.legend(handles=[
    plt.Rectangle((0, 0), 1, 1, color=C_SEARCH, label="search algorithm (+463)"),
    plt.Rectangle((0, 0), 1, 1, color=C_SPEED, label="implementation speed (+545)"),
    plt.Rectangle((0, 0), 1, 1, color=C_EVAL, label="eval knowledge (+429)"),
    plt.Rectangle((0, 0), 1, 1, color=C_BOOK, label="opening book (+147)"),
], loc="upper left", fontsize=8.5, framealpha=0)
style(ax)
fig.tight_layout()
fig.savefig(OUT / "4_attribution_waterfall.png")
plt.close(fig)

# ---------------------------------------------------------------- graph 5
# Fixed-depth node proxy vs gated Elo: the proxy does not predict strength.
PROXY = [
    # (label, % change nodes-to-fixed-depth (negative = "looks faster"), gated elo)
    ("reverse futility", -38, -56),
    ("RFP fixed", -25, -70),
    ("late-move pruning", -30, -56),
    ("aspiration (s8)", -7, -26),
    ("aggressive LMR (s11)", -10, -60),
    ("null-move guard", -11, 6),
    ("SEE ordering", 7, 53),
    ("malus+countermove", 10, 35),
    ("improving heuristic", -31, 53),
    ("futility-by-improving", -19, -12),
    ("qsearch TT probe", 17, 35),
    ("history-LMR", 5, -47),
    ("TT two-bucket", -2, -23),
]
fig, ax = plt.subplots(figsize=(8.8, 5.6), dpi=220)
ax.axhline(0, color=MUTED, lw=1)
ax.axvline(0, color=MUTED, lw=1)
LBL_OFF = {"malus+countermove": (-30, 8), "qsearch TT probe": (16, -18),
           "RFP fixed": (0, -16), "late-move pruning": (10, -16),
           "improving heuristic": (0, 10)}
for label, dn, elo in PROXY:
    ax.plot([dn], [elo], marker="o", color=C_SEARCH, markersize=9, zorder=3)
    dx, dy = LBL_OFF.get(label, (0, 8))
    ax.annotate(label, (dn, elo), textcoords="offset points", xytext=(dx, dy),
                fontsize=8.2, ha="center", color=TEXT)
ax.set_xlabel("Change in nodes to fixed depth (%)   ←  \"looks faster\"")
ax.set_ylabel("Match-gated Elo (60 games, fixed time)")
ax.set_title("Fixed-depth node counts don't predict strength (all points: this engine)")
ax.set_xlim(-44, 24)
ax.set_ylim(-82, 66)
ax.annotate("every DISCARD idea that\n\"won\" the node metric\nlost its match",
            (-40, 8), fontsize=8.6, color=MUTED)
ax.annotate("the one \"do less\" winner\ndeepens REDUCTIONS\n(re-searched on surprise)",
            (-27, 40), fontsize=8.6, color=MUTED)
ax.annotate("ordering + caching wins\nwere SLOWER to fixed depth",
            (6, -40), fontsize=8.6, color=MUTED)
style(ax)
fig.tight_layout()
fig.savefig(OUT / "5_proxy_vs_elo.png")
plt.close(fig)

print("wrote 5 graphs to", OUT)
