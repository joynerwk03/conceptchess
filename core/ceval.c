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
            for(int p=KNIGHT;p<=QUEEN;p++){
                U64 x=bb[c][p];
                while(x){ int sq=lsb(x); x&=x-1; U64 atk;
                    if(p==KNIGHT) atk=KNIGHT_ATK[sq];
                    else if(p==BISHOP) atk=bishop_atk(sq,all);
                    else if(p==ROOK) atk=rook_atk(sq,all);
                    else atk=bishop_atk(sq,all)|rook_atk(sq,all);
                    int hits=popcnt(atk&zone);
                    if(hits){ units+=UNIT[p]*hits; attackers++; }
                }
            }
            if(attackers>=2) s += sign*W_KATTACK_SCALE*units*units/10.0*phase;
        }
    }

    /* mobility (safe squares) */
    double MOBW[6]={0,W_MOB_KNIGHT,W_MOB_BISHOP,W_MOB_ROOK,W_MOB_QUEEN,0};
    static const int TYP[6]={0,4,6,7,13,0};
    for(int c=0;c<2;c++){
        int sign=c==WHITE?1:-1; U64 own=occ[c];
        U64 unsafe = c==WHITE ? BPAWN_ATK(bb[BLACK][PAWN]) : WPAWN_ATK(bb[WHITE][PAWN]);
        for(int p=KNIGHT;p<=QUEEN;p++){
            U64 x=bb[c][p];
            while(x){ int sq=lsb(x); x&=x-1; U64 atk;
                if(p==KNIGHT) atk=KNIGHT_ATK[sq];
                else if(p==BISHOP) atk=bishop_atk(sq,all);
                else if(p==ROOK) atk=rook_atk(sq,all);
                else atk=bishop_atk(sq,all)|rook_atk(sq,all);
                int n=popcnt(atk&~own&~unsafe);
                s += sign*MOBW[p]*(n-TYP[p]);
            }
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

    /* threats */
    {
        U64 atkby[2];
        for(int c=0;c<2;c++){
            U64 a = c==WHITE ? WPAWN_ATK(bb[WHITE][PAWN]) : BPAWN_ATK(bb[BLACK][PAWN]);
            U64 kn=bb[c][KNIGHT]; while(kn){int sq=lsb(kn);kn&=kn-1;a|=KNIGHT_ATK[sq];}
            U64 bp=bb[c][BISHOP]|bb[c][QUEEN]; while(bp){int sq=lsb(bp);bp&=bp-1;a|=bishop_atk(sq,all);}
            U64 rq=bb[c][ROOK]|bb[c][QUEEN]; while(rq){int sq=lsb(rq);rq&=rq-1;a|=rook_atk(sq,all);}
            a|=KING_ATK[lsb(bb[c][KING])];
            atkby[c]=a;
        }
        static const double PV[6]={100,320,330,500,900,0};
        for(int c=0;c<2;c++){
            int sign=c==WHITE?1:-1;
            for(int p=0;p<5;p++){
                U64 x=bb[!c][p];
                while(x){ int sq=lsb(x); x&=x-1;
                    if((atkby[c]&(1ULL<<sq)) && !(atkby[!c]&(1ULL<<sq)))
                        s += sign*W_THREAT_HANGING*PV[p];
                }
            }
        }
    }

    /* mating drive */
    for(int win=0; win<2; win++){
        int lose=!win, sign=win==WHITE?1:-1;
        U64 lm=bb[lose][PAWN]|bb[lose][KNIGHT]|bb[lose][BISHOP]|bb[lose][ROOK]|bb[lose][QUEEN];
        if(lm) continue;
        int mating=(bb[win][QUEEN]||bb[win][ROOK])||(popcnt(bb[win][KNIGHT])+popcnt(bb[win][BISHOP])>=2);
        if(!mating) continue;
        int lk=lsb(bb[lose][KING]), wk=lsb(bb[win][KING]);
        int md=abs((lk%8)-(wk%8))+abs((lk/8)-(wk/8));
        s += sign*(W_MATE_DRIVE_CORNER*CMD_TBL[lk] + W_MATE_DRIVE_KING_PROX*(14-md));
    }

    return s;
}

/* C API: eval a FEN, White's perspective (for cross-checking) */
double c_eval(const char *fen){
    if(!g_init){ init_tables(); g_init=1; }
    Board b; if(set_fen(&b,fen)) return 0;
    return eval_core(b.bb, b.side);
}
