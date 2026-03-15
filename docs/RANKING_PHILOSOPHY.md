# RepoScout — Ranking Philosophy

> A distilled account of what the ranking system believes, why, and how it was validated.  
> The full engineering record is in `tuning_log.md`.

---

## The core claim

RepoScout uses deterministic signals to filter structural noise and ensure
relevance can beat popularity. Semantic reasoning is applied only where
query intent cannot be resolved structurally.

This boundary was found empirically through a seven-version benchmark
harness, not assumed upfront.

---

## What the system ranks

RepoScout scores repositories on two independent dimensions:

| Dimension | Who computes it | What it measures |
|-----------|----------------|-----------------|
| `quality_score` (0–70) | Deterministic heuristics | Repo health: stars, recency, license, maintenance signals |
| `relevance_score` (0–100) | LLM (Claude) | Semantic fit to the user's specific query |
| `overall_score` | Weighted blend | `0.4 × quality + 0.6 × relevance` |

Relevance is weighted higher because a high-quality repo that doesn't match
the user's query is not useful. A moderately maintained repo that exactly
matches is more valuable.

**Proof:** `LOW_STAR NDCG = 1.000` across all benchmark versions — low-star
niche tools (kopf, zep, python-json-logger) consistently beat 10-80× larger
unrelated repos when the query is specific enough.

---

## The six ranking rules

Each rule was added to address a specific measured defect class and validated
against the benchmark before merging.

### 1. Relevance beats popularity
`quality_weight = 0.4`, `relevance_weight = 0.6`

Stars measure adoption, not fit. A 2k-star repo that exactly matches the
query outranks an 85k-star repo that only loosely relates.

### 2. Query intent routes the scoring regime
Queries classified as `implementation_intent` vs `discovery_intent` using
a deterministic regex classifier. All subsequent rules are intent-conditional.

Discovery queries (containing *awesome*, *curated list*, *alternatives*, etc.)
lift the awesome-list cap — curated lists should rank well when the user is
explicitly looking for one.

### 3. Aggregator lists are capped, not banned
For `implementation_intent` queries: awesome-list repos have a quality ceiling
of 20, regardless of star count. A 3,500-star curated list cannot
out-quality-score a 500-star implementation repo.

For `discovery_intent` queries: the cap is lifted.

This prevents *what starred repos exist in this space* from overwhelming
*which repo should I actually use.*

### 4. Tutorial repos require corroboration
For `implementation_intent` queries, repos tagged `tutorial` or `beginner`
must satisfy at least one of:
- **Domain overlap**: ≥2 non-generic query concepts found in repo topics  
- **Production signal**: repo topics include `framework`, `library`, `deployment`, etc.

This stops tutorial repos from entering top-3 on shallow term overlap alone.

### 5. Adoption differentiates topic-equivalent repos
Tutorial/beginner repos on implementation queries require ≥200 stars to be
top-3 eligible, even if they pass domain corroboration.

This handles the edge case where a tutorial repo is topic-accurate
(*rag + langchain*) but has no community adoption (120 stars vs 85,000).
Stars are not arbitrary popularity bias here — they are a proxy for
community validation between otherwise equivalent alternatives.

**Scope:** conditional on tutorial/beginner tags only. Does not affect
any non-tutorial repo, including low-star implementations.

### 6. Structural noise is hard-excluded
Before scoring:
- Archived repos with fewer than 50 stars are excluded entirely  
- Forks with fewer than 20 stars are excluded entirely  
- Cross-platform duplicates are deduplicated (higher-starred version kept)

---

## What the heuristic layer cannot do

One confirmed heuristic limit: single-word ambiguous queries like *embeddings*.

With one token, the system cannot distinguish:
- User wants a vector database implementation  
- User wants an embedding library  
- User wants a curated list of embedding tools

Relevance scores compress across all candidates. An awesome-list repo
survives on residual quality because the heuristic layer has no basis
to discriminate intent from a single word.

This is not a defect. This is the correct boundary.

**Heuristics handle structure. The LLM handles semantics.**

---

## Benchmark validation

Every rule was gated through a 33-query benchmark before merging, including
intentionally adversarial cases:

| Query class | What it tests |
|-------------|--------------|
| `standard` | Canonical unambiguous queries |
| `low_star` | Can relevance beat popularity? |
| `misleading` | Does popularity trap the ranker? |
| `ambiguous` | Do rules distort neutral queries? |
| `noise` | Does junk stay out of top-3? |
| `anti_awesome` | Do aggregators contaminate results? |
| `discovery_intent` | Do curated lists rank when wanted? |

**Acceptance criteria for any rule change:**
- Mean NDCG@3 does not decrease  
- No critical query regresses > 0.15 NDCG  
- No new noise gate failures  
- `LOW_STAR` NDCG ≥ 1.000  
- `AMBIGUOUS` NDCG within 0.05 of previous  
- All discovery-intent queries pass noise gate  

---

## Results summary

| Version | NDCG@3 | Noise failures | Key change |
|---------|--------|---------------|------------|
| Baseline | 0.801 | 5 | Initial locked baseline |
| v1 | 0.824 | 4 | Staleness tightening + awesome-list penalty |
| v2 | 0.843 | 3 | Tutorial/beginner penalties |
| v3 | 0.843 | 2 | Intent classifier + quality cap |
| v4a | 0.843 | 1 | Cap tightened: 25 → 20 |
| v4b | 0.857 | 1 | Tutorial eligibility rule |
| v5 | 0.871 | 1* | Conditional adoption floor |

*q09 ("embeddings") — confirmed semantic failure, not heuristic defect.

**LOW_STAR: 1.000 across all seven versions.**  
**AMBIGUOUS: 0.595 across all seven versions.**

---

## Known tradeoffs

These are intentional decisions. Each one is documented in `SCORING_DECISIONS.md`.

1. **Niche repos can outrank larger repos** when query fit is stronger  
2. **GitHub README presence is unscored** — the API does not confirm it  
3. **License absence is penalised** even for otherwise useful repos  
4. **Awesome-list aggregators rank lower** than implementations by default  
5. **Archived repos below 50 stars are hard-excluded**  
6. **Tutorial repos need corroboration** to compete for implementation queries  
7. **Old but maintained repos are not penalised for age** — recency measures last update, not creation  
8. **Single-word queries produce unpredictable rankings** — semantic layer required  

---

## What comes next

The heuristic layer is complete. Remaining improvements belong to the semantic layer:

- Better LLM relevance for ambiguous single-word queries (q09)  
- Query understanding for vague or broad intents  
- Enriched repo signals (verified README, release cadence, contributor count)  
- Compare mode: explain why repo A outranks repo B for a specific query  

