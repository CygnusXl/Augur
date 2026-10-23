/*
 * augur_cm: an exact (lossless) predictive codec.
 *
 * A bitwise context-mixing model predicts each next bit; a binary arithmetic
 * coder turns those predictions into bits on the wire. The decoder runs the
 * identical model on the data decoded so far, so only the model's surprises
 * cost bits. Output is byte-for-byte reproducible.
 *
 * Everything is integer arithmetic (no floating point anywhere), so the
 * encoder and decoder agree on any machine and compiler. That is the property
 * a shared model across two computers needs, and floating-point neural
 * models do not give it for free.
 *
 * This is a deliberately small design in the lpaq family: hashed context
 * models of several orders, one match model, one gated logistic mixer.
 * It is a measurement baseline, not a state-of-the-art compressor.
 *
 * Stream format: 8-byte little-endian length, then the arithmetic-coded body.
 */

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define N_ORD 8
#define N_IN (N_ORD + 3) /* direct order-1 + hashed orders + match + bias */
static const int ORDERS[N_ORD] = {1, 2, 3, 4, 5, 6, 8, 12};

#ifndef AUGUR_TABLE_BITS
#define AUGUR_TABLE_BITS 22
#endif
#ifndef AUGUR_MIX_LR
#define AUGUR_MIX_LR 8
#endif
#ifndef AUGUR_LIMIT
#define AUGUR_LIMIT 30
#endif
#ifndef AUGUR_ORDER_MASK
#define AUGUR_ORDER_MASK 0xff /* bit i enables ORDERS[i]; disabled orders feed 0 (ablation) */
#endif
#ifndef AUGUR_NO_MATCH
#define AUGUR_NO_MATCH 0 /* 1 disables the match model (ablation) */
#endif
#define MATCH_MIN 5
#define MATCH_HASH_BITS 20

/* ---- logistic helpers (integer only) ---------------------------------- */
static int squash_t[4096];
static int stretch_t[4096];
static int tables_ready = 0;

static int squash_calc(int d) {
    static const int t[33] = {1,    2,    3,    6,    10,   16,   27,   45,   73,
                              120,  194,  310,  488,  747,  1101, 1546, 2047, 2549,
                              2994, 3348, 3607, 3785, 3901, 3975, 4022, 4050, 4068,
                              4079, 4085, 4089, 4092, 4093, 4094};
    if (d > 2047) return 4095;
    if (d < -2047) return 0;
    int w = d & 127;
    int i = (d >> 7) + 16;
    return (t[i] * (128 - w) + t[i + 1] * w + 64) >> 7;
}

static void init_tables(void) {
    if (tables_ready) return;
    for (int i = 0; i < 4096; i++) squash_t[i] = squash_calc(i - 2048);
    int pi = 0;
    for (int x = -2047; x <= 2047; x++) {
        int v = squash_calc(x);
        for (int i = pi; i <= v; i++) stretch_t[i] = x;
        pi = v + 1;
    }
    for (int i = pi; i < 4096; i++) stretch_t[i] = 2047;
    tables_ready = 1;
}
static inline int squash(int d) {
    if (d > 2047) d = 2047;
    if (d < -2047) d = -2047;
    return squash_t[d + 2048];
}
static inline int stretch(int p) { return stretch_t[p]; }

/* ---- adaptive probability slot: 22-bit probability, 10-bit count ------- */
static int32_t rec_t[1024];
static int rec_ready = 0;
static void init_rec(void) {
    if (rec_ready) return;
    for (int i = 0; i < 1024; i++) rec_t[i] = (int32_t)(65536 * 2 / (2 * i + 3));
    rec_ready = 1;
}
#define SLOT_INIT ((uint32_t)(1u << 31)) /* p = 0.5, n = 0 */
static inline int slot_p12(uint32_t s) { return (int)(s >> 20); }
static inline void slot_update(uint32_t *s, int y, int limit) {
    uint32_t v = *s;
    int n = (int)(v & 1023);
    int64_t p = (int64_t)(v >> 10);
    int64_t target = (int64_t)y << 22;
    p += ((target - p) * rec_t[n]) >> 16;
    if (p < 0) p = 0;
    if (p > (1 << 22) - 1) p = (1 << 22) - 1;
    if (n < limit) n++;
    *s = ((uint32_t)p << 10) | (uint32_t)n;
}

