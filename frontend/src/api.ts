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
  observations_with_event_id?: number;
  unique_event_ids?: number;
  reliability_tier_counts: Record<string, number>;
  observation_type_counts: Record<string, number>;
  source_type_counts?: Record<string, number>;
  external_id_systems?: Record<string, number>;
}

export const getStats = () => j<CorpusStats>(`/api/stats`);
export const getRuns = () => j<RunSummary[]>(`/api/research-runs`);
export const getHypotheses = (runId: string) => j<Hypothesis[]>(`/api/research-runs/${runId}/hypotheses`);
export const getEntities = (q?: string) =>
  j<any[]>(`/api/entities?limit=500${q ? `&q=${encodeURIComponent(q)}` : ""}`);
export const getObservations = (opts?: { observation_type?: string; q?: string }) => {
  const params = new URLSearchParams({ limit: "800" });
  if (opts?.observation_type) params.set("observation_type", opts.observation_type);
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
