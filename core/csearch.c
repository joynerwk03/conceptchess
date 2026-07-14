/* ConceptChess compiled core — search. #included at the end of cengine.c.
 *
 * Ports engine/search.py: iterative-deepening negamax, TT (Zobrist), MVV-LVA +
 * killer + history ordering, quiescence with SEE + delta pruning + first-ply
 * checks, null move, LMR (two tiers), PVS, futility, check extension, soft time
 * management, draw detection (repetition/50-move/insufficient material).
 * Uses the perft-validated board/movegen and the cross-checked eval above.
 */
#include <time.h>

#define S_MATE 100000
#define S_MATE_TH 90000
#define TT_EXACTF 0
#define TT_LOWERF 1
#define TT_UPPERF 2
#define TT_BITS 22
#define TT_SIZE (1u<<TT_BITS)
#define TT_MASK (TT_SIZE-1)
#define MAXPLY 128

static const int SEEV[6]={100,320,330,500,900,0};

/* Zobrist */
static U64 Z_PIECE[2][6][64], Z_SIDE, Z_CASTLE[16], Z_EP[8];
static U64 splitmix(U64 *x){ U64 z=(*x+=0x9E3779B97F4A7C15ULL);
    z=(z^(z>>30))*0xBF58476D1CE4E5B9ULL; z=(z^(z>>27))*0x94D049BB133111EBULL; return z^(z>>31); }
static void zobrist_init(void){
    U64 s=0x123456789ABCDEFULL;
    for(int c=0;c<2;c++)for(int p=0;p<6;p++)for(int q=0;q<64;q++)Z_PIECE[c][p][q]=splitmix(&s);
    Z_SIDE=splitmix(&s);
    for(int i=0;i<16;i++)Z_CASTLE[i]=splitmix(&s);
    for(int i=0;i<8;i++)Z_EP[i]=splitmix(&s);
}
static U64 compute_hash(const Board *b){
    U64 h=0;
    for(int c=0;c<2;c++)for(int p=0;p<6;p++){ U64 x=b->bb[c][p]; while(x){int sq=lsb(x);x&=x-1;h^=Z_PIECE[c][p][sq];}}
    if(b->side==BLACK)h^=Z_SIDE;
    h^=Z_CASTLE[b->castle&15];
    if(b->ep>=0)h^=Z_EP[b->ep&7];
    return h;
}

typedef struct { U64 key; int score; Move move; short depth; unsigned char flag; } TTEntry;
static TTEntry *TT=0;

typedef struct {
    long nodes;
    double stop_time;
    int stopped;
    Move killers[MAXPLY][2];
    int history[2][64][64];
    U64 path[MAXPLY+256];   /* game history hashes + current search path */
    int path_len;
} Search;
static Search SS;

static double now_sec(void){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC,&ts);
    return ts.tv_sec + ts.tv_nsec*1e-9; }

static int is_capture(const Board *b, Move m){
    int to=MV_TO(m);
    if(MV_FLAG(m)==1) return 1; /* ep */
    return (b->occ[!b->side]>>to)&1;
}

