import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getEntities, getObservations, getSources } from "../api";

type Tab = "entities" | "observations" | "sources";

function formatExternalIds(row: any): string {
  const ids = row.external_ids;
  if (!Array.isArray(ids) || ids.length === 0) return "—";
  return ids
    .map((x: any) => `${x.system ?? "?"}:${x.id ?? "?"}`)
    .join(" · ");
}

function cellValue(tab: Tab, col: string, row: any): string {
  if (tab === "entities" && col === "external_ids") return formatExternalIds(row);
  if (tab === "sources" && col === "independence_group") {
    return String(row.independence_group || "—");
  }
  const v = row[col];
  if (v == null || v === "") return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export function DataExplorer() {
  const [tab, setTab] = useState<Tab>("entities");
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<any | null>(null);

  const entities = useQuery({ queryKey: ["entities"], queryFn: getEntities, enabled: tab === "entities" || !!selected });
  const observations = useQuery({ queryKey: ["observations"], queryFn: getObservations, enabled: tab === "observations" });
  const sources = useQuery({ queryKey: ["sources"], queryFn: getSources, enabled: tab === "sources" });

  const data = tab === "entities" ? entities.data : tab === "observations" ? observations.data : sources.data;
  const cols =
    tab === "entities"
      ? ["entity_type", "canonical_name", "country", "external_ids", "entity_id"]
      : tab === "observations"
        ? ["observation_type", "subject_entity", "observed_at", "confidence", "observation_id"]
        : ["source_type", "publisher", "reliability_tier", "independence_group", "source_id"];

  const filtered = useMemo(() => {
    const rows = data ?? [];
    const needle = q.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter((row: any) => {
      const blob = JSON.stringify(row).toLowerCase();
      return blob.includes(needle);
    });
  }, [data, q]);

  return (
    <div>
      <h2>Data Explorer</h2>
      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap", alignItems: "center" }}>
        {(["entities", "observations", "sources"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => {
              setTab(t);
              setSelected(null);
            }}
            style={{ fontWeight: tab === t ? 700 : 400 }}
          >
            {t}
          </button>
        ))}
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={
            tab === "entities"
              ? "Filter by name, lei:, domain:…"
              : "Filter…"
          }
          style={{ marginLeft: 8, padding: "4px 8px", minWidth: 220, border: "1px solid #d0d7de", borderRadius: 6 }}
        />
        <span style={{ fontSize: 12, color: "#57606a" }}>
          {filtered.length} rows{q ? ` (filtered)` : ""}
        </span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: selected ? "1.4fr 1fr" : "1fr", gap: 16 }}>
        <div style={{ overflowX: "auto", maxHeight: 520, overflowY: "auto" }}>
          <table style={{ borderCollapse: "collapse", fontSize: 12, minWidth: 700 }}>
            <thead>
              <tr
                style={{
                  textAlign: "left",
                  color: "#57606a",
                  borderBottom: "1px solid #d0d7de",
                  position: "sticky",
                  top: 0,
                  background: "white",
                }}
              >
                {cols.map((c) => (
                  <th key={c} style={{ padding: 6 }}>
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.slice(0, 300).map((row: any, i: number) => {
                const active =
                  selected &&
                  ((tab === "entities" && selected.entity_id === row.entity_id) ||
                    (tab === "sources" && selected.source_id === row.source_id) ||
                    (tab === "observations" && selected.observation_id === row.observation_id));
                return (
                  <tr
                    key={i}
                    onClick={() => setSelected(row)}
                    style={{
                      borderBottom: "1px solid #eaeef2",
                      cursor: "pointer",
                      background: active ? "#ddf4ff" : undefined,
                    }}
                  >
                    {cols.map((c) => (
                      <td key={c} style={{ padding: 6, maxWidth: 280, wordBreak: "break-word" }}>
                        {cellValue(tab, c, row)}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {selected && (
          <div
            style={{
              border: "1px solid #d0d7de",
              borderRadius: 8,
              padding: 12,
              fontSize: 12,
              maxHeight: 520,
              overflow: "auto",
              background: "#f6f8fa",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
              <b>Detail</b>
              <button onClick={() => setSelected(null)} style={{ fontSize: 11 }}>
                close
              </button>
            </div>
            {tab === "entities" && (
              <>
                <div style={{ marginBottom: 6 }}>
                  <b>{selected.canonical_name}</b> · {selected.entity_type}
                </div>
                <div style={{ color: "#57606a", marginBottom: 8 }}>{selected.entity_id}</div>
                <b>external_ids</b>
                <ul style={{ margin: "4px 0 10px", paddingLeft: 18 }}>
                  {(selected.external_ids || []).length === 0 && <li style={{ color: "#57606a" }}>none</li>}
                  {(selected.external_ids || []).map((x: any, i: number) => (
                    <li key={i}>
                      <code>
                        {x.system}:{x.id}
                      </code>
                    </li>
                  ))}
                </ul>
                <b>aliases</b>
                <div style={{ color: "#57606a", marginBottom: 8 }}>
                  {(selected.aliases || []).join(", ") || "—"}
                </div>
                {selected.country && (
                  <div>
                    <b>country</b> {selected.country}
                  </div>
                )}
              </>
            )}
            {tab !== "entities" && (
              <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: 11 }}>
                {JSON.stringify(selected, null, 2)}
              </pre>
            )}
          </div>
        )}
      </div>
      {!data && <p>Loading…</p>}
    </div>
  );
}
