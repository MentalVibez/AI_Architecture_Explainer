# Scoring Decisions

Every number in the scoring system is documented here.  
If you change a weight, update this file first and explain why.

---

## The two-layer model

```
quality_score   (0–70)  deterministic  computed from API facts
relevance_score (0–100) LLM-assigned   semantic fit to user query
overall_score          = blend(quality, relevance)
```

Quality is capped at 70, not 100. The remaining 30 points can only come from relevance.  
This forces the system to care about semantic fit, not just popular repos.

---

## Overall blend weights

```
overall = round(0.4 × quality + 0.6 × relevance)
```

**Why 60/40 in favour of relevance?**

A high-quality repo that does not match the user's query is not useful.
A moderately maintained repo that exactly matches is more useful than a
mega-star repo that only vaguely relates.

Example that motivated this weight:
- Query: "self-hosted vector database"
- `langchain/langchain` (stars: 85k, quality: 68) scores very high on quality
- `qdrant/qdrant`       (stars: 18k, quality: 45) scores lower on quality
  but its relevance to "self-hosted vector database" is much higher

At 60/40: qdrant ranks above langchain for this query. That is correct.
At 50/50: the results start converging toward "most popular" regardless of query.

**How to validate a weight change:**

1. Run `python tests/scout_benchmark.py --save before.json`
2. Edit the weight in `repo_scout.py`
3. Run `python tests/scout_benchmark.py --save after.json`
4. Run `python tests/scout_benchmark.py --compare before.json after.json`
5. Mean NDCG@3 must not decrease. If it does, revert.

---

## Quality score breakdown (max 70 points)

### Stars (max 22 points)

| Stars     | Points | Rationale |
|-----------|--------|-----------|
| ≥ 5,000   | 22     | Top tier — broad community validation |
| ≥ 1,000   | 18     | Established project |
| ≥ 100     | 12     | Gaining traction |
| ≥ 10      | 5      | Early but real usage |
| < 10      | 0      | Essentially unknown |

**Why stars at all?**  
Stars are an imperfect but real signal of adoption and community trust.
A project with 10k stars has survived more scrutiny than one with 10.
Stars do not measure correctness, but they correlate with documentation,
issue triage, and survival of common edge cases.

**Why not weight stars higher?**  
Stars are gameable and strongly correlated with age. A 2-year-old repo
will always outstar a 6-month-old repo on the same topic. We use them
as a floor check, not a ceiling.

### Recency (max 15 points)

| Days since update | Points | Rationale |
|-------------------|--------|-----------|
| ≤ 30              | 15     | Active maintenance |
| ≤ 90              | 10     | Recently active |
| ≤ 365             | 4      | Possibly maintained |
| > 365             | 0      | Likely abandoned |

**Why recency matters:**  
A repo last touched 3 years ago may have critical security vulnerabilities,
API incompatibilities, or be superseded by better alternatives.
Recency is not about perfection — it is about risk.

**Caveat on GitLab `last_activity_at`:**  
GitLab documents that `last_activity_at` can lag by up to 1 hour.
We treat it as approximate. It is accurate enough for the 30/90/365 buckets.

### License (7 points)

A missing license means users cannot legally use the code in most jurisdictions.
We do not weight license type (MIT vs Apache vs GPL) — that is a user decision.
We only check presence. `NOASSERTION` and `OTHER` are treated as "no license"
because they provide no clear usage rights.

### README — GitLab only (7 points)

GitHub's search API does NOT confirm README presence.  
We only score this signal for GitLab repos where `readme_url` is a real API field.

For GitHub, the README signal is displayed in the UI as "unverified" (`verified=False`)
and contributes zero points to the quality score.

This was FIX [2] from the v0 review. Setting `has_readme=True` for all GitHub repos
was awarding 8 phantom points. Every scoring point must be grounded in real data.

### Description quality (3 points)

A description longer than 40 characters suggests the author cared enough to explain
the project. Short or absent descriptions are a weak negative signal.

### Topics (3 points)

Three or more topics suggests intentional categorisation, not an accidental push.
No bonus beyond 3 — spam repos often load up topics.

### Forks (max 5 points)

| Forks   | Points |
|---------|--------|
| ≥ 500   | 5      |
| ≥ 50    | 2      |
| < 50    | 0      |

Forks are a weak quality signal. A high fork count means people are actively
building on the project. We weight it lightly to avoid over-rewarding large
corporate repos that have high forks for historical reasons.

---

## Noise penalties

These reduce quality_score. They are applied after the base score is computed.

| Flag              | Penalty | Rationale |
|-------------------|---------|-----------|
| `fork`            | -15     | Forks rarely add value unless they have unusual traction |
| `possible mirror` | -10     | Mirrors/backups obscure the original project |
| `no description`  | -5      | Weak signal of abandonment or personal use |

