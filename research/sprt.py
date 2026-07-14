"""Sequential probability ratio test for match gates.

Lets a gate match stop as soon as the result is decisive instead of always
playing the full N games — the biggest recurring time cost in the loop.

Trinomial model: each game is win/draw/loss. Under a hypothesis with expected
score p, we fix the draw probability from the running sample and split the
remaining mass into win/loss to hit mean p:
    pw = p - pd/2,   pl = 1 - pd - pw
The per-game log-likelihood ratio between H1 (elo=elo1) and H0 (elo=elo0)
accumulates; we stop when it crosses the Wald bounds.

    accept H1 (new engine better)      when LLR >= log((1-beta)/alpha)
    accept H0 (not better / worse)     when LLR <= log(beta/(1-alpha))
"""

import math


def _p(elo):
    return 1.0 / (1.0 + 10 ** (-elo / 400.0))


class SPRT:
    def __init__(self, elo0=0.0, elo1=35.0, alpha=0.05, beta=0.05, min_games=6):
        self.p0 = _p(elo0)
        self.p1 = _p(elo1)
        self.upper = math.log((1 - beta) / alpha)
        self.lower = math.log(beta / (1 - alpha))
        self.min_games = min_games
        self.w = self.d = self.l = 0

    def record(self, score):
        """score in {1.0 win, 0.5 draw, 0.0 loss} from our perspective."""
        if score == 1.0:
            self.w += 1
        elif score == 0.0:
            self.l += 1
        else:
            self.d += 1

    def _llr(self):
        n = self.w + self.d + self.l
        if n == 0:
            return 0.0
        pd = self.d / n
        # clamp win probs into a valid trinomial for both hypotheses
        eps = 1e-4
        llr = 0.0
        for p, sign in ((self.p1, 1), (self.p0, -1)):
            pw = min(max(p - pd / 2, eps), 1 - pd - eps)
            pl = 1 - pd - pw
            pdd = max(pd, eps)
            llr += sign * (self.w * math.log(pw) + self.l * math.log(pl)
                           + self.d * math.log(pdd))
        return llr

    def status(self):
        """Return 'H1', 'H0', or None (continue)."""
        n = self.w + self.d + self.l
        if n < self.min_games:
            return None
        llr = self._llr()
        if llr >= self.upper:
            return "H1"
        if llr <= self.lower:
            return "H0"
        return None


def _self_test():
    # A clearly-winning engine (80%) should accept H1; a clearly-losing one H0.
    import random
    rng = random.Random(0)
    for true_p, expect in ((0.80, "H1"), (0.20, "H0")):
        s = SPRT(elo0=0, elo1=35)
        outcome = None
        for _ in range(400):
            r = rng.random()
            s.record(1.0 if r < true_p else (0.5 if r < true_p + 0.15 else 0.0))
            outcome = s.status()
            if outcome:
                break
        assert outcome == expect, (true_p, outcome)
    print("sprt self-test ok")


if __name__ == "__main__":
    _self_test()
