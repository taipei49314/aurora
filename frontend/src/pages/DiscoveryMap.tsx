import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useCurrentRun } from "../useRun";
import { getGraph } from "../api";

const ROLE_COLORS: Record<string, string> = {
  RAW_INPUT: "#8b5cf6", CORE_COMPONENT: "#0969da", ENABLING_EQUIPMENT: "#0891b2",
  PROCESS: "#16a34a", INTEGRATION: "#ca8a04", INFRASTRUCTURE: "#dc2626",
  APPLICATION: "#db2777", END_CUSTOMER: "#57606a", STANDARD_OR_REGULATION: "#6b7280",
};

export function DiscoveryMap() {
  const { hyps } = useCurrentRun();
  const [sel, setSel] = useState<string | null>(null);
  const id = sel ?? hyps.data?.[0]?.hypothesis_id;
  const graph = useQuery({ queryKey: ["graph", id], queryFn: () => getGraph(id!), enabled: !!id });

  if (!hyps.data) return <p>Loading…</p>;
  const nodes = graph.data?.nodes ?? [];
  const edges = graph.data?.edges ?? [];
  const R = 200, CX = 260, CY = 240;
  const pos: Record<string, { x: number; y: number }> = {};
  nodes.forEach((n, i) => {
    const a = (2 * Math.PI * i) / Math.max(1, nodes.length);
    pos[n.id] = { x: CX + R * Math.cos(a), y: CY + R * Math.sin(a) };
  });

  return (
    <div>
      <h2>Discovery Map</h2>
      <select value={id} onChange={(e) => setSel(e.target.value)} style={{ marginBottom: 12 }}>
        {hyps.data.map((h) => <option key={h.hypothesis_id} value={h.hypothesis_id}>{h.generated_name}</option>)}
      </select>
      <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
        <svg width={520} height={480} style={{ border: "1px solid #d0d7de", borderRadius: 8 }}>
          {edges.map((e: any, i: number) => {
            const a = pos[e.from], b = pos[e.to];
            if (!a || !b) return null;
            return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#c0c0c0"
              strokeDasharray={e.confidence_flag === "CONFIRMED" ? "0" : "4"} />;
          })}
          {nodes.map((n) => {
            const p = pos[n.id];
            const isBottleneck = n.bottleneck_score >= 40;
            return (
              <g key={n.id}>
                <circle cx={p.x} cy={p.y} r={isBottleneck ? 12 : 8}
                  fill={ROLE_COLORS[n.role] ?? "#57606a"} stroke={isBottleneck ? "#cf222e" : "white"} strokeWidth={isBottleneck ? 3 : 1} />
                <text x={p.x} y={p.y - 14} fontSize={9} textAnchor="middle" fill="#1f2328">{n.name.slice(0, 18)}</text>
              </g>
            );
          })}
        </svg>
        <div style={{ fontSize: 12 }}>
          <b>Legend</b>
          {Object.entries(ROLE_COLORS).map(([role, c]) => (
            <div key={role} style={{ display: "flex", alignItems: "center", gap: 6, margin: "3px 0" }}>
              <span style={{ width: 10, height: 10, background: c, borderRadius: "50%" }} /> {role}
            </div>
          ))}
          <div style={{ marginTop: 8, color: "#cf222e" }}>◯ red ring = bottleneck node</div>
          <div style={{ marginTop: 4, color: "#57606a" }}>dashed edge = inferred (low confidence)</div>
        </div>
      </div>
    </div>
  );
}
