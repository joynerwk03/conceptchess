/* ConceptChess compiled core — search. #included at the end of cengine.c.
 *
 * Ports engine/search.py: iterative-deepening negamax, TT (Zobrist), MVV-LVA +
 * killer + history ordering, quiescence with SEE + delta pruning + first-ply
 * checks, null move, LMR (two tiers), PVS, futility, check extension, soft time
 * management, draw detection (repetition/50-move/insufficient material).
 * Uses the perft-validated board/movegen and the cross-checked eval above.
 */
#include <time.h>
#include <math.h>
#include <pthread.h>

/* Lazy SMP: N threads search the same root sharing one transposition table.
 * Each thread keeps its own search state (killers/history/path/nodes) in
 * thread-local storage; only the TT and eval hash are shared. Helper threads
 * diversify by starting iterative deepening at staggered depths, so they fill
 * the shared TT with entries the main thread reuses to go deeper in the same
 * wall-clock budget. TT/eval-hash writes race, which Lazy SMP tolerates (the
 * 64-bit key check rejects torn entries; rare torn scores self-correct).
 * Thread count is set via c_set_threads() (default 1 = exact old behavior). */
#define MAX_THREADS 8
static int g_threads = 1;
static volatile int g_stop = 0;
void c_set_threads(int n){ g_threads = n<1?1 : (n>MAX_THREADS?MAX_THREADS:n); }

/* MultiPV / true 2nd-best. OFF by default: a normal alpha-beta search scores
 * only the BEST root move exactly -- every other root move fails low against
 * best's alpha and returns an upper bound, so the "runner-up" is a move-order
 * artifact, not a real 2nd choice. When on (the analysis GUI turns it on), we
 * do one extra full-window root pass that excludes best to find the true 2nd
 * move. Off in play so games pay zero extra cost. */
static int g_want_second = 0;
void c_set_multipv(int on){ g_want_second = on?1:0; }

#define S_MATE 100000
#define S_MATE_TH 90000
#define TT_EXACTF 0
#define TT_LOWERF 1
#define TT_UPPERF 2
#define TT_BITS 22
#define TT_SIZE (1u<<TT_BITS)
#define TT_MASK (TT_SIZE-1)
#define MAXPLY 128
#define RFP_DEPTH 6      /* reverse-futility pruning: max depth to apply it */
#define RFP_MARGIN 90    /* ...and cp margin conceded per ply */
#define LMP_DEPTH 5      /* late-move pruning: max depth to skip late quiets */

static const int SEEV[6]={100,320,330,500,900,0};

/* Zobrist tables + zobrist_init() live in cengine.c (make() needs them to
 * maintain Board.hash incrementally); this file just consumes b->hash. */

typedef struct { U64 key; int score; Move move; short depth; unsigned char flag; } TTEntry;
static TTEntry *TT=0;

/* Eval hash: caches side-to-move static eval by Board.hash. The hash covers
 * side to move (Z_SIDE), so one entry can never serve both colors; full
 * 64-bit key compare, same collision profile as the TT. Values are exactly
 * what eval_core would return, so search shape is byte-identical — this is a
 * pure speedup (qsearch stand-pat + futility probes stop recomputing). */
#define EH_BITS 20
#define EH_SIZE (1u<<EH_BITS)
#define EH_MASK (EH_SIZE-1)
typedef struct { U64 key; int val; } EHEntry;
static EHEntry *EH=0;