/* attackers of square sq (both colors) given occupancy occ */
static U64 attackers_to(const Board *b, int sq, U64 occ){
    U64 a=0;
    a |= PAWN_ATK[BLACK][sq] & b->bb[WHITE][PAWN];   /* white pawns attacking sq */
    a |= PAWN_ATK[WHITE][sq] & b->bb[BLACK][PAWN];
    a |= KNIGHT_ATK[sq] & (b->bb[WHITE][KNIGHT]|b->bb[BLACK][KNIGHT]);
    a |= KING_ATK[sq] & (b->bb[WHITE][KING]|b->bb[BLACK][KING]);
    U64 ba=bishop_atk(sq,occ);
    a |= ba & (b->bb[WHITE][BISHOP]|b->bb[BLACK][BISHOP]|b->bb[WHITE][QUEEN]|b->bb[BLACK][QUEEN]);
    U64 ra=rook_atk(sq,occ);
    a |= ra & (b->bb[WHITE][ROOK]|b->bb[BLACK][ROOK]|b->bb[WHITE][QUEEN]|b->bb[BLACK][QUEEN]);
    return a & occ;
}
static int piece_on(const Board *b,int sq){
    U64 m=1ULL<<sq;
    for(int c=0;c<2;c++)for(int p=0;p<6;p++) if(b->bb[c][p]&m) return p;
    return -1;
}
/* SEE: >=0 means the capture doesn't lose material (mirrors engine/search._see) */
static int see(const Board *b, Move m){
    int to=MV_TO(m), from=MV_FROM(m);
    int firstv = (MV_FLAG(m)==1)?SEEV[PAWN]:SEEV[piece_on(b,to)>=0?piece_on(b,to):PAWN];
    U64 occ=b->all & ~(1ULL<<from);
    int gain[32], n=0; gain[n++]=firstv;
    int aval=SEEV[piece_on(b,from)];
    int side=!b->side;
    for(;;){
        U64 att=attackers_to(b,to,occ)&occ;
        U64 side_occ = (side==WHITE)?b->occ[WHITE]:b->occ[BLACK];
        U64 myatt=att&side_occ;
        if(!myatt) break;
        int bestsq=-1, bestval=1000000; U64 x=myatt;
        while(x){ int sq=lsb(x); x&=x-1; int v=SEEV[piece_on(b,sq)]; if(v<bestval){bestval=v;bestsq=sq;} }
        gain[n]=aval-gain[n-1]; n++;
        aval=bestval; occ&=~(1ULL<<bestsq); side=!side;
        if(n>=31) break;
    }
    while(n>1){ n--; if(-gain[n] < gain[n-1]) gain[n-1]=-gain[n]; }
    return gain[0];
}

static int insufficient(const Board *b){
    if(b->bb[WHITE][PAWN]|b->bb[BLACK][PAWN]|b->bb[WHITE][ROOK]|b->bb[BLACK][ROOK]
       |b->bb[WHITE][QUEEN]|b->bb[BLACK][QUEEN]) return 0;
    int minors = popcnt(b->bb[WHITE][KNIGHT]|b->bb[WHITE][BISHOP]|b->bb[BLACK][KNIGHT]|b->bb[BLACK][BISHOP]);
    return minors<=1;
}
static int is_rep(U64 h){
    for(int i=SS.path_len-2;i>=0;i-=2) if(SS.path[i]==h) return 1;
    return 0;
}

static int mvv_lva(const Board *b, Move m){
    int to=MV_TO(m), victim;
    if(MV_PROMO(m)) victim=SEEV[QUEEN];
    else if(MV_FLAG(m)==1) victim=SEEV[PAWN];
    else { int vp=piece_on(b,to); victim = vp>=0?SEEV[vp]:0; }
    int att=piece_on(b,MV_FROM(m));
    return victim*10 - (att>=0?SEEV[att]:0);
}

static void order(const Board *b, Move *mv, int n, Move ttm, int ply){
    int sc[256];
    Move k0=ply<MAXPLY?SS.killers[ply][0]:0, k1=ply<MAXPLY?SS.killers[ply][1]:0;
    for(int i=0;i<n;i++){
        Move m=mv[i];
        if(m==ttm) sc[i]=1000000;
        else if(is_capture(b,m)) sc[i]=100000+mvv_lva(b,m);
        else if(MV_PROMO(m)==QUEEN) sc[i]=90000;
        else if(m==k0) sc[i]=80000;
        else if(m==k1) sc[i]=79000;
        else sc[i]=SS.history[b->side][MV_FROM(m)][MV_TO(m)];
    }
    for(int i=1;i<n;i++){ Move m=mv[i]; int s=sc[i]; int j=i-1;
        while(j>=0&&sc[j]<s){ sc[j+1]=sc[j]; mv[j+1]=mv[j]; j--; } sc[j+1]=s; mv[j+1]=m; }
}

static int has_non_pawn(const Board *b){
    int c=b->side;
    return (b->bb[c][KNIGHT]|b->bb[c][BISHOP]|b->bb[c][ROOK]|b->bb[c][QUEEN])!=0;
}