/* ---- model ------------------------------------------------------------- */
typedef struct {
    uint32_t *tab[N_ORD];
    uint32_t *o0;            /* 256 x 256: previous byte x partial current byte (direct order-1) */
    uint32_t *mm;            /* match model slots */
    int32_t *w;              /* mixer weights: 256 sets x N_IN */
    uint8_t *buf;
    int32_t *mhash;
    size_t pos, cap;
    uint32_t c0;             /* partial byte with leading 1 */
    uint64_t hist;           /* last 8 bytes */
    uint64_t hctx[N_ORD];    /* per-order context hash at byte boundary */
    uint32_t *cur[N_ORD];    /* slot used for the current bit */
    uint32_t *cur0, *curm;
    int st[N_IN];
    int pr;                  /* final probability, 12 bit */
    int mbit;                /* expected bit from the match model, -1 if none */
    size_t mptr;
    int mlen;
    int bitpos;
    int tbits;
} Model;

static int model_init(Model *m, size_t cap, int tbits) {
    init_tables();
    init_rec();
    memset(m, 0, sizeof(*m));
    m->tbits = tbits;
    size_t tsz = (size_t)1 << tbits;
    for (int i = 0; i < N_ORD; i++) {
        m->tab[i] = (uint32_t *)malloc(tsz * sizeof(uint32_t));
        if (!m->tab[i]) return -1;
        for (size_t j = 0; j < tsz; j++) m->tab[i][j] = SLOT_INIT;
    }
    m->o0 = (uint32_t *)malloc(65536 * sizeof(uint32_t));
    m->mm = (uint32_t *)malloc(64 * 2 * sizeof(uint32_t));
    m->w = (int32_t *)malloc(256 * N_IN * sizeof(int32_t));
    m->buf = (uint8_t *)malloc(cap + 8);
    m->mhash = (int32_t *)calloc((size_t)1 << MATCH_HASH_BITS, sizeof(int32_t));
    if (!m->o0 || !m->mm || !m->w || !m->buf || !m->mhash) return -1;
    for (int i = 0; i < 65536; i++) m->o0[i] = SLOT_INIT;
    for (int i = 0; i < 128; i++) m->mm[i] = SLOT_INIT;
    for (int i = 0; i < 256 * N_IN; i++) m->w[i] = 65536 / 4;
    m->cap = cap;
    m->c0 = 1;
    m->mbit = -1;
    return 0;
}

static void model_free(Model *m) {
    for (int i = 0; i < N_ORD; i++) free(m->tab[i]);
    free(m->o0);
    free(m->mm);
    free(m->w);
    free(m->buf);
    free(m->mhash);
}

static inline uint64_t mix64(uint64_t x) {
    x ^= x >> 33;
    x *= 0xff51afd7ed558ccdULL;
    x ^= x >> 33;
    x *= 0xc4ceb9fe1a85ec53ULL;
    x ^= x >> 33;
    return x;
}

