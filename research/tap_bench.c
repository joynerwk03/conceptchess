/* Is packed-integer tapering actually faster than the double TAP we have?
 *
 * The structural idea for reaching 3000 is integer evaluation in BOTH languages
 * -- the invariant is "C eval equals Python eval", not "the eval is floating
 * point", so integers preserve it exactly. What that would buy is Stockfish's
 * trick: pack (middlegame, endgame) into one int32 so tapering is a single add
 * instead of two multiplies and two adds.
 *
 * Before refactoring the most safety-critical code in the project, measure the
 * inner loop. The pawn hash was a plausible speed idea that measured -1.0%.
 *
 * Three variants over the same synthetic weight stream:
 *   A  current: double phase*mg + (1-phase)*eg, per weight
 *   B  packed int32 (mg<<16 | eg) accumulated with one add, resolved ONCE
 *   C  packed, but resolved per weight (the naive port -- should be no better)
 *
 * cc -O2 -o /tmp/tapbench tap_bench.c && /tmp/tapbench
 */
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <stdint.h>

#define NW 40          /* weights touched per evaluation, post-Phase-3 */
#define NEVAL 20000000 /* evaluations */

static double now(void){
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec*1e-9;
}

int main(void){
    static double wmg[NW], weg[NW];
    static int32_t packed[NW];
    static double cnt[NW];
    srand(7);
    for(int i=0;i<NW;i++){
        int mg = rand()%200 - 50, eg = rand()%200 - 50;
        wmg[i]=mg; weg[i]=eg;
        packed[i]=((int32_t)mg<<16) + eg;   /* two int16 in one int32 */
        cnt[i]=(rand()%7)-3;                 /* how many times the term fires */
    }

    volatile double sink_d = 0; volatile int32_t sink_i = 0;

    double t0=now();
    for(int e=0;e<NEVAL;e++){
        double phase = (e & 24) / 24.0;
        double s=0;
        for(int i=0;i<NW;i++) s += cnt[i] * (phase*wmg[i] + (1.0-phase)*weg[i]);
        sink_d += s;
    }
    double tA=now()-t0;

    t0=now();
    for(int e=0;e<NEVAL;e++){
        int phase = e & 24;
        int32_t acc=0;
        for(int i=0;i<NW;i++) acc += (int32_t)cnt[i] * packed[i];
        /* resolve the pair once, at the end */
        int16_t eg = (int16_t)(acc & 0xffff);
        int16_t mg = (int16_t)((acc + 0x8000) >> 16);
        sink_i += (mg*phase + eg*(24-phase)) / 24;
    }
    double tB=now()-t0;

    t0=now();
    for(int e=0;e<NEVAL;e++){
        int phase = e & 24;
        int32_t s=0;
        for(int i=0;i<NW;i++){
            int16_t eg = (int16_t)(packed[i] & 0xffff);
            int16_t mg = (int16_t)((packed[i] + 0x8000) >> 16);
            s += (int32_t)cnt[i] * (mg*phase + eg*(24-phase)) / 24;
        }
        sink_i += s;
    }
    double tC=now()-t0;

    printf("weights per eval: %d, evaluations: %d\n\n", NW, NEVAL);
    printf("A  double TAP (what we have)      %6.3fs   1.00x\n", tA);
    printf("B  packed int32, resolved once    %6.3fs   %.2fx\n", tB, tA/tB);
    printf("C  packed int32, resolved per wt  %6.3fs   %.2fx\n", tC, tA/tC);
    printf("\n(sinks %g %d -- keeps the loops from being optimised away)\n",
           (double)sink_d, (int)sink_i);
    return 0;
}
