"""SPSA over the search constants, gated on GAMES against an external anchor.

Why this and not the referee screen: the screen is fixed-depth, so its optimum
for a pruning parameter is "prune less" all the way to plain alpha-beta. An
objective that cannot see the depth benefit will always walk this search toward
a fatter tree, which is the trap already walked into twice here. So every
iteration costs real games.

Why SPSA rather than more sweeps: it perturbs ALL parameters at once and needs
exactly two evaluations per iteration regardless of dimension, and it tolerates a
noisy objective by design -- which is the situation here, where a 120-game batch
resolves nothing on its own but its NOISE AVERAGES OUT over iterations while the
gradient signal accumulates. Single-parameter sweeps measured neutral precisely
because the surface is flat along each axis; that says nothing about off-axis.

The two perturbations play each other directly on shared openings (`abgate` with
theta-plus as candidate and theta-minus as baseline), so the anchor's own drift
cancels and the paired delta IS the gradient signal.

Standard SPSA gains: a_k = a/(A+k+1)^alpha, c_k = c/(k+1)^gamma. Parameters are
rescaled to a common unit range so one step size fits all six.

Checkpoints every iteration to spsa_state.json, so this survives interruption --
it is a long run and losing it to a restart would be the expensive failure.
"""
import json
import os
import pathlib
import random
import re
import subprocess
import sys

# abgate finds the anchor with shutil.which("stockfish"), and a non-interactive
# shell does not have ~/bin on PATH. Set it here rather than in the caller: the
# Windows entries in this box's PATH contain spaces, and exporting it from a
# wrapper shell mangles into a dozen "not a valid identifier" errors that
# surface only as a failed parse much later.
os.environ["PATH"] = f"{pathlib.Path.home()}/bin:" + os.environ.get("PATH", "")

CC = pathlib.Path("/home/joynerwk03/mission-control/projects/conceptchess")
PY = str(CC / ".venv/bin/python")
R = pathlib.Path("/home/joynerwk03/ccruns")
STATE = R / "spsa_state.json"

SEED = {"rfp": 90.0, "lmp": 5.0, "lmr2": 3.0, "lmr3": 12.0, "asp": 35.0, "hist": 8192.0}
# Per-parameter perturbation size, in the parameter's own units. Scaled to the
# NOISE, which is what SPSA requires and what the first sizing got wrong: a
# 100-slot batch has se ~32 Elo, so a perturbation whose true effect is 5 Elo is
# invisible no matter how many iterations run. These are large enough that the
# true difference between theta+ and theta- is comparable to the noise -- the
# RFP margin alone spans 33 Elo between 25 and 90, so +/-40 is well inside the
# region where this function has real structure, not off in a degenerate search.
CK = {"rfp": 40.0, "lmp": 2.5, "lmr2": 1.5, "lmr3": 6.0, "asp": 22.0, "hist": 7000.0}
KEYS = sorted(SEED)

GAMES = int(sys.argv[1]) if len(sys.argv) > 1 else 60      # per arm per iteration
ITERS = int(sys.argv[2]) if len(sys.argv) > 2 else 60
ANCHOR = sys.argv[3] if len(sys.argv) > 3 else "stockfish:3000"

A_GAIN, A_STAB, ALPHA, GAMMA = 0.30, 8.0, 0.602, 0.101


def build(name, p):
    wt = CC / "research/worktrees" / name
    subprocess.run(["git", "worktree", "remove", "--force", f"research/worktrees/{name}"],
                   cwd=CC, capture_output=True)
    subprocess.run(["git", "worktree", "add", f"research/worktrees/{name}", "HEAD"],
                   cwd=CC, capture_output=True, check=True)
    args = [PY, str(R / "spsa_patch.py"), str(wt)] + [f"{k}={p[k]}" for k in KEYS]
    subprocess.run(args, capture_output=True, check=True)
    subprocess.run(["sh", "core/build.sh"], cwd=wt, capture_output=True)
    if not (wt / "core/libcengine.so").exists():
        raise RuntimeError(f"BUILD FAILED for {name}")
    return wt


def play(wt_plus, wt_minus, offset):
    """Paired delta in Elo, theta-plus minus theta-minus."""
    out = subprocess.run(
        [PY, "-m", "research.abgate", "--games", str(GAMES), "--opponent", ANCHOR,
         "--baseline-cwd", str(wt_minus), "--movetime", "0.3", "--threads", "1",
         "--concurrency", "6", "--opening-offset", str(offset)],
        cwd=wt_plus, capture_output=True, text=True)
    # [-+]? , not -? : abgate prints "+70.5 Elo" for a positive delta, and a
    # regex that only accepts a minus sign parses every losing iteration and
    # crashes on the first winning one. That killed three runs and got blamed on
    # the tool timeout and on detached processes before the output was read.
    m = re.search(r"PAIRED external delta.*?:\s*([-+]?[\d.]+) Elo", out.stdout)
    if not m:
        sys.stderr.write(out.stdout[-1500:] + out.stderr[-500:])
        raise RuntimeError("could not parse abgate output")
    return float(m.group(1))


def main():
    if STATE.exists():
        st = json.loads(STATE.read_text())
        theta, k0 = st["theta"], st["k"]
        print(f"resumed at iteration {k0}", flush=True)
    else:
        theta, k0 = dict(SEED), 0

    rng = random.Random(20260827)
    for _ in range(k0):
        [rng.choice((-1, 1)) for _ in KEYS]          # keep the stream aligned

    for k in range(k0, ITERS):
        ak = A_GAIN / (A_STAB + k + 1) ** ALPHA
        ck = 1.0 / (k + 1) ** GAMMA
        d = {key: rng.choice((-1, 1)) for key in KEYS}
        pp = {key: theta[key] + ck * CK[key] * d[key] for key in KEYS}
        pm = {key: theta[key] - ck * CK[key] * d[key] for key in KEYS}

        wp, wm = build("spsa_p", pp), build("spsa_m", pm)
        elo = play(wp, wm, offset=(k * 997) % 1000)

        # gradient of (-Elo) wrt each parameter; step DOWN that gradient
        for key in KEYS:
            g = -elo / (2.0 * ck * CK[key] * d[key])
            theta[key] -= ak * g * CK[key] * CK[key] / 100.0

        STATE.write_text(json.dumps({"theta": theta, "k": k + 1, "last_elo": elo}))
        print(f"iter {k:3d}  paired {elo:+7.1f} Elo  "
              + " ".join(f"{key}={theta[key]:.0f}" for key in KEYS), flush=True)


if __name__ == "__main__":
    main()