static int qsearch(Board *b, int alpha, int beta, int ply, int qd){
    SS.nodes++;
    if(!(SS.nodes&2047) && now_sec()>SS.stop_time){ SS.stopped=1; return 0; }
    int checked=in_check(b,b->side);
    if(checked){
        Move mv[256]; int n=gen_legal(b,mv);
        if(!n) return -S_MATE+ply;
        order(b,mv,n,0,ply<MAXPLY?ply:MAXPLY-1);
        int best=-S_MATE-1;
        for(int i=0;i<n;i++){ Board c=*b; make(&c,mv[i]);
            int sc=-qsearch(&c,-beta,-alpha,ply+1,qd+1);
            if(SS.stopped) return 0;
            if(sc>best) best=sc;
            if(sc>alpha) alpha=sc;
            if(alpha>=beta) break; }
        return best;
    }
    int stand = (int)eval_core(b->bb,b->side); if(b->side==BLACK) stand=-stand;
    if(stand>=beta) return beta;
    if(stand>alpha) alpha=stand;
    Move mv[256]; int n=gen_legal(b,mv), cn=0; Move caps[256]; int cs[256];
    for(int i=0;i<n;i++){ Move m=mv[i];
        if(is_capture(b,m) || MV_PROMO(m)==QUEEN){
            if(is_capture(b,m) && see(b,m)<0) continue;   /* SEE prune losing caps */
            caps[cn]=m; cs[cn]=mvv_lva(b,m); cn++; } }
    for(int i=1;i<cn;i++){ Move m=caps[i]; int s=cs[i]; int j=i-1;
        while(j>=0&&cs[j]<s){cs[j+1]=cs[j];caps[j+1]=caps[j];j--;} cs[j+1]=s; caps[j+1]=m; }
    for(int i=0;i<cn;i++){ Move m=caps[i];
        int vp=(MV_FLAG(m)==1)?PAWN:piece_on(b,MV_TO(m)); int victim=MV_PROMO(m)?SEEV[QUEEN]:(vp>=0?SEEV[vp]:0);
        if(stand+victim+200<alpha) continue;
        Board c=*b; make(&c,m);
        int sc=-qsearch(&c,-beta,-alpha,ply+1,qd+1);
        if(SS.stopped) return 0;
        if(sc>=beta) return beta;
        if(sc>alpha) alpha=sc;
    }
    if(qd==0){ /* first-ply quiet checks */
        for(int i=0;i<n;i++){ Move m=mv[i];
            if(is_capture(b,m)||MV_PROMO(m)) continue;
            Board c=*b; make(&c,m);
            if(in_check(&c,c.side)){
                int sc=-qsearch(&c,-beta,-alpha,ply+1,qd+1);
                if(SS.stopped) return 0;
                if(sc>=beta) return beta;
                if(sc>alpha) alpha=sc;
            }
        }
    }
    return alpha;
}

