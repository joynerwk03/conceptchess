/* ConceptChess compiled core — evaluation, mirroring the Python concept eval.
 *
 * #included at the end of cengine.c (shares its Board, tables, and helpers).
 * Must return the SAME value as Python evaluate() so the fast search optimizes
 * exactly what the Python explanation reports. Cross-checked position by
 * position by core/eval_check.py; any divergence is a bug here. Uses double
 * throughout to match Python float semantics.
 */
#include "eval_data.h"

/* correct pawn-attack spans (match engine/concepts/mobility._pawn_attacks) */
#define WPAWN_ATK(p) ((((p)<<7)&~FILEBB[7]) | (((p)<<9)&~FILEBB[0]))
#define BPAWN_ATK(p) ((((p)>>7)&~FILEBB[0]) | (((p)>>9)&~FILEBB[7]))

static U64 FILEBB[8], ADJ_FILES[8];
static U64 PASSED_FRONT[2][64];
static U64 LIGHT_SQ;
/* PAWN_SPAN[c][sq]: where an ENEMY pawn could sit and, by advancing, ever
 * attack sq -- the adjacent files ahead of sq from the enemy's side. Empty
 * means the square can never be challenged by a pawn, which is what makes an
 * outpost an outpost. Note this is adjacent files ONLY, unlike PASSED_FRONT. */
static U64 PAWN_SPAN[2][64];
static U64 CENTER_BB, CENTER_FILES_BB, LONG_DIAG_BB;
/* SPACE_MASK[c]: the central files on that side's 2nd-4th ranks -- the squares
 * a minor piece wants to be able to reach. */
static U64 SPACE_MASK[2];
static int CMD_TBL[64];
static int e_init_done = 0;

static void eval_init(void){
    for(int f=0; f<8; f++){ U64 fm=0; for(int r=0;r<8;r++) fm|=1ULL<<(r*8+f); FILEBB[f]=fm; }
    for(int f=0; f<8; f++){ U64 a=0; if(f>0)a|=FILEBB[f-1]; if(f<7)a|=FILEBB[f+1]; ADJ_FILES[f]=a; }
    for(int sq=0; sq<64; sq++){
        int r=sq/8, f=sq%8;
        U64 span=FILEBB[f]|ADJ_FILES[f], wf=0, bf=0;
        for(int rr=r+1; rr<8; rr++) wf |= (span & (0xFFULL<<(rr*8)));
        for(int rr=r-1; rr>=0; rr--) bf |= (span & (0xFFULL<<(rr*8)));
        PASSED_FRONT[WHITE][sq]=wf; PASSED_FRONT[BLACK][sq]=bf;
        int cf=(3-f)>(f-4)?(3-f):(f-4); if(cf<0)cf=0;
        int cr=(3-r)>(r-4)?(3-r):(r-4); if(cr<0)cr=0;
        CMD_TBL[sq]=cf+cr;
    }
    LIGHT_SQ=0;
    for(int sq=0; sq<64; sq++){ int r=sq/8,f=sq%8; if((r+f)&1) LIGHT_SQ|=1ULL<<sq; }
    for(int sq=0; sq<64; sq++){
        int r=sq/8, f=sq%8; U64 wf=0, bf=0;
        for(int rr=r+1; rr<8; rr++) wf |= (ADJ_FILES[f] & (0xFFULL<<(rr*8)));
        for(int rr=r-1; rr>=0; rr--) bf |= (ADJ_FILES[f] & (0xFFULL<<(rr*8)));
        PAWN_SPAN[WHITE][sq]=wf; PAWN_SPAN[BLACK][sq]=bf;
    }
    CENTER_BB = (1ULL<<27)|(1ULL<<28)|(1ULL<<35)|(1ULL<<36);   /* d4 e4 d5 e5 */
    CENTER_FILES_BB = FILEBB[2]|FILEBB[3]|FILEBB[4]|FILEBB[5];
    LONG_DIAG_BB = 0;
    for(int sq=0; sq<64; sq++){ int r=sq/8,f=sq%8; if(f==r||f+r==7) LONG_DIAG_BB|=1ULL<<sq; }
    {   U64 r234=0, r567=0;
        for(int r=1;r<=3;r++) r234 |= 0xFFULL<<(r*8);   /* ranks 2-4 */
        for(int r=4;r<=6;r++) r567 |= 0xFFULL<<(r*8);   /* ranks 5-7 */
        SPACE_MASK[WHITE]=CENTER_FILES_BB & r234;
        SPACE_MASK[BLACK]=CENTER_FILES_BB & r567;
    }
    e_init_done=1;
}

/* A weight at the current game phase. Every weight is emitted by
 * core/gen_eval_data.py as a (middlegame, endgame) pair; where the two are
 * equal -- which is all of them until the tuner fills engine/weights.py's W_EG
 * -- both arguments are the same compile-time constant, so this folds away
 * entirely and the generated code is what it was before tapering existed.
 * `phase` is eval_core's local: 1.0 with all the pieces on, 0.0 at bare kings.
 *
 * Because it reads `phase`, a TAP is only a constant expression while the two
 * arguments are equal. Never use one to initialise a `static` -- that compiles
 * today and stops compiling the moment the tuner gives that weight a distinct
 * endgame value. Plain locals are fine; when the fold applies, gcc emits the
 * same constant load either way. */