typedef struct {
    long nodes;
    double stop_time;
    int stopped;
    Move killers[MAXPLY][2];
    int seval[MAXPLY];   /* static eval per ply, for the improving heuristic */
    /* Triangular PV table: pv[ply] holds the principal variation from `ply`
     * down. WRITE-ONLY during search (never read to make a decision), so the
     * search tree is byte-identical with or without it — it just records the
     * line for display instead of walking the (lossy) TT. */
    Move pv[MAXPLY][MAXPLY];
    int pvlen[MAXPLY];
    Move excluded[MAXPLY];   /* singular-extension verification: the move to skip at this ply */
    int history[2][64][64];
    Move counter[2][64][64];  /* countermove: reply-by-side indexed by prev from/to */
    /* Game-history hashes + current search path. Sized for the longest
     * realistic game (the match harness alone allows 250 moves = 500 plies)
     * plus MAXPLY of search; the old MAXPLY+256 (=384) overflowed on long
     * endgame grinds and segfaulted mid-match — more common since the
     * repetition fix stopped winners from shuffling into threefold. c_search
     * additionally drops the oldest entries if a game somehow approaches the
     * cap (is_rep only ever looks back one halfmove-clock window). */
    U64 path[4096];
    int path_len;
} Search;
static _Thread_local Search SS;   /* per-thread (Lazy SMP); TT/EH stay shared */
#define PATH_CAP ((int)(sizeof(SS.path)/sizeof(SS.path[0])))

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
static int is_rep(U64 h, int hm){
    /* Positions older than the halfmove clock are unreachable again (a pawn
     * move or capture is irreversible), so bound the scan to O(hm).
     * Scan EVERY entry in the window: the hash includes side-to-move
     * (Z_SIDE), so wrong-side entries can never match — and stepping by 2
     * is unsound anyway once null moves interleave the path. (The original
     * port started at path_len-2 stepping 2, which only ever visited
     * opposite-side entries: repetition detection had been dead since the
     * C port. Found via the KBN mate-conversion test.) */
    int lo = SS.path_len-1-hm; if(lo<0) lo=0;
    for(int i=SS.path_len-2;i>=lo;i--) if(SS.path[i]==h) return 1;
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

static void order(const Board *b, Move *mv, int n, Move ttm, int ply, Move cm){
    int sc[256];
    Move k0=ply<MAXPLY?SS.killers[ply][0]:0, k1=ply<MAXPLY?SS.killers[ply][1]:0;
    for(int i=0;i<n;i++){
        Move m=mv[i];
        if(m==ttm) sc[i]=1000000;
        else if(is_capture(b,m)){
            /* SEE ranks captures by actual material outcome (mirrors qsearch's
             * pruning signal), not MVV-LVA's cruder victim/attacker heuristic.
             * Losing captures (SEE<0) are demoted below quiet-move history —
             * still searched (unlike qsearch, which prunes them outright),
             * just not wastefully explored first. */
            int s = see(b,m);
            sc[i] = (s>=0) ? (100000+s) : (-1000000+s);
        }
        else if(MV_PROMO(m)==QUEEN) sc[i]=90000;
        else if(m==k0) sc[i]=80000;
        else if(m==k1) sc[i]=79000;
        else if(cm && m==cm) sc[i]=78000;  /* countermove: quiet that refuted this prev move before */
        else sc[i]=SS.history[b->side][MV_FROM(m)][MV_TO(m)];
    }
    for(int i=1;i<n;i++){ Move m=mv[i]; int s=sc[i]; int j=i-1;
        while(j>=0&&sc[j]<s){ sc[j+1]=sc[j]; mv[j+1]=mv[j]; j--; } sc[j+1]=s; mv[j+1]=m; }
}

static int has_non_pawn(const Board *b){
    int c=b->side;
    return (b->bb[c][KNIGHT]|b->bb[c][BISHOP]|b->bb[c][ROOK]|b->bb[c][QUEEN])!=0;
}

/* side-to-move static eval via the eval hash (see EHEntry above) */
static int eval_stm(Board *b){
    EHEntry *e=&EH[b->hash&EH_MASK];
    if(e->key==b->hash) return e->val;
    int v=(int)eval_core(b->bb,b->side); if(b->side==BLACK) v=-v;
    e->key=b->hash; e->val=v;
    return v;
}

static int qsearch(Board *b, int alpha, int beta, int ply, int qd){
    SS.nodes++;
    if(!(SS.nodes&2047) && (g_stop || now_sec()>SS.stop_time)){ SS.stopped=1; return 0; }
    int checked=in_check(b,b->side);
    if(checked){
        Move mv[256]; int n=gen_legal(b,mv);
        if(!n) return -S_MATE+ply;
        order(b,mv,n,0,ply<MAXPLY?ply:MAXPLY-1,0);
        int best=-S_MATE-1;
        for(int i=0;i<n;i++){ Board c=*b; make(&c,mv[i]);
            int sc=-qsearch(&c,-beta,-alpha,ply+1,qd+1);
            if(SS.stopped) return 0;
            if(sc>best) best=sc;
            if(sc>alpha) alpha=sc;
            if(alpha>=beta) break; }
        return best;
    }
    /* TT probe: any stored depth is >= qsearch's depth 0, so search-backed
     * scores cut off here directly — information reuse, same family as the
     * TT/eval caches. */
    {
        TTEntry *e=&TT[b->hash&TT_MASK];
        if(e->key==b->hash){
            if(e->flag==TT_EXACTF) return e->score;
            if(e->flag==TT_LOWERF && e->score>=beta) return e->score;
            if(e->flag==TT_UPPERF && e->score<=alpha) return e->score;
        }
    }
    int stand = eval_stm(b);
    if(stand>=beta) return beta;
    if(stand>alpha) alpha=stand;
    Move mv[256]; int n=0, cn=0; Move caps[256]; int cs[256];
    if(qd==0){ /* full legal list needed below for first-ply quiet checks */
        n=gen_legal(b,mv);
        for(int i=0;i<n;i++){ Move m=mv[i];
            if(is_capture(b,m) || MV_PROMO(m)==QUEEN){
                if(is_capture(b,m) && see(b,m)<0) continue;   /* SEE prune losing caps */
                caps[cn]=m; cs[cn]=mvv_lva(b,m); cn++; } }
    } else { /* deeper qsearch only ever searches captures/queen promos:
                generate just those (same order), skip the wasted legality tax */
        Move cl[256]; int ncl=gen_legal_captures(b,cl);
        for(int i=0;i<ncl;i++){ Move m=cl[i];
            if(is_capture(b,m) && see(b,m)<0) continue;   /* SEE prune losing caps */
            caps[cn]=m; cs[cn]=mvv_lva(b,m); cn++; }
    }
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
            /* cheap does-it-check test on a light copy (in_check only reads
             * piece bitboards); pay full make() only for actual checkers */
            Board t=*b; make_light(&t,m);
            if(in_check(&t,!b->side)){
                Board c=*b; make(&c,m);
                int sc=-qsearch(&c,-beta,-alpha,ply+1,qd+1);
                if(SS.stopped) return 0;
                if(sc>=beta) return beta;
                if(sc>alpha) alpha=sc;
            }
        }
    }
    return alpha;
}