static int negamax(Board *b, int depth, int alpha, int beta, int ply){
    SS.nodes++;
    if(!(SS.nodes&2047) && now_sec()>SS.stop_time){ SS.stopped=1; return 0; }
    U64 h=compute_hash(b);
    SS.path[SS.path_len++]=h;
    int ret, done=0;
    if(is_rep(h)||insufficient(b)){ ret=0; done=1; }
    int checked = done?0:in_check(b,b->side);
    if(!done && checked) depth++;
    if(!done && depth<=0){ ret=qsearch(b,alpha,beta,ply,0); done=1; }

    Move ttm=0;
    if(!done){
        TTEntry *e=&TT[h&TT_MASK];
        if(e->key==h){ ttm=e->move;
            if(e->depth>=depth && ply>0){
                if(e->flag==TT_EXACTF){ ret=e->score; done=1; }
                else if(e->flag==TT_LOWERF && e->score>=beta){ ret=e->score; done=1; }
                else if(e->flag==TT_UPPERF && e->score<=alpha){ ret=e->score; done=1; }
            }
        }
    }
    if(done){ SS.path_len--; return ret; }

    /* null move */
    if(depth>=3 && !checked && beta<S_MATE_TH && has_non_pawn(b)){
        Board c=*b; c.side=!c.side; c.ep=-1;
        int r = depth>=6?4:3;
        int sc=-negamax(&c,depth-r,-beta,-beta+1,ply+1);
        if(SS.stopped){ SS.path_len--; return 0; }
        if(sc>=beta){ SS.path_len--; return beta; }
    }

    Move mv[256]; int n=gen_legal(b,mv);
    if(!n){ SS.path_len--; return checked? -S_MATE+ply : 0; }

    int futile=0;
    if(depth<=2 && !checked && (alpha>-S_MATE_TH&&alpha<S_MATE_TH)){
        int st=(int)eval_core(b->bb,b->side); if(b->side==BLACK)st=-st;
        futile = st + (depth==1?150:300) <= alpha;
    }
    order(b,mv,n,ttm,ply<MAXPLY?ply:MAXPLY-1);
    int best=-S_MATE-1, orig_alpha=alpha; Move bestm=0;
    for(int i=0;i<n;i++){
        Move m=mv[i];
        int quiet = !is_capture(b,m) && MV_PROMO(m)==0;
        Board c=*b; make(&c,m);
        if(futile && quiet && bestm && !in_check(&c,c.side)){ continue; }
        int sc;
        if(i==0){ sc=-negamax(&c,depth-1,-beta,-alpha,ply+1); }
        else {
            int red=1;
            if(depth>=3 && quiet && !checked){ if(i>=12)red=3; else if(i>=3)red=2; }
            sc=-negamax(&c,depth-red,-alpha-1,-alpha,ply+1);
            if(sc>alpha && (red>1 || beta>alpha+1)) sc=-negamax(&c,depth-1,-beta,-alpha,ply+1);
        }
        if(SS.stopped){ SS.path_len--; return 0; }
        if(sc>best){ best=sc; bestm=m; }
        if(sc>alpha) alpha=sc;
        if(alpha>=beta){
            if(quiet && ply<MAXPLY){
                if(SS.killers[ply][0]!=m){ SS.killers[ply][1]=SS.killers[ply][0]; SS.killers[ply][0]=m; }
                SS.history[b->side][MV_FROM(m)][MV_TO(m)] += depth*depth;
            }
            break;
        }
    }
    int flag = best<=orig_alpha?TT_UPPERF : best>=beta?TT_LOWERF : TT_EXACTF;
    TTEntry *e=&TT[h&TT_MASK];
    e->key=h; e->depth=depth; e->flag=flag; e->score=best; e->move=bestm;
    SS.path_len--;
    return best;
}

static void uci_of(Move m, char *out){
    int f=MV_FROM(m), t=MV_TO(m);
    out[0]='a'+(f&7); out[1]='1'+(f>>3); out[2]='a'+(t&7); out[3]='1'+(t>>3);
    int pr=MV_PROMO(m);
    if(pr){ out[4]="  nbrq"[pr]; out[5]=0; } else out[4]=0;
}

/* Public API: search from startfen after the given space-separated UCI moves.
 * Fills uci_out (>=6 bytes), depth_out, nodes_out; returns score (stm cp). */
