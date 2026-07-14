/* ConceptChess compiled core — board, move generation, perft.
 *
 * Milestone 1: a correct bitboard move generator, validated by perft against
 * python-chess. Squares a1=0..h8=63; White=0, Black=1; pieces P,N,B,R,Q,K=0..5.
 * Copy-make (the board struct is small) keeps make/unmake bug-free.
 */
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

typedef uint64_t U64;

enum { WHITE, BLACK };
enum { PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING };

typedef struct {
    U64 bb[2][6];     /* piece bitboards per color */
    U64 occ[2];       /* per-color occupancy */
    U64 all;          /* total occupancy */
    int side;         /* side to move */
    int ep;           /* en-passant target square, or -1 */
    int castle;       /* bits: 1=WK 2=WQ 4=BK 8=BQ */
} Board;

/* A move: from | to<<6 | promo<<12 | flag<<15
 * promo: 0 none, else piece type (N=1..Q=4). flag: 1 ep, 2 castle, 3 double-push */
typedef uint32_t Move;
#define MK_MOVE(f,t,promo,flag) ((Move)((f)|((t)<<6)|((promo)<<12)|((flag)<<15)))
#define MV_FROM(m)  ((m)&63)
#define MV_TO(m)    (((m)>>6)&63)
#define MV_PROMO(m) (((m)>>12)&7)
#define MV_FLAG(m)  (((m)>>15)&7)

static U64 KNIGHT_ATK[64], KING_ATK[64];
static U64 PAWN_ATK[2][64];

static inline int popcnt(U64 b){ return __builtin_popcountll(b); }
static inline int lsb(U64 b){ return __builtin_ctzll(b); }
static inline U64 pop_lsb(U64 *b){ U64 x=*b; *b&=*b-1; return x&(~x+1); }

static const int KNIGHT_D[8][2]={{1,2},{2,1},{2,-1},{1,-2},{-1,-2},{-2,-1},{-2,1},{-1,2}};
static const int KING_D[8][2]={{0,1},{1,1},{1,0},{1,-1},{0,-1},{-1,-1},{-1,0},{-1,1}};

static void init_tables(void){
    for(int sq=0; sq<64; sq++){
        int r=sq/8, f=sq%8;
        U64 n=0,k=0;
        for(int i=0;i<8;i++){
            int nf=f+KNIGHT_D[i][0], nr=r+KNIGHT_D[i][1];
            if(nf>=0&&nf<8&&nr>=0&&nr<8) n|=1ULL<<(nr*8+nf);
            int kf=f+KING_D[i][0], kr=r+KING_D[i][1];
            if(kf>=0&&kf<8&&kr>=0&&kr<8) k|=1ULL<<(kr*8+kf);
        }
        KNIGHT_ATK[sq]=n; KING_ATK[sq]=k;
        U64 wp=0,bp=0;
        if(f>0&&r<7) wp|=1ULL<<((r+1)*8+f-1);
        if(f<7&&r<7) wp|=1ULL<<((r+1)*8+f+1);
        if(f>0&&r>0) bp|=1ULL<<((r-1)*8+f-1);
        if(f<7&&r>0) bp|=1ULL<<((r-1)*8+f+1);
        PAWN_ATK[WHITE][sq]=wp; PAWN_ATK[BLACK][sq]=bp;
    }
}

/* Sliding attacks by ray scan until a blocker (occ). */
static const int BISHOP_D[4][2]={{1,1},{1,-1},{-1,-1},{-1,1}};
static const int ROOK_D[4][2]={{0,1},{1,0},{0,-1},{-1,0}};

static U64 slide(int sq, U64 occ, const int dirs[4][2]){
    U64 a=0; int r=sq/8, f=sq%8;
    for(int d=0; d<4; d++){
        int nf=f, nr=r;
        for(;;){
            nf+=dirs[d][0]; nr+=dirs[d][1];
            if(nf<0||nf>=8||nr<0||nr>=8) break;
            int s=nr*8+nf; a|=1ULL<<s;
            if(occ&(1ULL<<s)) break;
        }
    }
    return a;
}
static inline U64 bishop_atk(int sq,U64 occ){ return slide(sq,occ,BISHOP_D); }
static inline U64 rook_atk(int sq,U64 occ){ return slide(sq,occ,ROOK_D); }

static void refresh(Board *b){
    b->occ[WHITE]=b->occ[BLACK]=0;
    for(int p=0;p<6;p++){ b->occ[WHITE]|=b->bb[WHITE][p]; b->occ[BLACK]|=b->bb[BLACK][p]; }
    b->all=b->occ[WHITE]|b->occ[BLACK];
}

