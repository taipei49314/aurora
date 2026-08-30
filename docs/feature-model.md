# Feature Model (spec §9)

The feature stage turns a cutoff-filtered `Snapshot` into deterministic sparse
entity profiles. It does not call a language model, use an external embedding,
or maintain a list of industry keywords. The implementation lives in
`backend/aurora/features.py`; `backend/aurora/clustering.py` composes the final
vectors used for feature-space clustering.

## Inputs and construction

For every entity, `build_entity_documents` creates one pseudo-document from:

1. the entity's canonical name and description;
2. excerpts from observations where the entity is the subject; and
3. canonical names of linked object entities.

Observation-type names and object entity-type names are deliberately excluded
from the text. Those generic terms made unrelated clusters easier to chain
together in earlier single-linkage behavior.

`tokenize` lowercases text and keeps tokens of at least two characters matching
`[a-z0-9][a-z0-9\-\+]*`. It removes a fixed list of generic language stopwords,
then `_doc_terms` counts unigrams and adjacent bigrams. The stopword list has no
industry or technology terms.

For entity document `d` and term `t`, the text weight is:

```text
tf(t,d)  = count(t,d) / all_term_counts(d)
idf(t)   = log((1 + document_count) / (1 + document_frequency(t))) + 1
weight   = tf * idf
```

Each TF-IDF vector is L2-normalized. `clustering.entity_vectors` then adds the
entity's normalized observation-type mix under `obs::<TYPE>` dimensions at
weight `0.5`. Cosine similarity compares the resulting sparse vectors.

Separately, `entity_cooccurrence` sums observation confidence for each sorted
subject/object pair. That structural signal feeds graph clustering; it is not
silently folded into the TF-IDF coordinates.

## Determinism and run provenance

- The feature stage is a pure function of the normalized entities and
  observations admitted by the cutoff.
- Sparse keys use stable strings and entity pairs are stored in sorted order.
- `EngineConfig.feature_version` is included in the run manifest.
- The clustering stage records complete-versus-sparse candidate generation,
  retained pair counts, block counts, and entity coverage in
  `feature_space_candidate_diagnostics`.

Changing tokenization, weighting, the observation-type multiplier, or the
feature version changes model behavior and must be treated as an engine change.

## Boundaries

- Tokenization is intentionally small and ASCII-oriented. It does not perform
  stemming, language detection, synonym expansion, or semantic embedding.
- Text associated only with an observation object is represented through that
  object's canonical name, not its complete description.
- TF-IDF and cosine use Python floating-point math. Repository determinism tests
  cover the supported implementation and fixtures; they are not a proof that
  every platform's `libm` is bit-identical at a decision boundary.
- Feature similarity proposes structure. Taxonomy comparison, evidence
  independence, hype, counterevidence, and classification gates decide what the
  structure means.

## Verification

- `tests/test_properties.py` checks cosine properties.
- `tests/test_clustering.py` exercises feature-space grouping, thresholds,
  complete and sparse candidate paths, and oversized-block behavior.
- `tests/test_scoring_determinism_divergence.py` verifies that realized
  candidate diagnostics are preserved in the research-run manifest.
- `tests/test_provisional_entities.py` verifies that the default `PROVISIONAL`
  type does not become a cluster member. All entities still enter the TF-IDF
  document corpus, and callers can stage another entity type; the boundaries
  below therefore still apply.

## Provisional-entity boundary

Clustering membership is filtered by `entity_type`, not by
`metadata.provisional`. The default staged type, `PROVISIONAL`, is not a member
of `CLUSTERABLE_TYPES`, but a caller-supplied staged `COMPANY`, `TECHNOLOGY`, or
other clusterable type can participate before promotion. In addition,
`entity_vectors` builds the TF-IDF corpus from every entity before membership
filtering, so even a default `PROVISIONAL` row can affect document frequency.
Curated cases use the `--no-provisional` lint and scorecard gate; arbitrary
runtime packages must apply the same policy when this distinction matters.
