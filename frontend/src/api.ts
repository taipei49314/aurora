// Thin typed client for the AURORA API.
export interface Hypothesis {
  hypothesis_id: string;
  generated_name: string;
  human_name: string | null;
  status: string;
  summary: string;
  overall_score: number;
  hype_risk_score: number;
  contradiction_score: number;
  naming_gap_score: number;
  novelty_score: number;
  coherence_score: number;
  acceleration_score: number;
  value_chain_score: number;
  real_investment_score: number;
  demand_score: number;
  bottleneck_score: number;
  cluster_stability_score: number;
  source_independence_score: number;
  data_quality_penalty?: number;
  confidence_band: string;
  entity_ids: string[];
  observation_ids: string[];
  strongest_supporting_evidence: string[];
  strongest_counterevidence: string[];
  missing_evidence: string[];
  disconfirmation_conditions: string[];
  existing_industry_similarity: Record<string, any>;
  score_explanation: Record<string, any>;
}

export interface RunSummary {
  run_id: string;
  cutoff_date: string | null;
  status: string;
  created_at: string;
  n_hypotheses: number;
}

async function j<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json();
}

export const getHealth = () => j<{ status: string; engine: string; snapshot: string; runs: number }>(`/api/health`);

export interface CorpusStats {
  engine: string;
  snapshot_id: string;
  counts: Record<string, number>;
  entities_total: number;
  entities_with_external_ids: number;
  sources_total?: number;
  sources_with_family_id?: number;
  sources_with_event_date?: number;
  sources_with_event_id?: number;
  sources_with_outlet_domain?: number;
  sources_with_wire_id?: number;
  sources_with_geo?: number;
  sources_with_license?: number;
  license_counts?: Record<string, number>;
  observations_with_event_id?: number;
  observations_with_geo?: number;
  observations_with_document_id?: number;
  observations_with_char_span?: number;
  observations_with_char_span_auto?: number;
  observations_missing_char_span?: number;
  char_span_ratio?: number;
  document_link_ratio?: number;
  documents_total?: number;
  documents_with_text?: number;
  document_ids_referenced?: number;
  observation_country_counts?: Record<string, number>;
  entities_with_country?: number;
  entity_country_counts?: Record<string, number>;
  entity_type_counts?: Record<string, number>;
  entities_provisional?: number;
  observations_subject_provisional?: number;
  unique_event_ids?: number;
  reliability_tier_counts: Record<string, number>;
  observation_type_counts: Record<string, number>;
  source_type_counts?: Record<string, number>;
  external_id_systems?: Record<string, number>;
}

export const getStats = () => j<CorpusStats>(`/api/stats`);
export const getRuns = () => j<RunSummary[]>(`/api/research-runs`);
export const getHypotheses = (runId: string) => j<Hypothesis[]>(`/api/research-runs/${runId}/hypotheses`);
export const getEntities = (
  q?: string,
  entityType?: string,
  opts?: { provisional?: boolean },
) => {
  const params = new URLSearchParams({ limit: "500" });
  if (q) params.set("q", q);
  if (entityType) params.set("entity_type", entityType);
  if (opts?.provisional === true) params.set("provisional", "true");
  if (opts?.provisional === false) params.set("provisional", "false");
  return j<any[]>(`/api/entities?${params.toString()}`);
};
export const getObservations = (opts?: {
  observation_type?: string;
  document_id?: string;
  has_char_span?: boolean;
  char_span_auto?: boolean;
  has_document_id?: boolean;
  missing_char_span?: boolean;
  subject_provisional?: boolean;
  provisional_mention?: boolean;
  q?: string;
}) => {
  const params = new URLSearchParams({ limit: "800" });
  if (opts?.observation_type) params.set("observation_type", opts.observation_type);
  if (opts?.document_id) params.set("document_id", opts.document_id);
  if (opts?.has_char_span === true) params.set("has_char_span", "true");
  if (opts?.has_char_span === false) params.set("has_char_span", "false");
  if (opts?.char_span_auto === true) params.set("char_span_auto", "true");
  if (opts?.char_span_auto === false) params.set("char_span_auto", "false");
  if (opts?.has_document_id === true) params.set("has_document_id", "true");
  if (opts?.has_document_id === false) params.set("has_document_id", "false");
  if (opts?.missing_char_span === true) params.set("missing_char_span", "true");
  if (opts?.missing_char_span === false) params.set("missing_char_span", "false");
  if (opts?.subject_provisional === true) params.set("subject_provisional", "true");
  if (opts?.subject_provisional === false) params.set("subject_provisional", "false");
  if (opts?.provisional_mention === true) params.set("provisional_mention", "true");
  if (opts?.provisional_mention === false) params.set("provisional_mention", "false");
  if (opts?.q) params.set("q", opts.q);
  return j<any[]>(`/api/observations?${params.toString()}`);
};
export const getSources = (opts?: {
  reliability_tier?: string;
  source_type?: string;
  q?: string;
}) => {
  const params = new URLSearchParams({ limit: "500" });
  if (opts?.reliability_tier) params.set("reliability_tier", opts.reliability_tier);
  if (opts?.source_type) params.set("source_type", opts.source_type);
  if (opts?.q) params.set("q", opts.q);
  return j<any[]>(`/api/sources?${params.toString()}`);
};
export const getDocument = (documentId: string) =>
  j<any>(`/api/documents/${encodeURIComponent(documentId)}`);
export const getDocuments = (opts?: { q?: string; include_stubs?: boolean }) => {
  const params = new URLSearchParams({ limit: "500" });
  if (opts?.q) params.set("q", opts.q);
  if (opts?.include_stubs === false) params.set("include_stubs", "false");
  return j<any[]>(`/api/documents?${params.toString()}`);
};
export const getGraph = (id: string) => j<{ nodes: any[]; edges: any[] }>(`/api/hypotheses/${id}/graph`);
export const getTimeline = (id: string) => j<{ timeline: any[] }>(`/api/hypotheses/${id}/timeline`);
export const getBottlenecks = (id: string) => j<any[]>(`/api/hypotheses/${id}/bottlenecks`);

export const createRun = (cutoff: string | null) =>
  j<{ run_id: string }>(`/api/research-runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cutoff_date: cutoff }),
  });

export const runBacktest = (cutoffs: string[]) =>
  j<any>(`/api/backtests`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cutoffs }),
  });

export const getBacktest = (id: string) => j<any>(`/api/backtests/${id}`);
export const getDivergence = (a: string, b: string) => j<any>(`/api/research-runs/${a}/divergence/${b}`);
export const setHumanName = (id: string, human_name: string) =>
  j<any>(`/api/hypotheses/${id}/human-name`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ human_name }),
  });

export const resolveEntity = (ref: string, external_ids?: { system: string; id: string }[]) =>
  j<{
    ref: string;
    entity_id: string;
    canonical_name: string;
    aliases: string[];
    external_ids: { system: string; id: string }[];
  }>(`/api/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ref, external_ids }),
  });

export const STATUS_COLORS: Record<string, string> = {
  INDUSTRY_CANDIDATE: "#1a7f37",
  EMERGING_CAPABILITY_CLUSTER: "#3b82f6",
  EXISTING_INDUSTRY_VARIANT: "#8250df",
  HYPE_CLUSTER: "#bf8700",
  REJECTED: "#cf222e",
  DORMANT: "#57606a",
  INSUFFICIENT_EVIDENCE: "#57606a",
};