static int g_search_init=0;
int c_search(const char *startfen, const char *moves, double movetime,
             char *uci_out, int *depth_out, long *nodes_out){
    if(!g_init){ init_tables(); g_init=1; }
    if(!g_search_init){ zobrist_init(); TT=calloc(TT_SIZE,sizeof(TTEntry)); g_search_init=1; }
    Board b; if(set_fen(&b,startfen)){ uci_out[0]=0; return 0; }
    /* replay moves to build the board + repetition history */
    memset(&SS,0,sizeof(SS));
    SS.path[SS.path_len++]=compute_hash(&b);
    if(moves && *moves){
        const char *p=moves;
        while(*p){
            while(*p==' ')p++;
            if(!*p)break;
            int ff=p[0]-'a', fr=p[1]-'1', tf=p[2]-'a', tr=p[3]-'1';
            int from=fr*8+ff, to=tr*8+tf, promo=0, flag=0;
            char pc=p[4];
            if(pc>='a'&&pc<='z'&&pc!=' '){ promo = pc=='n'?KNIGHT:pc=='b'?BISHOP:pc=='r'?ROOK:pc=='q'?QUEEN:0; p++; }
            /* infer flags from board */
            int mover=piece_on(&b,from);
            if(mover==PAWN){ if(to==b.ep && ((to&7)!=(from&7))) flag=1;
                else if(abs(tr-fr)==2) flag=3; }
            if(mover==KING && abs(tf-ff)==2) flag=2;
            Move m=MK_MOVE(from,to,promo,flag);
            make(&b,m);
            SS.path[SS.path_len++]=compute_hash(&b);
            p+=4; while(*p&&*p!=' ')p++;
        }
    }
    /* iterative deepening */
    double start=now_sec(); SS.stop_time=start+movetime;
    Move root[256]; int rn=gen_legal(&b,root);
    if(!rn){ uci_out[0]=0; return 0; }
    Move best=root[0]; int score=0, cd=0;
    for(int depth=1; depth<=64; depth++){
        int a=-S_MATE, bt=S_MATE, bm_found=0; Move bm=0; int bs=-S_MATE-1;
        order(&b,root,rn,best,0);
        for(int i=0;i<rn;i++){
            Board c=b; make(&c,root[i]);
            int sc;
            if(i==0) sc=-negamax(&c,depth-1,-bt,-a,1);
            else { sc=-negamax(&c,depth-1,-a-1,-a,1);
                   if(sc>a) sc=-negamax(&c,depth-1,-bt,-a,1); }
            if(SS.stopped) break;
            if(sc>bs){ bs=sc; bm=root[i]; bm_found=1; }
            if(sc>a) a=sc;
        }
        if(SS.stopped) break;
        if(bm_found){ best=bm; score=bs; cd=depth;
            /* move best to front for next iteration */
            for(int i=0;i<rn;i++) if(root[i]==best){ Move t=root[i]; for(int j=i;j>0;j--)root[j]=root[j-1]; root[0]=t; break; } }
        if(score>S_MATE_TH||score<-S_MATE_TH) break;
        if(now_sec()-start > movetime*0.5) break;
    }
    uci_of(best,uci_out);
    if(depth_out)*depth_out=cd;
    if(nodes_out)*nodes_out=SS.nodes;
    return score;
}

/* Principal variation from the TT, as space-separated UCI, into pv_out. */
void c_pv(const char *startfen, const char *moves, char *pv_out, int maxlen){
    Board b; if(set_fen(&b,startfen)){ pv_out[0]=0; return; }
    if(moves && *moves){
        const char *p=moves;
        while(*p){ while(*p==' ')p++; if(!*p)break;
            int ff=p[0]-'a',fr=p[1]-'1',tf=p[2]-'a',tr=p[3]-'1';
            int from=fr*8+ff,to=tr*8+tf,promo=0,flag=0; char pc=p[4];
            if(pc>='a'&&pc<='z'&&pc!=' '){ promo=pc=='n'?KNIGHT:pc=='b'?BISHOP:pc=='r'?ROOK:pc=='q'?QUEEN:0; p++; }
            int mover=piece_on(&b,from);
            if(mover==PAWN){ if(to==b.ep&&((to&7)!=(from&7)))flag=1; else if(abs(tr-fr)==2)flag=3; }
            if(mover==KING&&abs(tf-ff)==2)flag=2;
            make(&b,MK_MOVE(from,to,promo,flag)); p+=4; while(*p&&*p!=' ')p++;
        }
    }
    int pos=0; U64 seen[64]; int ns=0;
    for(int d=0; d<24; d++){
        U64 h=compute_hash(&b);
        for(int i=0;i<ns;i++) if(seen[i]==h){ d=999; break; }
        if(d==999) break;
        if(ns<64) seen[ns++]=h;
        TTEntry *e=&TT[h&TT_MASK];
        if(e->key!=h||e->move==0) break;
        /* verify legal */
        Move legal[256]; int nl=gen_legal(&b,legal), ok=0;
        for(int i=0;i<nl;i++) if(legal[i]==e->move){ ok=1; break; }
        if(!ok) break;
        char u[8]; uci_of(e->move,u);
        int ul=(int)strlen(u);
        if(pos+ul+1>=maxlen) break;
        if(pos) pv_out[pos++]=' ';
        memcpy(pv_out+pos,u,ul); pos+=ul;
        make(&b,e->move);
    }
    pv_out[pos]=0;
}