static void byte_update_contexts(Model *m) {
    for (int i = 0; i < N_ORD; i++) {
        int o = ORDERS[i];
        uint64_t mask = (o >= 8) ? ~0ULL : ((1ULL << (8 * o)) - 1);
        uint64_t c = m->hist & mask;
        if (o > 8) c = m->hist; /* order 12 is approximated by the last 8 bytes plus older hash */
        m->hctx[i] = mix64(c * 0x9E3779B97F4A7C15ULL + (uint64_t)(i + 1));
    }
    /* order-12: fold bytes 9..12 from the buffer */
    if (m->pos >= 12) {
        uint64_t older = 0;
        for (int k = 8; k < 12; k++) older = (older << 8) | m->buf[m->pos - 1 - k];
        m->hctx[N_ORD - 1] = mix64(m->hctx[N_ORD - 1] ^ (older * 0xD6E8FEB86659FD93ULL));
    }
    /* match model: maintain pointer */
    if (m->mlen > 0 && m->mptr < m->pos && m->buf[m->mptr] == m->buf[m->pos - 1]) {
        m->mlen++;
        m->mptr++;
    } else {
        m->mlen = 0;
    }
    if (m->pos >= MATCH_MIN) {
        uint64_t h = 0;
        for (int k = 0; k < MATCH_MIN; k++) h = (h << 8) | m->buf[m->pos - 1 - k];
        uint32_t hi = (uint32_t)(mix64(h) >> (64 - MATCH_HASH_BITS));
        if (m->mlen == 0) {
            int32_t cand = m->mhash[hi];
            if (cand > 0) {
                size_t p = (size_t)cand;
                int len = 0;
                while (len < 32 && p > (size_t)len && m->buf[p - 1 - len] == m->buf[m->pos - 1 - len]) len++;
                if (len >= MATCH_MIN) {
                    m->mlen = len;
                    m->mptr = p;
                }
            }
        }
        m->mhash[hi] = (int32_t)m->pos;
    }
}

/* Predict the next bit: returns P(bit = 1) in (0, 4096). */
static int model_predict(Model *m) {
    uint32_t c0 = m->c0;
    int k = 0;
    uint32_t c1 = (uint32_t)(m->hist & 0xff);
    m->cur0 = &m->o0[(c1 << 8) | c0];
    m->st[k++] = stretch(slot_p12(*m->cur0));
    uint32_t mask = ((uint32_t)1 << m->tbits) - 1;
    for (int i = 0; i < N_ORD; i++) {
        uint32_t idx = (uint32_t)((m->hctx[i] + (uint64_t)c0 * 0x9E3779B1ULL) * 0x2545F4914F6CDD1DULL >> 32) & mask;
        if (!((AUGUR_ORDER_MASK >> i) & 1)) {
            m->cur[i] = NULL;
            m->st[k++] = 0;
            continue;
        }
        m->cur[i] = &m->tab[i][idx];
        m->st[k++] = stretch(slot_p12(*m->cur[i]));
    }
    /* match model */
    m->mbit = -1;
    m->curm = NULL;
    if (!AUGUR_NO_MATCH && m->mlen > 0 && m->mptr < m->pos) {
        uint32_t eb = (uint32_t)m->buf[m->mptr] | 256u;
        /* does the expected byte agree with the bits seen so far? */
        if ((eb >> (8 - m->bitpos)) == c0) {
            m->mbit = (int)((eb >> (7 - m->bitpos)) & 1);
            int lb = m->mlen > 31 ? 31 : m->mlen;
            m->curm = &m->mm[(lb << 1) | m->mbit];
            m->st[k++] = stretch(slot_p12(*m->curm));
        } else {
            m->st[k++] = 0;
        }
    } else {
        m->st[k++] = 0;
    }
    m->st[k++] = 256; /* bias */
    int32_t *w = &m->w[(size_t)c0 * N_IN];
    int64_t dot = 0;
    for (int i = 0; i < N_IN; i++) dot += (int64_t)w[i] * m->st[i];
    int d = (int)(dot >> 16);
    int p = squash(d);
    if (p < 1) p = 1;
    if (p > 4095) p = 4095;
    m->pr = p;
    return p;
}