/* Is square sq attacked by side `by`? */
static int attacked(const Board *b, int sq, int by){
    if(PAWN_ATK[!by][sq] & b->bb[by][PAWN]) return 1;   /* by-pawns attack sq */
    if(KNIGHT_ATK[sq] & b->bb[by][KNIGHT]) return 1;
    if(KING_ATK[sq] & b->bb[by][KING]) return 1;
    U64 ba=bishop_atk(sq,b->all);
    if(ba & (b->bb[by][BISHOP]|b->bb[by][QUEEN])) return 1;
    U64 ra=rook_atk(sq,b->all);
    if(ra & (b->bb[by][ROOK]|b->bb[by][QUEEN])) return 1;
    return 0;
}

static inline int king_sq(const Board *b, int side){ return lsb(b->bb[side][KING]); }
static inline int in_check(const Board *b, int side){ return attacked(b,king_sq(b,side),!side); }

static int piece_at(const Board *b, int sq, int color){
    U64 m=1ULL<<sq;
    for(int p=0;p<6;p++) if(b->bb[color][p]&m) return p;
    return -1;
}

/* Apply a move (copy-make: caller passes a copy). Returns nothing; updates b. */
static void make(Board *b, Move mv){
    int from=MV_FROM(mv), to=MV_TO(mv), promo=MV_PROMO(mv), flag=MV_FLAG(mv);
    int us=b->side, them=!us;
    int pc=piece_at(b,from,us);
    U64 frombb=1ULL<<from, tobb=1ULL<<to;
    b->bb[us][pc]&=~frombb;
    /* captures */
    if(flag==1){ /* en passant */
        int capsq = us==WHITE ? to-8 : to+8;
        b->bb[them][PAWN]&=~(1ULL<<capsq);
    } else {
        int cap=piece_at(b,to,them);
        if(cap>=0) b->bb[them][cap]&=~tobb;
    }
    if(promo){ b->bb[us][promo]|=tobb; }
    else { b->bb[us][pc]|=tobb; }
    /* castling rook move */
    if(flag==2){
        if(to==6){ b->bb[us][ROOK]&=~(1ULL<<7); b->bb[us][ROOK]|=1ULL<<5; }
        else if(to==2){ b->bb[us][ROOK]&=~(1ULL<<0); b->bb[us][ROOK]|=1ULL<<3; }
        else if(to==62){ b->bb[us][ROOK]&=~(1ULL<<63); b->bb[us][ROOK]|=1ULL<<61; }
        else if(to==58){ b->bb[us][ROOK]&=~(1ULL<<56); b->bb[us][ROOK]|=1ULL<<59; }
    }
    /* castling rights */
    if(pc==KING){ if(us==WHITE) b->castle&=~3; else b->castle&=~12; }
    if(from==0||to==0) b->castle&=~2;
    if(from==7||to==7) b->castle&=~1;
    if(from==56||to==56) b->castle&=~8;
    if(from==63||to==63) b->castle&=~4;
    /* en passant target */
    b->ep = (flag==3) ? (us==WHITE ? from+8 : from-8) : -1;
    b->side=them;
    refresh(b);
}