Archived repos and low-traction forks are **hard excluded** before scoring.
They never appear in results. The boundary:
- Archived + stars < 50 → excluded
- Fork + stars < 20 → excluded

High-star archived/forked repos survive because they may be historically
significant or a widely-adopted fork of an inactive upstream.

---

## What the LLM is NOT asked to score

The prompt explicitly excludes:
- stars / forks / recency (already deterministic)
- "production readiness" (ungrounded speculation)
- "code quality" (unverifiable from repo metadata)
- "maintainership" (only ask for facts that are visible in the API response)

The LLM is asked only for:
- Semantic fit to the user's specific query (0–100)
- A 2-sentence insight specific to the query
- Concrete, factual risks (e.g. "Python 2 only", "no tests directory", "last release 2019")

If the LLM invents facts not present in the evidence it was given, that is a
prompt violation. The prompt constraint "report only what the evidence supports"
mirrors Atlas's own LLM prompt discipline.

---

## Known tradeoffs we accept

These are intentional decisions, not bugs. Do not re-litigate them without
updating both this document and running the benchmark first.

**1. Niche repos may outrank larger repos if query fit is much stronger.**  
A 2k-star repo that exactly matches the query will outscore a 70k-star repo
that only loosely relates. This is by design — the 60/40 relevance weight
ensures semantic fit dominates popularity for specific queries.  
*Implication: users searching for specific tools (kopf, zep, python-json-logger)
get the right answer even if the answer is not famous.*

**2. GitHub README presence is intentionally not scored.**  
The GitHub search API does not confirm README existence. We mark the signal
as unverified (`verified=False`) and award zero points.  
*Implication: GitHub repos may appear to rank lower than equivalent GitLab repos
by up to 7 quality points. This is a data availability constraint, not a
platform preference. It will be corrected when we add a verified second-pass
README check for top-N candidates.*

**3. License absence is penalised even if the codebase may still be useful.**  
A missing license creates legal uncertainty for most organizations. We penalise
it as a quality signal because it is a practical adoption barrier.  
*Implication: a brilliant unlicensed repo with 5k stars may rank lower than a
licensed repo with 1k stars. Users can see the "No license" signal in the
evidence panel and make their own judgment.*

**4. Awesome-list aggregators rank lower than implementation repos by design.**  
Repos whose description or name contains "awesome" or "curated list" receive
implicit noise suppression via the heuristic system and are further downweighted
by the LLM's relevance score (aggregators are not implementations).  
*Implication: a query for "awesome machine learning" will still surface
implementation repos above curated lists. If a user genuinely wants an
awesome-list, they can find one via GitHub's native search.*

**5. Archived repos with fewer than 50 stars are hard-excluded.**  
These provide no ongoing value and create noise. The 50-star threshold
preserves historically significant archived projects (e.g. a retired framework
that is still widely referenced).  
*Implication: a query containing the word "archived" will not resurface
hard-excluded archived repos. The exclusion is unconditional.*

**6. Fork penalty applies even when the fork is the user's intended target.**  
Forks with fewer than 20 stars are excluded; forks with 20-499 stars receive
a -15 quality penalty. This suppresses the vast majority of personal forks and
shallow clones.  
*Implication: a popular fork that has diverged significantly from upstream
(e.g. a hardened fork with its own active community) may still rank well if
it has sufficient stars. Low-star forks will not appear in results.*

**7. Old but actively maintained repos are not penalised for their age.**  
The recency score measures days since last update, not days since creation.
A repo created in 2012 that was updated yesterday scores the same recency
as a repo created last week that was also updated yesterday.  
*Implication: mature frameworks like Django, Celery, and Scrapy rank correctly
for relevant queries despite their age.*

**8. Single-word or extremely vague queries produce unpredictable rankings.**  
Queries like "Python" or "chatbot" are too ambiguous for the scoring system to
produce defensible results. The evidence panel and TLDR will reflect this
uncertainty. No ideal ranking is possible for such queries.  
*Implication: query quality is partly the user's responsibility. RepoScout
performs best with queries of 3+ specific terms.*

---

## Benchmark validation

Before merging any weight change, run:

```bash
cd backend
python tests/scout_benchmark.py --save baseline.json
# make your change
python tests/scout_benchmark.py --save new.json
python tests/scout_benchmark.py --compare baseline.json new.json
```

Acceptance criteria:
- Mean NDCG@3 does not decrease
- No single query drops by more than 0.15 NDCG
- Noise tests do not surface junk repos in top-3

The query pack in `scout_benchmark.py` is the authoritative source of truth for
ranking quality. Add new queries when you find ranking failures in real usage.