static void model_update(Model *m, int y) {
    int err = ((y << 12) - m->pr);
    int32_t *w = &m->w[(size_t)m->c0 * N_IN];
    for (int i = 0; i < N_IN; i++) {
        int64_t d = ((int64_t)m->st[i] * err * AUGUR_MIX_LR) >> 14;
        w[i] += (int32_t)d;
    }
    slot_update(m->cur0, y, AUGUR_LIMIT);
    for (int i = 0; i < N_ORD; i++)
        if (m->cur[i]) slot_update(m->cur[i], y, AUGUR_LIMIT);
    if (m->curm) slot_update(m->curm, y, 1023);
    m->c0 = (m->c0 << 1) | (uint32_t)y;
    m->bitpos++;
    if (m->bitpos == 8) {
        uint8_t b = (uint8_t)(m->c0 & 0xff);
        m->buf[m->pos++] = b;
        m->hist = (m->hist << 8) | b;
        m->c0 = 1;
        m->bitpos = 0;
        byte_update_contexts(m);
    }
}

/* ---- public API -------------------------------------------------------- */
size_t augur_cm_bound(size_t n) { return n + n / 8 + 64; }

size_t augur_cm_compress(const uint8_t *in, size_t n, uint8_t *out, size_t cap) {
    if (cap < 16) return 0;
    for (int i = 0; i < 8; i++) out[i] = (uint8_t)((uint64_t)n >> (8 * i));
    size_t o = 8;
    Model m;
    if (model_init(&m, n, AUGUR_TABLE_BITS) != 0) {
        model_free(&m);
        return 0;
    }
    uint32_t x1 = 0, x2 = 0xffffffffu;
    for (size_t i = 0; i < n; i++) {
        for (int b = 7; b >= 0; b--) {
            int y = (in[i] >> b) & 1;
            int p = model_predict(&m);
            uint32_t xmid = x1 + (uint32_t)(((uint64_t)(x2 - x1) * (uint32_t)p) >> 12);
            if (y) x2 = xmid; else x1 = xmid + 1;
            model_update(&m, y);
            while (((x1 ^ x2) & 0xff000000u) == 0) {
                if (o >= cap) { model_free(&m); return 0; }
                out[o++] = (uint8_t)(x2 >> 24);
                x1 <<= 8;
                x2 = (x2 << 8) | 255;
            }
        }
    }
    if (o + 4 > cap) { model_free(&m); return 0; }
    out[o++] = (uint8_t)(x1 >> 24);
    out[o++] = (uint8_t)(x1 >> 16);
    out[o++] = (uint8_t)(x1 >> 8);
    out[o++] = (uint8_t)x1;
    model_free(&m);
    return o;
}

/* Returns the number of bytes produced (== stored length), or 0 on error.
 * Never reads past `in` or writes past `out`; corrupt input yields wrong
 * bytes, not a crash. */
size_t augur_cm_decompress(const uint8_t *in, size_t n_in, uint8_t *out, size_t out_cap) {
    if (n_in < 8) return 0;
    uint64_t n = 0;
    for (int i = 0; i < 8; i++) n |= (uint64_t)in[i] << (8 * i);
    if (n > out_cap) return 0;
    if (n == 0) return 0;
    Model m;
    if (model_init(&m, (size_t)n, AUGUR_TABLE_BITS) != 0) {
        model_free(&m);
        return 0;
    }
    size_t ip = 8;
    uint32_t x1 = 0, x2 = 0xffffffffu, x = 0;
    for (int i = 0; i < 4; i++) x = (x << 8) | (ip < n_in ? in[ip++] : 0);
    for (size_t i = 0; i < n; i++) {
        uint32_t c = 0;
        for (int b = 7; b >= 0; b--) {
            int p = model_predict(&m);
            uint32_t xmid = x1 + (uint32_t)(((uint64_t)(x2 - x1) * (uint32_t)p) >> 12);
            int y = x <= xmid;
            if (y) x2 = xmid; else x1 = xmid + 1;
            model_update(&m, y);
            c = (c << 1) | (uint32_t)y;
            while (((x1 ^ x2) & 0xff000000u) == 0) {
                x1 <<= 8;
                x2 = (x2 << 8) | 255;
                x = (x << 8) | (ip < n_in ? in[ip++] : 0);
            }
        }
        out[i] = (uint8_t)c;
    }
    model_free(&m);
    return (size_t)n;
}
