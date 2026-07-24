import { useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { useCurrentRun } from "../useRun";
import { STATUS_COLORS, Hypothesis } from "../api";

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, marginBottom: 3 }}>
      <span style={{ width: 160, color: "#57606a" }}>{label}</span>
      <div style={{ flex: 1, background: "#eaeef2", height: 8, borderRadius: 4 }}>
        <div style={{ width: `${Math.max(0, Math.min(100, value))}%`, background: "#0969da", height: 8, borderRadius: 4 }} />
      </div>
      <span style={{ width: 34, textAlign: "right" }}>{value.toFixed(0)}</span>
    </div>
  );
}

function Detail({ h }: { h: Hypothesis }) {
  const sim = h.existing_industry_similarity ?? {};
  const bns = h.score_explanation?.bottlenecks ?? [];
  const sc = h.score_explanation?.scoring ?? {};
  const dq = h.score_explanation?.data_quality ?? {};
  return (
    <div style={{ borderTop: "1px solid #d0d7de", marginTop: 8, paddingTop: 10, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
      <div>
        <b style={{ fontSize: 12 }}>Score components</b>
        <ScoreBar label="novelty" value={h.novelty_score} />
        <ScoreBar label="cross-source coherence" value={h.coherence_score} />
        <ScoreBar label="temporal acceleration" value={h.acceleration_score} />
        <ScoreBar label="value chain completeness" value={h.value_chain_score} />
        <ScoreBar label="real investment" value={h.real_investment_score} />
        <ScoreBar label="demand pull" value={h.demand_score} />
        <ScoreBar label="naming gap" value={h.naming_gap_score} />
        <ScoreBar label="source independence" value={h.source_independence_score} />
        <ScoreBar label="cluster stability" value={h.cluster_stability_score} />
        <ScoreBar label="hype risk (penalty)" value={h.hype_risk_score} />
        <ScoreBar label="contradiction (penalty)" value={h.contradiction_score} />
        <ScoreBar label="data quality (penalty)" value={h.data_quality_penalty ?? dq.penalty ?? 0} />
        <div style={{ fontSize: 12, marginTop: 8, color: "#57606a" }}>
          formula: {sc.formula} · weighted sum {sc.weighted_sum} − penalties → <b>{h.overall_score.toFixed(1)}</b>
        </div>
        {dq.factors && (
          <div style={{ fontSize: 11, marginTop: 6, color: "#57606a" }}>
            data_quality factors: date/conf {dq.factors.date_conf_penalty ?? "—"} · reliability{" "}
            {dq.factors.reliability_penalty ?? "—"}
            {dq.factors.tier_counts && (
              <span>
                {" "}
                · tiers {JSON.stringify(dq.factors.tier_counts)}
              </span>
            )}
          </div>
        )}
        <div style={{ fontSize: 12, marginTop: 4 }}>
          nearest existing industry: <b>{sim.best_industry_name ?? "-"}</b> (sim {(sim.similarity ?? 0).toFixed(2)})
        </div>
        <div style={{ fontSize: 12, marginTop: 6 }}>
          <b>entities in cluster</b> · {h.entity_ids?.length ?? 0}
        </div>
      </div>
      <div style={{ fontSize: 12 }}>
        <b>Top bottlenecks</b>
        <ol style={{ margin: "4px 0 10px", paddingLeft: 18 }}>
          {bns.slice(0, 3).map((b: any) => (
            <li key={b.entity_id}>score {b.bottleneck_score} · centrality {b.centrality} · substitutability {b.substitutability}</li>
          ))}
        </ol>
        <b>Strongest counterevidence</b>
        <div style={{ color: "#57606a" }}>{h.strongest_counterevidence.length} items · contradiction {h.contradiction_score.toFixed(0)}</div>
        <b style={{ display: "block", marginTop: 8 }}>Missing evidence</b>
        <div style={{ color: "#57606a" }}>{h.missing_evidence.join(", ") || "none"}</div>
        <b style={{ display: "block", marginTop: 8 }}>Disconfirmation conditions</b>
        <ul style={{ margin: "4px 0", paddingLeft: 16 }}>
          {h.disconfirmation_conditions.slice(0, 4).map((d, i) => <li key={i}>{d}</li>)}
        </ul>
      </div>
    </div>
  );
}

/** Read open hypothesis id from URL (`id`, `hypothesis_id`, or short `h`). */
function parseOpenId(params: URLSearchParams): string | null {
  return params.get("id") || params.get("hypothesis_id") || params.get("h") || null;
}

export function HypothesisExplorer() {
  const { hyps } = useCurrentRun();
  const [searchParams, setSearchParams] = useSearchParams();
  const openId = parseOpenId(searchParams);
  const cardRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const scrolledFor = useRef<string | null>(null);

  const setOpen = (id: string | null) => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        // Normalize to a single canonical param.
        next.delete("hypothesis_id");
        next.delete("h");
        if (id) next.set("id", id);
        else next.delete("id");
        return next;
      },
      { replace: true },
    );
  };

  // Scroll the deep-linked card into view once per id (Dashboard → Explorer).
  useEffect(() => {
    if (!openId || !hyps.data) return;
    if (scrolledFor.current === openId) return;
    const el = cardRefs.current[openId];
    if (!el) return;
    scrolledFor.current = openId;
    el.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [openId, hyps.data]);

  if (!hyps.data) return <p>Loading…</p>;

  const known = openId && hyps.data.some((h) => h.hypothesis_id === openId);

  return (
    <div>
      <h2>Hypothesis Explorer</h2>
      {openId && !known && (
        <p style={{ fontSize: 12, color: "#9a6700", marginBottom: 10 }}>
          No hypothesis matches <code>?id={openId}</code> for this run.
        </p>
      )}
      {hyps.data.map((h) => {
        const isOpen = openId === h.hypothesis_id;
        return (
          <div
            key={h.hypothesis_id}
            ref={(el) => {
              cardRefs.current[h.hypothesis_id] = el;
            }}
            style={{
              border: isOpen ? "1px solid #0969da" : "1px solid #d0d7de",
              borderRadius: 8,
              padding: 12,
              marginBottom: 10,
              background: isOpen ? "#f6f8fa" : undefined,
            }}
          >
            <div
              style={{ display: "flex", alignItems: "center", gap: 12, cursor: "pointer" }}
              onClick={() => setOpen(isOpen ? null : h.hypothesis_id)}
              title={isOpen ? "Collapse detail" : "Expand detail (URL updates for sharing)"}
            >
              <span
                style={{
                  background: STATUS_COLORS[h.status] ?? "#57606a",
                  color: "white",
                  padding: "2px 8px",
                  borderRadius: 12,
                  fontSize: 11,
                  fontWeight: 600,
                }}
              >
                {h.status}
              </span>
              <span style={{ fontWeight: 600, flex: 1 }}>{h.human_name ?? h.generated_name}</span>
              <span style={{ fontSize: 20, fontWeight: 700 }}>{h.overall_score.toFixed(0)}</span>
            </div>
            {isOpen && <Detail h={h} />}
          </div>
        );
      })}
    </div>
  );
}