static int negamax(Board *b, int depth, int alpha, int beta, int ply, Move prev){
    SS.nodes++;
    if(!(SS.nodes&2047) && (g_stop || now_sec()>SS.stop_time)){ SS.stopped=1; return 0; }
    int pvnode = beta > alpha+1;          /* wide window == PV node (for PV recording) */
    Move excl = (ply<MAXPLY)? SS.excluded[ply] : 0;  /* singular verification skips this move */
    if(ply<MAXPLY) SS.pvlen[ply]=0;       /* leaf/cutoff nodes leave an empty PV here */
    U64 h=b->hash;
    SS.path[SS.path_len++]=h;
    int ret, done=0;
    if(is_rep(h,b->hm)||insufficient(b)){ ret=0; done=1; }
    int checked = done?0:in_check(b,b->side);
    if(!done && checked) depth++;
    if(!done && depth<=0){ ret=qsearch(b,alpha,beta,ply,0); done=1; }

    Move ttm=0; int tt_hit=0, tt_depth=0, tt_flag=0, tt_score=0;
    if(!done){
        TTEntry *e=&TT[h&TT_MASK];
        if(e->key==h){ ttm=e->move; tt_hit=1; tt_depth=e->depth; tt_flag=e->flag; tt_score=e->score;
            if(!excl && e->depth>=depth && ply>0){   /* no TT cutoff during a singular verification */
                if(e->flag==TT_EXACTF){ ret=e->score; done=1; }
                else if(e->flag==TT_LOWERF && e->score>=beta){ ret=e->score; done=1; }
                else if(e->flag==TT_UPPERF && e->score<=alpha){ ret=e->score; done=1; }
            }
        }
    }
    if(done){ SS.path_len--; return ret; }

    /* reverse futility pruning (static null move): at shallow depth in a
     * non-PV node, if the static eval sits so far above beta that conceding a
     * margin per ply still clears beta, assume this node fails high and cut.
     * Not in check; beta clear of mate scores. eval_stm is ~free via the hash. */
    if(!pvnode && !checked && depth<=RFP_DEPTH && beta>-S_MATE_TH && beta<S_MATE_TH){
        int st=eval_stm(b);
        if(st - RFP_MARGIN*depth >= beta){ SS.path_len--; return st; }
    }

    /* null move — only when the static eval already beats beta: if we're
     * statically below beta, "passing" almost never fails high, so the
     * reduced search is wasted; and skipping it avoids some wrong cutoffs
     * where the eval overestimates (near-zugzwang). eval_stm is ~free via
     * the eval hash. */
    if(depth>=3 && !checked && beta<S_MATE_TH && has_non_pawn(b) && eval_stm(b)>=beta){
        Board c=*b;
        /* c is not built via make(), so its hash must be fixed up by hand for
         * the side flip + ep clear (same terms make() would apply). */
        c.hash ^= Z_SIDE;
        if(b->ep>=0) c.hash ^= Z_EP[b->ep&7];
        c.side=!c.side; c.ep=-1;
        c.hm++;   /* a null move is reversible: without this, path entries under
                   * a null move outnumber the clock and is_rep's bound cuts off
                   * legitimate repetition history (missed rep draws broke KBN
                   * mate conversion — found by tests/test_endgame.py) */
        int r = depth>=6?4:3;
        int sc=-negamax(&c,depth-r,-beta,-beta+1,ply+1,0);
        if(SS.stopped){ SS.path_len--; return 0; }
        if(sc>=beta){ SS.path_len--; return beta; }
    }

    int futile=0;
    if(depth<=2 && !checked && (alpha>-S_MATE_TH&&alpha<S_MATE_TH)){
        int st=eval_stm(b);
        futile = st + (depth==1?150:300) <= alpha;
    }
    /* improving: is the static eval better than 2 plies ago (same side)?
     * Non-improving nodes get one extra ply of late-quiet reduction — the
     * position is trending down, so late quiets are even less likely to
     * save it. eval_stm is ~free via the eval hash; in-check nodes record
     * a sentinel and count as not-improving. */
    int improving=0;
    if(ply<MAXPLY){
        int se = checked ? -S_MATE : eval_stm(b);
        SS.seval[ply]=se;
        improving = !checked && ply>=2 && se > SS.seval[ply-2];
    }

    /* Lazy legality: order the PSEUDO-legal list up front (stable sort +
     * per-move scores, so the legal moves' relative order is exactly what
     * order() on the legal list produced), then pay the copy+in_check
     * legality tax per move only as the loop reaches it. On a first-move
     * cutoff — the common case at interior nodes with a TT move — the other
     * ~35 legality tests are never paid. Search-shape is byte-identical:
     * order() runs before any child search (same history/killer state), and
     * illegal moves score but never search. */
    Move pl[256]; int np=gen_pseudo(b,pl);
    Move cm = prev ? SS.counter[b->side][MV_FROM(prev)][MV_TO(prev)] : 0;
    order(b,pl,np,ttm,ply<MAXPLY?ply:MAXPLY-1,cm);

    /* singular extension: a deep, trusted TT fail-high move -- if a reduced-depth
     * search of every OTHER move fails below ttScore-margin, that move is the only
     * good one, so extend it a ply. Skipped inside a verification (excl set). */
    int sing_ext = 0;
    if(!excl && ttm && ply>0 && depth>=8 && tt_hit && tt_depth>=depth-3
       && tt_flag==TT_LOWERF && tt_score>-S_MATE_TH && tt_score<S_MATE_TH){
        int sbeta = tt_score - 2*depth;
        SS.excluded[ply] = ttm;
        SS.path_len--;                    /* verification re-searches this same position */
        int v = negamax(b, (depth-1)/2, sbeta-1, sbeta, ply, prev);
        SS.path_len++;
        SS.excluded[ply] = 0;
        if(!SS.stopped && v < sbeta) sing_ext = 1;
    }

    int best=-S_MATE-1, orig_alpha=alpha; Move bestm=0;
    Move quiets[64]; int nq=0;   /* quiets tried before a cutoff, for history malus */
    int li=0;                    /* index among LEGAL moves (drives PVS/LMR) */
    for(int pi=0;pi<np;pi++){
        Move m=pl[pi];
        if(!is_legal(b,m)) continue;
        if(m==excl) continue;                 /* singular verification: skip the excluded move */
        int i=li++;
        int quiet = !is_capture(b,m) && MV_PROMO(m)==0;
        int ext = (m==ttm)? sing_ext : 0;     /* singular extension applies to the TT move */
        Board c=*b; make(&c,m);
        if(futile && quiet && bestm && !in_check(&c,c.side)){ continue; }
        /* late move pruning: in a non-PV node at shallow depth, once enough
         * quiets have been tried, skip the remaining late quiets outright
         * (fewer when the eval isn't improving). Never skip a checking move. */
        if(!pvnode && quiet && bestm && !checked && depth<=LMP_DEPTH
           && i >= ((3 + depth*depth) >> (improving?0:1)) && !in_check(&c,c.side)){ continue; }
        int sc;
        if(i==0){ sc=-negamax(&c,depth-1+ext,-beta,-alpha,ply+1,m); }
        else {
            int red=1;
            if(depth>=3 && quiet && !checked){ if(i>=12)red=3; else if(i>=3)red=2;
                if(red>1 && !improving) red++; }
            sc=-negamax(&c,depth-red,-alpha-1,-alpha,ply+1,m);
            if(sc>alpha && (red>1 || beta>alpha+1)) sc=-negamax(&c,depth-1+ext,-beta,-alpha,ply+1,m);
        }
        if(SS.stopped){ SS.path_len--; return 0; }
        if(sc>best){ best=sc; bestm=m; }
        if(sc>alpha){ alpha=sc;
            /* record PV: this move + the child's PV (write-only; never read by
             * search, so the tree is unchanged). Only at PV nodes. */
            if(pvnode && ply+1<MAXPLY){
                SS.pv[ply][0]=m;
                int cl=SS.pvlen[ply+1]; if(cl>MAXPLY-1) cl=MAXPLY-1;
                for(int k=0;k<cl;k++) SS.pv[ply][k+1]=SS.pv[ply+1][k];
                SS.pvlen[ply]=cl+1;
            }
        }
        if(alpha>=beta){
            if(quiet && ply<MAXPLY){
                if(SS.killers[ply][0]!=m){ SS.killers[ply][1]=SS.killers[ply][0]; SS.killers[ply][0]=m; }
                int bonus=depth*depth;
                SS.history[b->side][MV_FROM(m)][MV_TO(m)] += bonus;
                /* history gravity: the quiets tried before this cutoff didn't
                 * work here, so penalize them so ordering learns from failures too. */
                for(int q=0;q<nq;q++)
                    SS.history[b->side][MV_FROM(quiets[q])][MV_TO(quiets[q])] -= bonus;
                if(prev) SS.counter[b->side][MV_FROM(prev)][MV_TO(prev)] = m;
            }
            break;
        }
        if(quiet && nq<64) quiets[nq++]=m;
    }
    /* no legal move searched: mate/stalemate normally, but during a singular
     * verification it just means the excluded move was the only one -> fail low
     * so the caller treats it as singular (a forced move gets extended). */
    if(!li){ SS.path_len--; return excl ? alpha : (checked? -S_MATE+ply : 0); }
    if(!excl){   /* don't pollute this position's TT entry from a verification search */
        int flag = best<=orig_alpha?TT_UPPERF : best>=beta?TT_LOWERF : TT_EXACTF;
        TTEntry *e=&TT[h&TT_MASK];
        e->key=h; e->depth=depth; e->flag=flag; e->score=best; e->move=bestm;
    }
    SS.path_len--;
    return best;
}

