import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getEntities, getObservations, getSources } from "../api";

type Tab = "entities" | "observations" | "sources";

export function DataExplorer() {
  const [tab, setTab] = useState<Tab>("entities");
  const entities = useQuery({ queryKey: ["entities"], queryFn: getEntities, enabled: tab === "entities" });
  const observations = useQuery({ queryKey: ["observations"], queryFn: getObservations, enabled: tab === "observations" });
  const sources = useQuery({ queryKey: ["sources"], queryFn: getSources, enabled: tab === "sources" });

  const data = tab === "entities" ? entities.data : tab === "observations" ? observations.data : sources.data;
  const cols = tab === "entities" ? ["entity_id", "entity_type", "canonical_name", "country"]
    : tab === "observations" ? ["observation_id", "observation_type", "subject_entity", "observed_at", "confidence"]
    : ["source_id", "source_type", "publisher", "reliability_tier", "independence_group"];

  return (
    <div>
      <h2>Data Explorer</h2>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        {(["entities", "observations", "sources"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            style={{ fontWeight: tab === t ? 700 : 400 }}>{t}</button>
        ))}
      </div>
      <div style={{ overflowX: "auto", maxHeight: 520, overflowY: "auto" }}>
        <table style={{ borderCollapse: "collapse", fontSize: 12, minWidth: 700 }}>
          <thead>
            <tr style={{ textAlign: "left", color: "#57606a", borderBottom: "1px solid #d0d7de", position: "sticky", top: 0, background: "white" }}>
              {cols.map((c) => <th key={c} style={{ padding: 6 }}>{c}</th>)}
            </tr>
          </thead>
          <tbody>
            {(data ?? []).slice(0, 300).map((row: any, i: number) => (
              <tr key={i} style={{ borderBottom: "1px solid #eaeef2" }}>
                {cols.map((c) => <td key={c} style={{ padding: 6 }}>{String(row[c] ?? "")}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!data && <p>Loading…</p>}
    </div>
  );
}
