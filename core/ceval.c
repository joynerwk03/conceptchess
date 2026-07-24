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
    e_init_done=1;
}

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
    static const double PSTSCALE[6]={W_PST_PAWN,W_PST_KNIGHT,W_PST_BISHOP,W_PST_ROOK,W_PST_QUEEN,W_PST_KING};
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

    /* pawn structure */
    double passed_scale = phase + (1-phase)*W_PAWN_PASSED_EG_SCALE;
    double kd_w = W_PAWN_PASSER_KING_DIST*(1-phase);  /* king race, endgame-scaled */
    for(int c=0;c<2;c++){
        int sign=c==WHITE?1:-1;
        U64 ownp=bb[c][PAWN], enp=bb[!c][PAWN];
        /* passer set for this color (mirrors pawn_structure.py's pfiles) */
        U64 passers=0;
        { U64 x=ownp; while(x){ int sq=lsb(x); x&=x-1;
            if(!(enp&PASSED_FRONT[c][sq])) passers|=1ULL<<sq; } }
        for(int f=0; f<8; f++){
            U64 onfile=ownp&FILEBB[f]; int cnt=popcnt(onfile);
            if(!cnt) continue;
            if(cnt>1) s -= sign*W_PAWN_DOUBLED*(cnt-1);
            if(!(ownp&ADJ_FILES[f])) s -= sign*W_PAWN_ISOLATED*cnt;
            U64 x=onfile;
            while(x){ int sq=lsb(x); x&=x-1;
                if(!(enp&PASSED_FRONT[c][sq])){
                    int r=sq/8, rel=c==WHITE?r:7-r, front=c==WHITE?sq+8:sq-8;
                    double mult=(front>=0&&front<64&&(all&(1ULL<<front)))?W_PAWN_BLOCKED_PASSER:1.0;
                    s += sign*PASSED_BONUS[rel]*W_PAWN_PASSED_SCALE*mult*passed_scale;
                    if(passers&ADJ_FILES[f])
                        s += sign*W_PAWN_CONNECTED_PASSER*mult*passed_scale;
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
                }
            }
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
            s -= sign*(W_KING_SHIELD_GAP*missing + W_KING_OPEN_FILE*openf)*phase;
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
            if(attackers>=2) s += sign*W_KATTACK_SCALE*units*units/10.0*phase;
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
            if(prox) s += sign*W_KATTACK_PROXIMITY*prox*phase;
        }
    }

    /* mobility (safe squares) */
    double MOBW[6]={0,W_MOB_KNIGHT,W_MOB_BISHOP,W_MOB_ROOK,W_MOB_QUEEN,0};
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
        if(popcnt(bb[c][BISHOP])>=2) s += sign*W_ACT_BISHOP_PAIR;
        U64 ownp=bb[c][PAWN], enp=bb[!c][PAWN];
        int seventh=c==WHITE?6:1; U64 rooks=bb[c][ROOK];
        while(rooks){ int sq=lsb(rooks); rooks&=rooks-1; int f=sq%8;
            if(!(ownp&FILEBB[f])) s += sign*(!(enp&FILEBB[f])?W_ACT_ROOK_OPEN:W_ACT_ROOK_SEMI);
            if(sq/8==seventh) s += sign*W_ACT_ROOK_SEVENTH;
        }
    }

    /* tempo */
    s += (side==WHITE?1:-1)*W_TEMPO;

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
            double w = (c==side) ? (1.0+W_THREAT_INITIATIVE) : 1.0;
            double wp=W_THREAT_PAWN*w, wm=W_THREAT_MINOR*w, wr=W_THREAT_ROOK*w, wh=W_THREAT_HANGING*w;
            for(int p=0;p<5;p++){            /* PAWN..QUEEN (0-indexed here) */
                U64 x=bb[!c][p];
                while(x){ int sq=lsb(x); x&=x-1; U64 m=1ULL<<sq;
                    if((pawnatk[c]&m)  && p>=KNIGHT) s += sign*wp*PV[p];
                    if((minoratk[c]&m) && p>=ROOK)   s += sign*wm*PV[p];
                    if((rookatk[c]&m)  && p==QUEEN)  s += sign*wr*PV[p];
                    if((atkby[c]&m) && !(atkby[!c]&m)) s += sign*wh*PV[p];
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
        s += sign*(W_MATE_DRIVE_CORNER*CMD_TBL[lk]*scale + W_MATE_DRIVE_KING_PROX*(14-md)*scale);
    }

    return s;
}

/* C API: eval a FEN, White's perspective (for cross-checking) */
double c_eval(const char *fen){
    if(!g_init){ init_tables(); g_init=1; }
    Board b; if(set_fen(&b,fen)) return 0;
    return eval_core(b.bb, b.side);
}