/* Generate pseudo-legal moves into list; return count. */
static int gen_pseudo(const Board *b, Move *list){
    int n=0, us=b->side, them=!us;
    U64 own=b->occ[us], opp=b->occ[them], all=b->all;
    /* pawns */
    U64 pawns=b->bb[us][PAWN];
    int up = us==WHITE ? 8 : -8;
    U64 rank_promo = us==WHITE ? 0xFF00000000000000ULL : 0x00000000000000FFULL;
    U64 rank_start = us==WHITE ? 0x000000000000FF00ULL : 0x00FF000000000000ULL;
    U64 p=pawns;
    while(p){
        U64 one=pop_lsb(&p); int from=lsb(one);
        int to=from+up;
        if(to>=0&&to<64&&!(all&(1ULL<<to))){
            if((1ULL<<to)&rank_promo){
                for(int pr=QUEEN;pr>=KNIGHT;pr--) list[n++]=MK_MOVE(from,to,pr,0);
            } else {
                list[n++]=MK_MOVE(from,to,0,0);
                if((one&rank_start)){
                    int to2=to+up;
                    if(!(all&(1ULL<<to2))) list[n++]=MK_MOVE(from,to2,0,3);
                }
            }
        }
        U64 atk=PAWN_ATK[us][from]&(opp|(b->ep>=0?(1ULL<<b->ep):0));
        while(atk){
            U64 a=pop_lsb(&atk); int t=lsb(a);
            if(t==b->ep){ list[n++]=MK_MOVE(from,t,0,1); }
            else if((1ULL<<t)&rank_promo){
                for(int pr=QUEEN;pr>=KNIGHT;pr--) list[n++]=MK_MOVE(from,t,pr,0);
            } else list[n++]=MK_MOVE(from,t,0,0);
        }
    }
    /* knights */
    U64 kn=b->bb[us][KNIGHT];
    while(kn){ int from=lsb(pop_lsb(&kn)); U64 t=KNIGHT_ATK[from]&~own;
        while(t){ list[n++]=MK_MOVE(from,lsb(pop_lsb(&t)),0,0);} }
    /* bishops+queens diagonal */
    U64 bq=b->bb[us][BISHOP]|b->bb[us][QUEEN];
    while(bq){ int from=lsb(pop_lsb(&bq)); U64 t=bishop_atk(from,all)&~own;
        while(t){ list[n++]=MK_MOVE(from,lsb(pop_lsb(&t)),0,0);} }
    /* rooks+queens orthogonal */
    U64 rq=b->bb[us][ROOK]|b->bb[us][QUEEN];
    while(rq){ int from=lsb(pop_lsb(&rq)); U64 t=rook_atk(from,all)&~own;
        while(t){ list[n++]=MK_MOVE(from,lsb(pop_lsb(&t)),0,0);} }
    /* king */
    int ks=king_sq(b,us);
    U64 kt=KING_ATK[ks]&~own;
    while(kt){ list[n++]=MK_MOVE(ks,lsb(pop_lsb(&kt)),0,0);}
    /* castling */
    if(us==WHITE){
        if((b->castle&1) && !(all&0x60ULL) && !attacked(b,4,them)&&!attacked(b,5,them)&&!attacked(b,6,them))
            list[n++]=MK_MOVE(4,6,0,2);
        if((b->castle&2) && !(all&0x0EULL) && !attacked(b,4,them)&&!attacked(b,3,them)&&!attacked(b,2,them))
            list[n++]=MK_MOVE(4,2,0,2);
    } else {
        if((b->castle&4) && !(all&0x6000000000000000ULL) && !attacked(b,60,them)&&!attacked(b,61,them)&&!attacked(b,62,them))
            list[n++]=MK_MOVE(60,62,0,2);
        if((b->castle&8) && !(all&0x0E00000000000000ULL) && !attacked(b,60,them)&&!attacked(b,59,them)&&!attacked(b,58,them))
            list[n++]=MK_MOVE(60,58,0,2);
    }
    return n;
}

/* Legal moves: pseudo-legal filtered by own-king safety. */
int gen_legal(const Board *b, Move *out){
    Move pl[256]; int n=gen_pseudo(b,pl), m=0;
    for(int i=0;i<n;i++){
        Board c=*b; make(&c,pl[i]);
        if(!in_check(&c,b->side)) out[m++]=pl[i];
    }
    return m;
}

/* FEN -> Board */
int set_fen(Board *b, const char *fen){
    memset(b,0,sizeof(*b)); b->ep=-1;
    int sq=56; const char *s=fen;
    for(; *s && *s!=' '; s++){
        char c=*s;
        if(c=='/'){ sq-=16; }
        else if(c>='1'&&c<='8'){ sq+=c-'0'; }
        else {
            int color = (c>='a') ? BLACK : WHITE;
            char l = (c>='a')?c:c+32;
            int pc = l=='p'?PAWN:l=='n'?KNIGHT:l=='b'?BISHOP:l=='r'?ROOK:l=='q'?QUEEN:l=='k'?KING:-1;
            if(pc<0) return -1;
            b->bb[color][pc]|=1ULL<<sq; sq++;
        }
    }
    while(*s==' ')s++;
    b->side = (*s=='w')?WHITE:BLACK; s++;
    while(*s==' ')s++;
    b->castle=0;
    for(; *s && *s!=' '; s++){
        if(*s=='K')b->castle|=1; else if(*s=='Q')b->castle|=2;
        else if(*s=='k')b->castle|=4; else if(*s=='q')b->castle|=8;
    }
    while(*s==' ')s++;
    if(*s && *s!='-'){ int f=s[0]-'a', r=s[1]-'1'; b->ep=r*8+f; }
    refresh(b);
    return 0;
}

/* perft */
U64 perft(Board *b, int depth){
    if(depth==0) return 1;
    Move list[256]; int n=gen_legal(b,list);
    if(depth==1) return (U64)n;
    U64 nodes=0;
    for(int i=0;i<n;i++){ Board c=*b; make(&c,list[i]); nodes+=perft(&c,depth-1); }
    return nodes;
}

/* --- C API for ctypes --- */
static int g_init=0;
U64 c_perft(const char *fen, int depth){
    if(!g_init){ init_tables(); g_init=1; }
    Board b; if(set_fen(&b,fen)) return 0;
    return perft(&b,depth);
}
