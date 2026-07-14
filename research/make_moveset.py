"""Label eval-set positions with Stockfish's top moves (multipv).

For each position in the existing eval set, records SF depth-12 multipv-3:
the top moves with their scores. Used by the move-ranking metrics (session 3).
Output: research/data/moves_{train,val}.jsonl with
{"fen": ..., "moves": [[uci, cp_white], ...]}   (best first)

Usage: python -m research.make_moveset
"""

import json
import shutil
from pathlib import Path

import chess
import chess.engine

DATA = Path(__file__).parent / "data"
SF_DEPTH = 12
CLIP = 1200


def main():
    sf = chess.engine.SimpleEngine.popen_uci(shutil.which("stockfish"))
    try:
        for split in ("train", "val"):
            rows = [json.loads(l) for l in
                    (DATA / f"evalset_{split}.jsonl").read_text().splitlines()]
            out = []
            for i, r in enumerate(rows):
                board = chess.Board(r["fen"])
                if board.legal_moves.count() < 3:
                    continue
                infos = sf.analyse(board, chess.engine.Limit(depth=SF_DEPTH), multipv=3)
                moves = []
                for info in infos:
                    cp = info["score"].white().score(mate_score=CLIP + 1)
                    moves.append([info["pv"][0].uci(), max(-CLIP, min(CLIP, cp))])
                out.append({"fen": r["fen"], "moves": moves})
                if (i + 1) % 400 == 0:
                    print(f"  {split}: {i + 1}/{len(rows)}")
            path = DATA / f"moves_{split}.jsonl"
            path.write_text("\n".join(json.dumps(r) for r in out) + "\n")
            print(f"wrote {len(out)} -> {path}")
    finally:
        sf.quit()


if __name__ == "__main__":
    main()