#define TAP(MG, EG) ((MG) == (EG) ? (MG) : (phase) * (MG) + (1.0 - (phase)) * (EG))

/* Pawn hash: the pawn-only half of the pawn evaluation, keyed by the two pawn
 * bitboards and stored as an (mg, eg) pair so the entry does not depend on the
 * phase. Per-thread, because a shared table would need locking or a torn-read
 * scheme, and a torn read would corrupt the evaluation somewhere eval_check --
 * single-threaded -- could never see it. A zeroed entry reads as "no pawns, no
 * passers, score zero", which is the right answer for a pawnless position. */
#define PH_BITS 14
#define PH_SIZE (1<<PH_BITS)
#define PH_MASK (PH_SIZE-1)
typedef struct { U64 wp, bp, pw, pb; double mg, eg; } PHEntry;
static _Thread_local PHEntry PH[PH_SIZE];

double eval_core(U64 bb[2][6], int side){
    if(!e_init_done) eval_init();
    U64 occ[2];
    occ[WHITE]=bb[WHITE][0]|bb[WHITE][1]|bb[WHITE][2]|bb[WHITE][3]|bb[WHITE][4]|bb[WHITE][5];
    occ[BLACK]=bb[BLACK][0]|bb[BLACK][1]|bb[BLACK][2]|bb[BLACK][3]|bb[BLACK][4]|bb[BLACK][5];
    U64 all=occ[WHITE]|occ[BLACK];

    int ph = popcnt(bb[WHITE][KNIGHT]|bb[BLACK][KNIGHT]|bb[WHITE][BISHOP]|bb[BLACK][BISHOP])
           + 2*popcnt(bb[WHITE][ROOK]|bb[BLACK][ROOK])
           + 4*popcnt(bb[WHITE][QUEEN]|bb[BLACK][QUEEN]);
    double phase = ph>=24 ? 1.0 : (double)ph/24.0;
    double s=0.0;

    /* one pass of slider/knight attacks per piece: king attack, mobility and
     * threats all need them, and were each recomputing the magic lookups.
     * Iteration order matches the per-section loops (c, then piece type,
     * then lsb), so consumers see identical sequences — byte-identical. */
    U64 pat[2][6][10]; int pna[2][6];
    for(int c=0;c<2;c++)
        for(int p=KNIGHT;p<=QUEEN;p++){
            int n=0; U64 x=bb[c][p];
            while(x){ int sq=lsb(x); x&=x-1;
                U64 atk;
                if(p==KNIGHT) atk=KNIGHT_ATK[sq];
                else if(p==BISHOP) atk=bishop_atk(sq,all);
                else if(p==ROOK) atk=rook_atk(sq,all);
                else atk=bishop_atk(sq,all)|rook_atk(sq,all);
                pat[c][p][n++]=atk;
            }
            pna[c][p]=n;
        }

    /* material */
    static const double MATV[5]={W_MATERIAL_PAWN,W_MATERIAL_KNIGHT,W_MATERIAL_BISHOP,W_MATERIAL_ROOK,W_MATERIAL_QUEEN};
    for(int p=0;p<5;p++) s += MATV[p]*(popcnt(bb[WHITE][p])-popcnt(bb[BLACK][p]));

    /* piece placement (PST) */
    const double PSTSCALE[6]={TAP(W_PST_PAWN_MG, W_PST_PAWN_EG),TAP(W_PST_KNIGHT_MG, W_PST_KNIGHT_EG),TAP(W_PST_BISHOP_MG, W_PST_BISHOP_EG),TAP(W_PST_ROOK_MG, W_PST_ROOK_EG),TAP(W_PST_QUEEN_MG, W_PST_QUEEN_EG),TAP(W_PST_KING_MG, W_PST_KING_EG)};
    for(int c=0;c<2;c++){
        int flip=c==WHITE?0:56, sign=c==WHITE?1:-1;
        for(int p=0;p<6;p++){
            U64 x=bb[c][p];
            while(x){ int sq=lsb(x); x&=x-1; int i=sq^flip; double v;
                if(p==PAWN) v=phase*PST_PAWN_MG[i]+(1-phase)*PST_PAWN_EG[i];
                else if(p==KING) v=phase*PST_KING_MG[i]+(1-phase)*PST_KING_EG[i];
                else if(p==KNIGHT) v=PST_KNIGHT[i];
                else if(p==BISHOP) v=PST_BISHOP[i];
                else if(p==ROOK) v=PST_ROOK[i];
                else v=PST_QUEEN[i];
                s += sign*PSTSCALE[p]*v;
            }
        }
    }

    /* pawn structure.
     *
     * Split in two. Everything that depends only on the pawn bitboards --
     * doubled, isolated, backward, connected, and the passer sets -- is cached
     * in a per-thread pawn hash as an (mg, eg) pair, so the entry is
     * phase-independent and survives every capture that does not take a pawn.
     * The rest needs more than pawns (occupancy for a blocked passer, the kings
     * for the race, the rooks for Tarrasch) and runs over the passers only.
     *
     * Sums in a different order than the Python reference, so the two agree to
     * float reassociation (~1e-12cp) rather than bit-for-bit; eval_check still
     * reports 0.000000 with zero mismatches. */
    double passed_scale = phase + (1-phase)*TAP(W_PAWN_PASSED_EG_SCALE_MG, W_PAWN_PASSED_EG_SCALE_EG);
    double kd_w = TAP(W_PAWN_PASSER_KING_DIST_MG, W_PAWN_PASSER_KING_DIST_EG)*(1-phase);  /* king race, endgame-scaled */

    U64 wpawns=bb[WHITE][PAWN], bpawns=bb[BLACK][PAWN];
    U64 passers_of[2];
    double pmg, peg;
    {
        U64 k = wpawns*0x9E3779B97F4A7C15ULL ^ bpawns*0xC2B2AE3D27D4EB4FULL;
        k ^= k>>29; k *= 0xBF58476D1CE4E5B9ULL; k ^= k>>32;
        PHEntry *pe = &PH[k & PH_MASK];
        if(pe->wp==wpawns && pe->bp==bpawns){
            passers_of[WHITE]=pe->pw; passers_of[BLACK]=pe->pb;
            pmg=pe->mg; peg=pe->eg;
        } else {
            double mg=0.0, eg=0.0;
            for(int c=0;c<2;c++){
                int sign=c==WHITE?1:-1;
                U64 ownp=bb[c][PAWN], enp=bb[!c][PAWN];
                U64 passers=0;
                { U64 x=ownp; while(x){ int sq=lsb(x); x&=x-1;
                    if(!(enp&PASSED_FRONT[c][sq])) passers|=1ULL<<sq; } }
                passers_of[c]=passers;
                for(int f=0; f<8; f++){
                    U64 onfile=ownp&FILEBB[f]; int cnt=popcnt(onfile);
                    if(!cnt) continue;
                    if(cnt>1){ mg -= sign*W_PAWN_DOUBLED_MG*(cnt-1);
                               eg -= sign*W_PAWN_DOUBLED_EG*(cnt-1); }
                    if(!(ownp&ADJ_FILES[f])){ mg -= sign*W_PAWN_ISOLATED_MG*cnt;
                                              eg -= sign*W_PAWN_ISOLATED_EG*cnt; }
                }
            }
            /* backward pawns (mirrors engine/concepts/backward_pawns.py): a pawn
             * whose adjacent-file friends have all advanced past it and whose stop
             * square an enemy pawn covers -- worse on a half-open file. */
            for(int c=0;c<2;c++){
                int sign=c==WHITE?1:-1;
                U64 own=bb[c][PAWN], enemy=bb[!c][PAWN];
                U64 enemy_atk = c==WHITE ? BPAWN_ATK(enemy) : WPAWN_ATK(enemy);
                U64 x=own;
                while(x){ int sq=lsb(x); x&=x-1; int f=sq%8, r=sq/8;
                    U64 adj = (f>0?FILEBB[f-1]:0) | (f<7?FILEBB[f+1]:0);
                    U64 own_adj = own & adj;
                    if(!own_adj) continue;                     /* isolated, not backward */
                    U64 support; int stop;
                    if(c==WHITE){ support = adj & ((1ULL<<((r+1)*8))-1); stop=sq+8; }
                    else        { support = adj & ~((1ULL<<(r*8))-1);    stop=sq-8; }
                    if(own_adj & support) continue;            /* a neighbour is level/behind */
                    if(stop<0||stop>63) continue;
                    if(!(enemy_atk & (1ULL<<stop))) continue;  /* can advance safely */
                    int half_open = !(enemy & FILEBB[f]);
                    mg -= sign * W_PAWN_BACKWARD_MG * (half_open?2:1);
                    eg -= sign * W_PAWN_BACKWARD_EG * (half_open?2:1);
                }
            }
            /* connected pawns (mirrors engine/concepts/connected_pawns.py):
             * phalanx or supported, bonus x(rank-3) so only advanced duos score. */
            for(int c=0;c<2;c++){
                int sign=c==WHITE?1:-1; U64 own=bb[c][PAWN];
                U64 x=own;
                while(x){ int sq=lsb(x); x&=x-1; int f=sq%8, r=sq/8;
                    int rel = c==WHITE ? r : 7-r, adv = rel-2;
                    if(adv<=0) continue;
                    int back = c==WHITE ? r-1 : r+1, conn=0;
                    for(int af=f-1; af<=f+1; af+=2){
                        if(af<0||af>7) continue;
                        if(own & (1ULL<<(r*8+af))) conn=1;                          /* phalanx */
                        if(back>=0 && back<8 && (own & (1ULL<<(back*8+af)))) conn=1; /* supported */
                    }
                    if(conn){ mg += sign * W_PAWN_CONNECTED_MG * adv;
                              eg += sign * W_PAWN_CONNECTED_EG * adv; }
                }
            }
            pmg=mg; peg=eg;
            pe->wp=wpawns; pe->bp=bpawns;
            pe->pw=passers_of[WHITE]; pe->pb=passers_of[BLACK];
            pe->mg=mg; pe->eg=eg;
        }
    }
    s += phase*pmg + (1.0-phase)*peg;

    /* Full attack union per side -- pieces, pawns and king -- mirroring
     * engine/context.py's attacked_by. Measured at -0.64% NPS, which is what
     * made the passer path terms below affordable. */
    U64 au[2];
    for(int c=0;c<2;c++){
        U64 a = c==WHITE ? WPAWN_ATK(bb[WHITE][PAWN]) : BPAWN_ATK(bb[BLACK][PAWN]);
        for(int pp=KNIGHT;pp<=QUEEN;pp++)
            for(int i=0;i<pna[c][pp];i++) a |= pat[c][pp][i];
        if(bb[c][KING]) a |= KING_ATK[lsb(bb[c][KING])];
        au[c] = a;
    }

    /* passer terms that need more than pawns -- over the passer set only */
    for(int c=0;c<2;c++){
        int sign=c==WHITE?1:-1;
        U64 passers=passers_of[c];
        U64 x=passers;
        while(x){ int sq=lsb(x); x&=x-1;
            int f=sq%8, r=sq/8, rel=c==WHITE?r:7-r, front=c==WHITE?sq+8:sq-8;
            /* Can the passer actually run? A pawn on the sixth whose road is
             * covered by enemy pieces is not the asset its rank suggests.
             * Mirrors _path_terms() in pawn_structure.py, same order. */
            U64 path = c==WHITE ? (FILEBB[f] & ~((1ULL<<(sq+1))-1))
                                : (FILEBB[f] & ((1ULL<<sq)-1));
            if(path){
                if(!(path & au[!c]))
                    s += sign*TAP(W_PAWN_PATH_CLEAR_MG, W_PAWN_PATH_CLEAR_EG)*rel*passed_scale;
                if(!(path & ~au[c]))
                    s += sign*TAP(W_PAWN_PATH_DEFENDED_MG, W_PAWN_PATH_DEFENDED_EG)*rel*passed_scale;
                if(front>=0 && front<64 && ((au[!c]>>front)&1ULL))
                    s -= sign*TAP(W_PAWN_PATH_ATTACKED_MG, W_PAWN_PATH_ATTACKED_EG)*rel*passed_scale;
            }
            double mult=(front>=0&&front<64&&(all&(1ULL<<front)))?TAP(W_PAWN_BLOCKED_PASSER_MG, W_PAWN_BLOCKED_PASSER_EG):1.0;
            s += sign*PASSED_BONUS[rel]*TAP(W_PAWN_PASSED_SCALE_MG, W_PAWN_PASSED_SCALE_EG)*mult*passed_scale;
            if(passers&ADJ_FILES[f])
                s += sign*TAP(W_PAWN_CONNECTED_PASSER_MG, W_PAWN_CONNECTED_PASSER_EG)*mult*passed_scale;
            if(kd_w!=0.0 && front>=0 && front<64){
                /* mirror of pawn_structure.py: escort your passer /
                 * catch theirs (Chebyshev distance to the front sq) */
                int ok=lsb(bb[c][KING]), ek=lsb(bb[!c][KING]);
                int dfo=ok%8-front%8, dro=ok/8-front/8;
                int dfe=ek%8-front%8, dre=ek/8-front/8;
                if(dfo<0)dfo=-dfo; if(dro<0)dro=-dro;
                if(dfe<0)dfe=-dfe; if(dre<0)dre=-dre;
                int dok=dfo>dro?dfo:dro, dek=dfe>dre?dfe:dre;
                s += sign*kd_w*(dek-dok);
            }
            /* rook behind the passer (Tarrasch); mirrors pawn_structure._rook_behind:
             * own rook supports (bonus), enemy rook attacks it from behind (penalty) */
            { U64 behind = c==WHITE ? ((1ULL<<(r*8))-1) : ~((1ULL<<((r+1)*8))-1);
              if((bb[c][ROOK]&FILEBB[f]) & behind)  s += sign*TAP(W_PAWN_ROOK_BEHIND_PASSER_MG, W_PAWN_ROOK_BEHIND_PASSER_EG)*passed_scale;
              if((bb[!c][ROOK]&FILEBB[f]) & behind) s -= sign*TAP(W_PAWN_ROOK_BEHIND_ENEMY_PASSER_MG, W_PAWN_ROOK_BEHIND_ENEMY_PASSER_EG)*passed_scale; }
        }
    }

    /* king safety */
    if(phase>=0.05){
        for(int c=0;c<2;c++){
            int sign=c==WHITE?1:-1, ksq=lsb(bb[c][KING]), kf=ksq%8, kr=ksq/8;
            U64 ownp=bb[c][PAWN], enp=bb[!c][PAWN];
            int missing=0, openf=0;
            for(int f=kf-1; f<=kf+1; f++){
                if(f<0||f>7) continue;
                int shielded=0;
                int r1=c==WHITE?kr+1:kr-1, r2=c==WHITE?kr+2:kr-2;
                if(r1>=0&&r1<8 && (ownp&(1ULL<<(r1*8+f)))) shielded=1;
                if(r2>=0&&r2<8 && (ownp&(1ULL<<(r2*8+f)))) shielded=1;
                if(!shielded) missing++;
                if(!(ownp&FILEBB[f]) && !(enp&FILEBB[f])) openf++;
            }
            s -= sign*(TAP(W_KING_SHIELD_GAP_MG, W_KING_SHIELD_GAP_EG)*missing + TAP(W_KING_OPEN_FILE_MG, W_KING_OPEN_FILE_EG)*openf)*phase;
        }
    }

    /* king attack */
    if(phase>=0.05){
        static const int UNIT[6]={0,2,2,3,5,0};
        for(int c=0;c<2;c++){
            int sign=c==WHITE?1:-1, eksq=lsb(bb[!c][KING]);
            U64 zone=KING_ATK[eksq]|(1ULL<<eksq);
            int units=0, attackers=0;
            for(int p=KNIGHT;p<=QUEEN;p++)
                for(int i=0;i<pna[c][p];i++){
                    int hits=popcnt(pat[c][p][i]&zone);
                    if(hits){ units+=UNIT[p]*hits; attackers++; }
                }
            /* The queen is the piece that mates, so an attack without one is a
             * different animal. Expressed as a discount OFF full price, so a
             * weight of zero reproduces the old behaviour exactly. */
            double disc = bb[c][QUEEN] ? 1.0 : 1.0 -
                TAP(W_KATTACK_QUEENLESS_DISCOUNT_MG, W_KATTACK_QUEENLESS_DISCOUNT_EG);
            /* Gated on a real attack existing: partly chess (a safe check
             * matters most when pieces are already pressing) and partly cost
             * -- ungated this scan measured -4.62% NPS, about -4.6 Elo of lost
             * depth against +3.8 Elo of knowledge, a net loss. */
            if(attackers>=2){
                /* danger by units, from a fitted curve rather than a forced
                 * quadratic; mirrors _danger() in king_attack.py */
                { int u = units < KD_MAX ? units : KD_MAX-1;
                  s += sign*TAP(KD_MG[u], KD_EG[u])*phase*disc; }

                /* Safe checks: a check the defender cannot answer by capturing the
                 * checker, i.e. the landing square is covered by no enemy piece
                 * other than the king itself. Volume of pressure says nothing about
                 * whether an attack can actually finish; this does. Mirrors
                 * king_attack.py term for term and in the same order. */
                U64 by[6]={0,0,0,0,0,0};
                for(int p=KNIGHT;p<=QUEEN;p++)
                    for(int i=0;i<pna[c][p];i++) by[p]|=pat[c][p][i];
                U64 defended = c==WHITE ? BPAWN_ATK(bb[BLACK][PAWN])
                                        : WPAWN_ATK(bb[WHITE][PAWN]);
                for(int p=KNIGHT;p<=QUEEN;p++)
                    for(int i=0;i<pna[!c][p];i++) defended|=pat[!c][p][i];
                U64 safesq = ~defended & ~occ[c];
                U64 dfrom = bishop_atk(eksq,all), lfrom = rook_atk(eksq,all);
                int nck = popcnt(by[KNIGHT] & KNIGHT_ATK[eksq] & safesq);
                int ncb = popcnt(by[BISHOP] & dfrom & safesq);
                int ncr = popcnt(by[ROOK] & lfrom & safesq);
                int ncq = popcnt(by[QUEEN] & (dfrom|lfrom) & safesq);
                if(nck) s += sign*TAP(W_KATTACK_CHECK_KNIGHT_MG, W_KATTACK_CHECK_KNIGHT_EG)*nck*phase*disc;
                if(ncb) s += sign*TAP(W_KATTACK_CHECK_BISHOP_MG, W_KATTACK_CHECK_BISHOP_EG)*ncb*phase*disc;
                if(ncr) s += sign*TAP(W_KATTACK_CHECK_ROOK_MG, W_KATTACK_CHECK_ROOK_EG)*ncr*phase*disc;
                if(ncq) s += sign*TAP(W_KATTACK_CHECK_QUEEN_MG, W_KATTACK_CHECK_QUEEN_EG)*ncq*phase*disc;
                /* king-zone squares the attacker hits that only the king defends --
                 * the squares a mate actually lands on */
                int weak = popcnt(zone & ~defended &
                                  (by[KNIGHT]|by[BISHOP]|by[ROOK]|by[QUEEN]));
                if(weak) s += sign*TAP(W_KATTACK_WEAK_ZONE_MG, W_KATTACK_WEAK_ZONE_EG)*weak*phase*disc;
            }
            /* proximity gradient (mirrors king_attack.py): pieces closing in
             * on the king matter before they attack the zone */
            int prox=0;
            for(int p=KNIGHT;p<=QUEEN;p++){
                U64 x=bb[c][p];
                while(x){ int sq=lsb(x); x&=x-1;
                    int df=sq%8-eksq%8, dr=sq/8-eksq/8;
                    if(df<0)df=-df; if(dr<0)dr=-dr;
                    int d=df>dr?df:dr;
                    if(d<4) prox += UNIT[p]*(4-d);
                }
            }
            if(prox) s += sign*TAP(W_KATTACK_PROXIMITY_MG, W_KATTACK_PROXIMITY_EG)*prox*phase;
        }
    }

    /* mobility (safe squares) */
    double MOBW[6]={0,TAP(W_MOB_KNIGHT_MG, W_MOB_KNIGHT_EG),TAP(W_MOB_BISHOP_MG, W_MOB_BISHOP_EG),TAP(W_MOB_ROOK_MG, W_MOB_ROOK_EG),TAP(W_MOB_QUEEN_MG, W_MOB_QUEEN_EG),0};
    static const int TYP[6]={0,4,6,7,13,0};
    for(int c=0;c<2;c++){
        int sign=c==WHITE?1:-1; U64 own=occ[c];
        U64 unsafe = c==WHITE ? BPAWN_ATK(bb[BLACK][PAWN]) : WPAWN_ATK(bb[WHITE][PAWN]);
        for(int p=KNIGHT;p<=QUEEN;p++)
            for(int i=0;i<pna[c][p];i++){
                int n=popcnt(pat[c][p][i]&~own&~unsafe);
                s += sign*MOBW[p]*(n-TYP[p]);
            }
    }

    /* piece activity */
    for(int c=0;c<2;c++){
        int sign=c==WHITE?1:-1;
        if(popcnt(bb[c][BISHOP])>=2) s += sign*TAP(W_ACT_BISHOP_PAIR_MG, W_ACT_BISHOP_PAIR_EG);
        U64 ownp=bb[c][PAWN], enp=bb[!c][PAWN];
        int seventh=c==WHITE?6:1; U64 rooks=bb[c][ROOK];
        while(rooks){ int sq=lsb(rooks); rooks&=rooks-1; int f=sq%8;
            if(!(ownp&FILEBB[f])) s += sign*(!(enp&FILEBB[f])?TAP(W_ACT_ROOK_OPEN_MG, W_ACT_ROOK_OPEN_EG):TAP(W_ACT_ROOK_SEMI_MG, W_ACT_ROOK_SEMI_EG));
            if(sq/8==seventh) s += sign*TAP(W_ACT_ROOK_SEVENTH_MG, W_ACT_ROOK_SEVENTH_EG);
        }
    }

    /* imbalance and space: what the piece count alone cannot say.
     * Mirrors engine/concepts/imbalance.py -- colour outer, and within a colour
     * the order rook_flat, knight_pawns, rook_pawns, rook_pair, knight_pair,
     * space, so the float sum matches term for term. Sits between activity and
     * minor pieces because that is where Imbalance() sits in the registry. */
    for(int c=0;c<2;c++){
        int sign=c==WHITE?1:-1;
        int np=popcnt(bb[c][PAWN]), nn=popcnt(bb[c][KNIGHT]), nr=popcnt(bb[c][ROOK]);
        if(nr) s += sign*TAP(W_IMBALANCE_ROOK_FLAT_MG, W_IMBALANCE_ROOK_FLAT_EG)*nr;
        if(nn && np!=5) s += sign*TAP(W_IMBALANCE_KNIGHT_PAWNS_MG, W_IMBALANCE_KNIGHT_PAWNS_EG)*nn*(np-5);
        if(nr && np!=5) s -= sign*TAP(W_IMBALANCE_ROOK_PAWNS_MG, W_IMBALANCE_ROOK_PAWNS_EG)*nr*(np-5);
        if(nr>=2) s -= sign*TAP(W_IMBALANCE_ROOK_PAIR_MG, W_IMBALANCE_ROOK_PAIR_EG);
        if(nn>=2) s -= sign*TAP(W_IMBALANCE_KNIGHT_PAIR_MG, W_IMBALANCE_KNIGHT_PAIR_EG);
        if(phase > 0.4){
            U64 ownp=bb[c][PAWN];
            U64 unsafe = c==WHITE ? BPAWN_ATK(bb[BLACK][PAWN]) : WPAWN_ATK(bb[WHITE][PAWN]);
            U64 safe = SPACE_MASK[c] & ~ownp & ~unsafe;
            U64 behind = ownp;
            if(c==WHITE){ behind |= behind>>8; behind |= behind>>16; }
            else        { behind |= behind<<8; behind |= behind<<16; }
            /* the defender's whole attack union, king and pawns included */
            U64 theirs = c==WHITE ? BPAWN_ATK(bb[BLACK][PAWN]) : WPAWN_ATK(bb[WHITE][PAWN]);
            for(int p=KNIGHT;p<=QUEEN;p++)
                for(int i=0;i<pna[!c][p];i++) theirs |= pat[!c][p][i];
            if(bb[!c][KING]) theirs |= KING_ATK[lsb(bb[!c][KING])];
            int bonus = popcnt(safe) + popcnt(behind & safe & ~theirs);
            int pieces = popcnt(occ[c]);
            int weight = pieces-3; if(weight<0) weight=0;
            if(bonus && weight)
                s += sign*TAP(W_SPACE_SCALE_MG, W_SPACE_SCALE_EG)*bonus*weight*weight/16.0;
        }
    }

    /* minor pieces: outposts, minors behind pawns, bad bishops, long diagonals.
     * Mirrors engine/concepts/minor_pieces.py — colour, then KNIGHT before
     * BISHOP, then squares LSB-first, and within a piece: outpost, behind pawn,
     * bad bishop, long diagonal. Same order, same float sum. */
    for(int c=0;c<2;c++){
        int sign=c==WHITE?1:-1;
        U64 ownp=bb[c][PAWN], enp=bb[!c][PAWN], allp=ownp|enp;
        U64 pawnatk = c==WHITE ? WPAWN_ATK(ownp) : BPAWN_ATK(ownp);
        int up = c==WHITE ? 8 : -8;
        U64 blocked = ownp & (c==WHITE ? (all>>8) : (all<<8));
        int blocked_centre = popcnt(blocked & CENTER_FILES_BB);
        for(int p=KNIGHT;p<=BISHOP;p++){
            U64 x=bb[c][p];
            while(x){ int sq=lsb(x); x&=x-1;
                int r=sq/8, f=sq%8;
                int rel = c==WHITE ? r : 7-r;
                /* knights only: the tuner drove the bishop outpost weight to
                 * exactly zero, which is chess -- a short-range piece needs a
                 * permanent square, a bishop already radiates from anywhere. */
                if(p==KNIGHT && rel>=3 && rel<=5 && ((pawnatk>>sq)&1) && !(PAWN_SPAN[c][sq]&enp))
                    s += sign*TAP(W_MINOR_OUTPOST_KNIGHT_MG, W_MINOR_OUTPOST_KNIGHT_EG);
                int ahead = sq + up;
                if(rel<4 && ahead>=0 && ahead<64 && ((allp>>ahead)&1))
                    s += sign*TAP(W_MINOR_BEHIND_PAWN_MG, W_MINOR_BEHIND_PAWN_EG);
                if(p==BISHOP){
                    U64 same = ((r+f)&1) ? LIGHT_SQ : ~LIGHT_SQ;
                    int n = popcnt(ownp & same);
                    if(n) s -= sign*TAP(W_MINOR_BISHOP_PAWNS_MG, W_MINOR_BISHOP_PAWNS_EG)
                                    *n*(1+blocked_centre);
                    if(((LONG_DIAG_BB>>sq)&1) && popcnt(bishop_atk(sq,allp)&CENTER_BB)>1)
                        s += sign*TAP(W_MINOR_LONG_DIAGONAL_MG, W_MINOR_LONG_DIAGONAL_EG);
                }
            }
        }
    }

    /* tempo */
    s += (side==WHITE?1:-1)*TAP(W_TEMPO_MG, W_TEMPO_EG);

    /* threats: pieces pressured by a lower-value attacker, plus hanging pieces.
     * Mirrors engine/concepts/threats.py — per enemy piece, add the pawn / minor
     * / rook / hanging terms in THAT order so the float sum matches byte-for-byte. */
    {
        U64 atkby[2], pawnatk[2], minoratk[2], rookatk[2];
        for(int c=0;c<2;c++){
            U64 pa = c==WHITE ? WPAWN_ATK(bb[WHITE][PAWN]) : BPAWN_ATK(bb[BLACK][PAWN]);
            U64 ma=0, ra=0, qa=0;
            for(int i=0;i<pna[c][KNIGHT];i++) ma|=pat[c][KNIGHT][i];
            for(int i=0;i<pna[c][BISHOP];i++) ma|=pat[c][BISHOP][i];
            for(int i=0;i<pna[c][ROOK];i++)   ra|=pat[c][ROOK][i];
            for(int i=0;i<pna[c][QUEEN];i++)  qa|=pat[c][QUEEN][i];
            pawnatk[c]=pa; minoratk[c]=ma; rookatk[c]=ra;
            atkby[c] = pa|ma|ra|qa|KING_ATK[lsb(bb[c][KING])];
        }
        static const double PV[6]={100,320,330,500,900,0};
        for(int c=0;c<2;c++){
            int sign=c==WHITE?1:-1;
            /* the side to move can execute its threats now, so scale them up */
            double w = (c==side) ? (1.0+TAP(W_THREAT_INITIATIVE_MG, W_THREAT_INITIATIVE_EG)) : 1.0;
            /* value by (kind, victim) from the fitted table, not weight x victim
             * value; mirrors THREAT_MG/THREAT_EG in threats.py. A lookup
             * replaces the multiply, so the extra freedom is free. */
            for(int p=0;p<5;p++){            /* PAWN..QUEEN (0-indexed here) */
                U64 x=bb[!c][p];
                while(x){ int sq=lsb(x); x&=x-1; U64 m=1ULL<<sq;
                    if((pawnatk[c]&m)  && p>=KNIGHT) s += sign*w*TAP(THR_MG[0*5+p], THR_EG[0*5+p]);
                    if((minoratk[c]&m) && p>=ROOK)   s += sign*w*TAP(THR_MG[1*5+p], THR_EG[1*5+p]);
                    if((rookatk[c]&m)  && p==QUEEN)  s += sign*w*TAP(THR_MG[2*5+p], THR_EG[2*5+p]);
                    if((atkby[c]&m) && !(atkby[!c]&m)) s += sign*w*TAP(THR_MG[3*5+p], THR_EG[3*5+p]);
                }
            }
        }
    }

    /* mating drive (+ s18 mop-up: pawnless defender dominated by >= a rook
     * gets the drive gradient at half strength — KR vs KB, KQ vs KN, ...) */
    for(int win=0; win<2; win++){
        int lose=!win, sign=win==WHITE?1:-1;
        U64 lp=bb[lose][PAWN];
        U64 lpieces=bb[lose][KNIGHT]|bb[lose][BISHOP]|bb[lose][ROOK]|bb[lose][QUEEN];
        int full=0, mopup=0;
        if(!lp && !lpieces)
            full=(bb[win][QUEEN]||bb[win][ROOK])||(popcnt(bb[win][KNIGHT])+popcnt(bb[win][BISHOP])>=2);
        else if(!lp){
            int lmat=320*popcnt(bb[lose][KNIGHT])+330*popcnt(bb[lose][BISHOP])
                    +500*popcnt(bb[lose][ROOK])+900*popcnt(bb[lose][QUEEN]);
            int wmat=320*popcnt(bb[win][KNIGHT])+330*popcnt(bb[win][BISHOP])
                    +500*popcnt(bb[win][ROOK])+900*popcnt(bb[win][QUEEN]);
            mopup=(wmat-lmat)>=500;
        }
        if(!full && !mopup) continue;
        double scale=full?1.0:0.5;
        int lk=lsb(bb[lose][KING]), wk=lsb(bb[win][KING]);
        int md=abs((lk%8)-(wk%8))+abs((lk/8)-(wk/8));
        s += sign*(TAP(W_MATE_DRIVE_CORNER_MG, W_MATE_DRIVE_CORNER_EG)*CMD_TBL[lk]*scale + TAP(W_MATE_DRIVE_KING_PROX_MG, W_MATE_DRIVE_KING_PROX_EG)*(14-md)*scale);
    }

    /* opposite-colored-bishop drawishness (multiplicative modifier; mirrors
     * engine/concepts/opposite_bishops.py). Pure OCB ending -> damp the eval. */
    if(popcnt(bb[WHITE][BISHOP])==1 && popcnt(bb[BLACK][BISHOP])==1
       && !bb[WHITE][KNIGHT] && !bb[BLACK][KNIGHT]
       && !bb[WHITE][ROOK]   && !bb[BLACK][ROOK]
       && !bb[WHITE][QUEEN]  && !bb[BLACK][QUEEN]){
        int wl = (bb[WHITE][BISHOP]&LIGHT_SQ)!=0;
        int bl = (bb[BLACK][BISHOP]&LIGHT_SQ)!=0;
        if(wl!=bl) s *= W_OCB_DRAW_SCALE;
    }

    /* Endgame drawishness (multiplicative; mirrors engine/concepts/
     * endgame_scale.py, and applied AFTER the opposite-bishop modifier because
     * ALL_MODIFIERS runs in that order). Some endings are drawn however the
     * concept sum adds up, and stay drawn for longer than any search horizon,
     * so the verdict has to be corrected here rather than found. */
    {
        double npw = W_MATERIAL_KNIGHT*popcnt(bb[WHITE][KNIGHT])
                   + W_MATERIAL_BISHOP*popcnt(bb[WHITE][BISHOP])
                   + W_MATERIAL_ROOK  *popcnt(bb[WHITE][ROOK])
                   + W_MATERIAL_QUEEN *popcnt(bb[WHITE][QUEEN]);
        double npb = W_MATERIAL_KNIGHT*popcnt(bb[BLACK][KNIGHT])
                   + W_MATERIAL_BISHOP*popcnt(bb[BLACK][BISHOP])
                   + W_MATERIAL_ROOK  *popcnt(bb[BLACK][ROOK])
                   + W_MATERIAL_QUEEN *popcnt(bb[BLACK][QUEEN]);
        if(npw != npb){
            int strong = npw > npb ? WHITE : BLACK;
            double diff = npw > npb ? npw-npb : npb-npw;
            /* A small edge with NO pawns anywhere cannot be converted: nothing
             * to promote and not enough to force mate. Both sides must be
             * pawnless -- requiring it only of the stronger side scored a
             * bishop against three pawns as drawish, which cost 0.198% on
             * decisive games until it was tightened. */
            if(!bb[WHITE][PAWN] && !bb[BLACK][PAWN] && diff < W_MATERIAL_ROOK)
                s *= 1.0 - W_SCALE_NO_PAWNS;
            /* Wrong rook pawn: bishop plus rook pawns on one wing only, bishop
             * not covering the promotion square, defending king sitting on it. */
            U64 sp = bb[strong][PAWN];
            if(sp && popcnt(bb[strong][BISHOP])==1 && !bb[strong][KNIGHT]
               && !bb[strong][ROOK] && !bb[strong][QUEEN]){
                int only_a = (sp & ~FILEBB[0])==0, only_h = (sp & ~FILEBB[7])==0;
                if(only_a || only_h){
                    int f = only_a ? 0 : 7;
                    int promo = (strong==WHITE ? 56 : 0) + f;
                    int bl2 = (bb[strong][BISHOP]&LIGHT_SQ)!=0;
                    int pl2 = ((1ULL<<promo)&LIGHT_SQ)!=0;
                    int dk = lsb(bb[!strong][KING]);
                    int df = dk%8-promo%8, dr = dk/8-promo/8;
                    if(df<0)df=-df; if(dr<0)dr=-dr;
                    if(bl2!=pl2 && (df>dr?df:dr)<=1) s *= 1.0 - W_SCALE_WRONG_BISHOP;
                }
            }
        }
    }

    return s;
}

/* C API: eval a FEN, White's perspective (for cross-checking) */
double c_eval(const char *fen){
    if(!g_init){ init_tables(); g_init=1; }
    Board b; if(set_fen(&b,fen)) return 0;
    return eval_core(b.bb, b.side);
}