static void uci_of(Move m, char *out){
    int f=MV_FROM(m), t=MV_TO(m);
    out[0]='a'+(f&7); out[1]='1'+(f>>3); out[2]='a'+(t&7); out[3]='1'+(t>>3);
    int pr=MV_PROMO(m);
    /* promo piece type: 1=N,2=B,3=R,4=Q (see MK_MOVE/PIECE enum) — index 0
     * is unused (pr=0 means no promotion, guarded by the `if(pr)` above). */
    if(pr){ out[4]=" nbrq"[pr]; out[5]=0; } else out[4]=0;
}

/* One Lazy-SMP worker: runs iterative deepening on a private search state,
 * sharing TT/eval-hash with the others. Helpers stagger their start depth to
 * diversify what fills the shared TT. Only the main thread's result is used. */
typedef struct {
    Board root;
    const U64 *ghist; int nghist;   /* game-history hashes to seed SS.path */
    double start, stop_time, opt_time, max_time;
    int max_depth, id, is_main;
    /* outputs (main thread only) */
    Move best, second; int score, cd; long nodes;
    Move pv[MAXPLY]; int pvlen;   /* principal variation of the last completed iter */
} ThreadCtx;

static void run_id(ThreadCtx *tc){
    memset(&SS,0,sizeof(SS));
    for(int i=0;i<tc->nghist;i++) SS.path[SS.path_len++]=tc->ghist[i];
    SS.stop_time = tc->stop_time;
    Board b = tc->root;
    Move root[256]; int rn=gen_legal(&b,root);
    if(!rn){ if(tc->is_main){ tc->best=0; tc->second=0; tc->score=0; tc->cd=0; tc->nodes=0; } return; }
    Move best=root[0], second=0; int score=0, cd=0;
    Move prev_best=0; int prev_score=-S_MATE, stable_streak=0;
    int d0 = tc->is_main ? 1 : (2 + (tc->id % 3));   /* helpers start deeper */
    for(int depth=d0; depth<=tc->max_depth; depth++){
        if(g_stop) break;
        /* Aspiration window: once the score has settled (depth>4) most iterations
         * land near the last one, so search the root inside a narrow band around
         * `score` — a tighter window prunes far more. Widen and re-search only on
         * a fail-high/low. Shallow plies keep the full window (score not settled;
         * helpers start at depth<=4 so their first pass is always full-window). */
        int delta = 20;
        int alpha0 = depth<=4 ? -S_MATE : score-delta;
        int beta0  = depth<=4 ?  S_MATE : score+delta;
        int bm_found=0; Move bm=0, sm=0; int bs=-S_MATE-1, ss=-S_MATE-1;
        Move iter_pv[MAXPLY]; int iter_pvlen=0;   /* root PV of this iteration */
        for(;;){
            int a=alpha0, bt=beta0;
            bm_found=0; bm=0; sm=0; bs=-S_MATE-1; ss=-S_MATE-1;
            order(&b,root,rn,best,0,0);
            for(int i=0;i<rn;i++){
                Board c=b; make(&c,root[i]);
                int sc;
                if(i==0) sc=-negamax(&c,depth-1,-bt,-a,1,root[i]);
                else { sc=-negamax(&c,depth-1,-a-1,-a,1,root[i]);
                       if(sc>a) sc=-negamax(&c,depth-1,-bt,-a,1,root[i]); }
                if(SS.stopped) break;
                if(sc>bs){ ss=bs; sm=bm; bs=sc; bm=root[i]; bm_found=1;
                    /* root PV = this move + its child's PV (from ply 1) */
                    iter_pv[0]=root[i];
                    int cl=SS.pvlen[1]; if(cl>MAXPLY-1) cl=MAXPLY-1;
                    for(int k=0;k<cl;k++) iter_pv[k+1]=SS.pv[1][k];
                    iter_pvlen=cl+1;
                }
                else if(sc>ss){ ss=sc; sm=root[i]; }
                if(sc>a) a=sc;
            }
            if(SS.stopped) break;
            if(bs<=alpha0 && alpha0>-S_MATE){        /* fail low: widen downward, re-search */
                alpha0 = bs-delta; delta += delta;
                if(alpha0<-S_MATE) alpha0=-S_MATE;
                continue;
            }
            if(bs>=beta0 && beta0<S_MATE){           /* fail high: widen upward, re-search */
                beta0 = bs+delta; delta += delta;
                if(beta0>S_MATE) beta0=S_MATE;
                continue;
            }
            break;   /* score inside the window: accept this iteration */
        }
        if(SS.stopped) break;
        if(bm_found){ best=bm; score=bs; cd=depth; second=sm;
            tc->pvlen=iter_pvlen;                    /* publish this completed iter's PV */
            for(int k=0;k<iter_pvlen;k++) tc->pv[k]=iter_pv[k];
            if(tc->is_main){   /* only main writes the root entry c_pv reads */
                U64 rh=b.hash; TTEntry *re=&TT[rh&TT_MASK];
                re->key=rh; re->depth=depth; re->flag=TT_EXACTF; re->score=score; re->move=best;
            }
            for(int i=0;i<rn;i++) if(root[i]==best){ Move t=root[i]; for(int j=i;j>0;j--)root[j]=root[j-1]; root[0]=t; break; } }
        if(score>S_MATE_TH||score<-S_MATE_TH) break;
        /* Time management. Fixed movetime (max==opt) keeps the exact old rule.
         * Clock mode (max>opt) adapts around the optimum budget:
         *   - falling eval (score dropped vs the previous iteration) is a real
         *     "we're in trouble, look harder" signal -> spend more;
         *   - a best move settled for several iterations is easy -> bank time
         *     for later moves; capped by the hard maximum.
         * Best-move flip-flopping is NOT used to extend: in flat/quiet
         * positions the PV oscillates between equal moves — noise, not
         * difficulty (an early draft extended there and it was backwards). */
        double soft;
        if(tc->max_time > tc->opt_time*1.01){
            int stable = (best==prev_best);
            stable_streak = stable ? stable_streak+1 : 0;
            double mult = 1.0;
            if(depth>=6 && score < prev_score-40) mult = 1.8;   /* falling eval */
            else if(stable_streak>=3) mult = 0.66;              /* easy, settled */
            soft = tc->opt_time * 0.5 * mult;
            if(soft > tc->max_time*0.5) soft = tc->max_time*0.5;
        } else {
            soft = tc->opt_time*0.5;
        }
        prev_best=best; prev_score=score;
        if(now_sec()-tc->start > soft) break;
    }
    if(tc->is_main){
        tc->best=best; tc->second=second; tc->score=score; tc->cd=cd; tc->nodes=SS.nodes;
        g_stop=1;   /* tell helpers to wind down */
    }
}

