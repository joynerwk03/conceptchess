"""Find the adjudication threshold EMPIRICALLY instead of asserting one.

Resign adjudication would speed the loop up by roughly 20-30% of wall clock,
because decisive games typically reach a winning score around move 40-50 and
then spend another 20-40 plies converting. The question is what threshold is
safe, and asserting "1000cp" is an opinion. This measures it.

Method. For every ply of every game, record BOTH engines' scores (requiring both
to agree removes the risk of adjudicating on one engine's blind spot) and the
eventual result. Then for each candidate (threshold, persistence) pair, find the
games where the rule would have fired, and check how often the predicted winner
actually won. Report accuracy and the plies saved, so the trade is visible
rather than assumed.

The bias this is really testing. Adjudication removes CONVERSION skill from the
measurement, and conversion is real strength -- this engine's KPvK bitbase and
root tablebases live entirely in that phase, and contempt's whole mechanism is
draw avoidance. So the rule is scored SEPARATELY on games that reach an endgame,
because if those need a much higher threshold that quantifies the bias instead
of leaving it as an assertion.

Usage:
  adjudicate.py record <n_games> <out.jsonl> [opponent] [movetime]
  adjudicate.py analyse <in.jsonl>
"""
import json
import sys
from pathlib import Path

import chess
import chess.engine

ROOT = Path("/home/joynerwk03/mission-control/projects/conceptchess")


def record(n, out, opponent="stockfish:2800", movetime=0.3):
    """Play n games, logging both engines' score at every ply plus the result."""
    import shutil
    sf = shutil.which("stockfish")
    assert sf, "REFUSING TO RECORD: stockfish not on PATH"
    elo = int(opponent.split(":")[1])
    book = [l.split()[0:4] for l in
            open(ROOT / "research/books/uho_1000.epd").read().splitlines() if l.strip()]

    ours = chess.engine.SimpleEngine.popen_uci(
        [str(ROOT / ".venv/bin/python"), "-m", "engine.uci"], cwd=str(ROOT))
    them = chess.engine.SimpleEngine.popen_uci(sf)
    them.configure({"UCI_LimitStrength": True, "UCI_Elo": elo, "Threads": 1})
    lim = chess.engine.Limit(time=movetime)
    rows = []
    try:
        for g in range(n):
            b = chess.Board(" ".join(book[(g // 2) % len(book)]))
            we_white = (g % 2 == 0)
            trace = []
            while not b.is_game_over(claim_draw=True) and b.fullmove_number < 200:
                mover = ours if (b.turn == chess.WHITE) == we_white else them
                other = them if mover is ours else ours
                r = mover.play(b, lim, info=chess.engine.INFO_SCORE)
                sc = r.info.get("score")
                oi = other.analyse(b, chess.engine.Limit(depth=8))
                s1 = sc.white().score(mate_score=10000) if sc else None
                s2 = oi["score"].white().score(mate_score=10000)
                if s1 is not None:
                    trace.append([s1, s2])
                b.push(r.move)
            res = b.result(claim_draw=True)
            w = 1.0 if res == "1-0" else (0.0 if res == "0-1" else 0.5)
            rows.append({"white_score": w, "plies": len(trace), "trace": trace,
                         "pieces_end": chess.popcount(b.occupied)})
            print(f"game {g+1}/{n} {res} {len(trace)} plies", flush=True)
    finally:
        ours.quit()
        them.quit()
    Path(out).write_text("\n".join(json.dumps(r) for r in rows))
    print(f"wrote {len(rows)} games -> {out}")


def analyse(path):
    rows = [json.loads(l) for l in open(path) if l.strip()]
    print(f"{len(rows)} games\n")
    print(f"{'thresh':>7}{'plies':>7}{'fired':>7}{'correct':>9}{'acc':>8}"
          f"{'saved%':>8}{'endgame acc':>13}")
    for th in (400, 600, 800, 1000, 1200, 1500):
        for persist in (4, 8):
            fired = ok = saved = total_plies = 0
            eg_fired = eg_ok = 0
            for r in rows:
                tr, res = r["trace"], r["white_score"]
                total_plies += len(tr)
                run_side, run_len, hit = 0, 0, None
                for i, (s1, s2) in enumerate(tr):
                    side = 1 if (s1 >= th and s2 >= th) else (-1 if (s1 <= -th and s2 <= -th) else 0)
                    run_len = run_len + 1 if side and side == run_side else (1 if side else 0)
                    run_side = side
                    if side and run_len >= persist:
                        hit = (i, side)
                        break
                if hit is None:
                    continue
                i, side = hit
                fired += 1
                saved += len(tr) - i
                pred = 1.0 if side > 0 else 0.0
                good = (res == pred)
                ok += good
                if r["pieces_end"] <= 10:
                    eg_fired += 1
                    eg_ok += good
            if not fired:
                continue
            eg = f"{100*eg_ok/eg_fired:.1f}% ({eg_fired})" if eg_fired else "n/a"
            print(f"{th:>7}{persist:>7}{fired:>7}{ok:>9}{100*ok/fired:>7.1f}%"
                  f"{100*saved/total_plies:>7.1f}%{eg:>13}")


if __name__ == "__main__":
    if sys.argv[1] == "record":
        record(int(sys.argv[2]), sys.argv[3], *sys.argv[4:])
    else:
        analyse(sys.argv[2])