static void* thread_entry(void* arg){ run_id((ThreadCtx*)arg); return NULL; }

/* Find the TRUE 2nd-best root move: a fresh full-window root search that
 * excludes `best`. Runs single-threaded on the main thread after the main
 * search, reusing its warm TT (so it is cheap). Alpha starts at -inf, so the
 * best-of-the-rest raises alpha and is scored exactly by PVS -- exactly how the
 * main search finds `best`. Returns 0 if there is no legal alternative. */
static Move root_second(const Board *rootb, Move best, int maxdepth,
                        const U64 *ghist, int nghist, double stop_time){
    memset(&SS,0,sizeof(SS));
    for(int i=0;i<nghist && i<PATH_CAP;i++) SS.path[SS.path_len++]=ghist[i];
    SS.stop_time = stop_time;
    Board b = *rootb;
    Move root[256]; int rn=gen_legal(&b,root);
    if(rn<=1) return 0;
    if(maxdepth<1) maxdepth=1;
    /* Iterative deepening over the non-best moves, so a sensible 2nd move is
     * always available even if the budget runs out before full depth (the
     * sibling subtrees are cold -- the main search failed them low early). */
    Move sm=0;
    for(int depth=1; depth<=maxdepth; depth++){
        order(&b,root,rn, sm?sm:best, 0,0);  /* last iter's 2nd sorts first */
        Move dsm=0; int ds=-S_MATE-1, a=-S_MATE; int first=1;
        for(int i=0;i<rn;i++){
            if(root[i]==best) continue;
            Board c=b; make(&c,root[i]);
            int sc;
            if(first){ sc=-negamax(&c,depth-1,-S_MATE,-a,1,root[i]); first=0; }
            else { sc=-negamax(&c,depth-1,-a-1,-a,1,root[i]);
                   if(sc>a && !SS.stopped) sc=-negamax(&c,depth-1,-S_MATE,-a,1,root[i]); }
            if(SS.stopped) break;
            if(sc>ds){ ds=sc; dsm=root[i]; }
            if(sc>a) a=sc;
        }
        if(SS.stopped) break;                /* depth incomplete: keep prior sm */
        sm=dsm;
        if(ds>S_MATE_TH||ds<-S_MATE_TH) break;
    }
    return sm;
}

/* Stored principal variation of the last c_search (root line captured by the
 * triangular-PV table). Formatted by c_get_pv — no TT walk, so it never
 * truncates the way walking the (lossy, overwrite-heavy) TT does. */
static Move g_pv[MAXPLY]; static int g_pvlen=0;

/* Public API: search from startfen after the given space-separated UCI moves.
 * Fills uci_out (>=6 bytes), depth_out, nodes_out; returns score (stm cp). */
static int g_search_init=0;
int c_search(const char *startfen, const char *moves, double movetime, double max_time,
             int max_depth, char *uci_out, char *second_out, int *depth_out, long *nodes_out){
    if(max_time < movetime) max_time = movetime;   /* max budget >= optimum */
    if(max_depth<=0) max_depth=64;
    if(!g_init){ init_tables(); g_init=1; }
    if(!g_search_init){ TT=calloc(TT_SIZE,sizeof(TTEntry)); EH=calloc(EH_SIZE,sizeof(EHEntry)); g_search_init=1; }
    Board b; if(set_fen(&b,startfen)){ uci_out[0]=0; return 0; }
    /* replay moves to build the board + game-history hashes (to seed each
     * worker's repetition path) */
    static _Thread_local U64 ghist[4096]; int nghist=0;
    ghist[nghist++]=b.hash;
    if(moves && *moves){
        const char *p=moves;
        while(*p){
            while(*p==' ')p++;
            if(!*p)break;
            int ff=p[0]-'a', fr=p[1]-'1', tf=p[2]-'a', tr=p[3]-'1';
            int from=fr*8+ff, to=tr*8+tf, promo=0, flag=0;
            char pc=p[4];
            if(pc>='a'&&pc<='z'&&pc!=' '){ promo = pc=='n'?KNIGHT:pc=='b'?BISHOP:pc=='r'?ROOK:pc=='q'?QUEEN:0; p++; }
            int mover=piece_on(&b,from);
            if(mover==PAWN){ if(to==b.ep && ((to&7)!=(from&7))) flag=1;
                else if(abs(tr-fr)==2) flag=3; }
            if(mover==KING && abs(tf-ff)==2) flag=2;
            Move m=MK_MOVE(from,to,promo,flag);
            make(&b,m);
            if(nghist >= (int)(sizeof(ghist)/sizeof(ghist[0]))-4){
                memmove(ghist, ghist+256, (nghist-256)*sizeof(U64)); nghist-=256;
            }
            ghist[nghist++]=b.hash;
            p+=4; while(*p&&*p!=' ')p++;
        }
    }
    double start=now_sec();
    int T = g_threads;
    g_stop = 0;
    ThreadCtx ctx[MAX_THREADS];
    pthread_t th[MAX_THREADS];
    for(int k=0;k<T;k++){
        ctx[k].root=b; ctx[k].ghist=ghist; ctx[k].nghist=nghist;
        ctx[k].start=start; ctx[k].stop_time=start+max_time;
        ctx[k].opt_time=movetime; ctx[k].max_time=max_time;
        ctx[k].max_depth=max_depth; ctx[k].id=k; ctx[k].is_main=(k==0);
        ctx[k].best=0; ctx[k].second=0; ctx[k].score=0; ctx[k].cd=0; ctx[k].nodes=0;
    }
    for(int k=1;k<T;k++) pthread_create(&th[k], NULL, thread_entry, &ctx[k]);
    run_id(&ctx[0]);                       /* main thread runs in-place */
    for(int k=1;k<T;k++) pthread_join(th[k], NULL);

    Move best=ctx[0].best;
    if(!best){ uci_out[0]=0; g_pvlen=0; return 0; }
    uci_of(best,uci_out);
    g_pvlen = ctx[0].pvlen;                 /* stash the PV for c_get_pv */
    for(int i=0;i<g_pvlen && i<MAXPLY;i++) g_pv[i]=ctx[0].pv[i];
    if(second_out){
        second_out[0]=0;
        if(g_want_second){          /* real 2nd move via a full-window exclude-best pass */
            g_stop=0;               /* helpers already joined; this is single-threaded */
            Move snd=root_second(&b, best, ctx[0].cd, ghist, nghist, now_sec()+movetime*0.5);
            if(snd) uci_of(snd,second_out);
        }
    }
    if(depth_out)*depth_out=ctx[0].cd;
    if(nodes_out)*nodes_out=ctx[0].nodes;
    return ctx[0].score;
}

/* Principal variation from the last search's triangular PV table (full length,
 * never TT-truncated), as space-separated UCI into pv_out. */
void c_get_pv(char *pv_out, int maxlen){
    int pos=0;
    for(int i=0;i<g_pvlen;i++){
        char u[8]; uci_of(g_pv[i],u); int ul=(int)strlen(u);
        if(pos+ul+1>=maxlen) break;
        if(pos) pv_out[pos++]=' ';
        memcpy(pv_out+pos,u,ul); pos+=ul;
    }
    pv_out[pos]=0;
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
        U64 h=b.hash;
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
