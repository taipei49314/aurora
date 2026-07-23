import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useCurrentRun } from "../useRun";
import { getTimeline } from "../api";

export function Timeline() {
  const { hyps } = useCurrentRun();
  const [sel, setSel] = useState<string | null>(null);
  const id = sel ?? hyps.data?.[0]?.hypothesis_id;
  const tl = useQuery({ queryKey: ["timeline", id], queryFn: () => getTimeline(id!), enabled: !!id });

  if (!hyps.data) return <p>Loading…</p>;
  const rows = tl.data?.timeline ?? [];
  const max = Math.max(1, ...rows.map((r: any) => r.total));

  return (
    <div>
      <h2>Timeline — signal acceleration</h2>
      <select value={id} onChange={(e) => setSel(e.target.value)} style={{ marginBottom: 16 }}>
        {hyps.data.map((h) => <option key={h.hypothesis_id} value={h.hypothesis_id}>{h.generated_name}</option>)}
      </select>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 12, height: 240, borderBottom: "1px solid #d0d7de", paddingBottom: 4 }}>
        {rows.map((r: any) => (
          <div key={r.year} style={{ textAlign: "center" }}>
            <div title={JSON.stringify(r.by_type)} style={{ width: 44, height: `${(r.total / max) * 200}px`,
              background: "#0969da", borderRadius: "4px 4px 0 0" }} />
            <div style={{ fontSize: 12, marginTop: 4 }}>{r.year}</div>
            <div style={{ fontSize: 11, color: "#57606a" }}>{r.total}</div>
          </div>
        ))}
      </div>
      <p style={{ fontSize: 12, color: "#57606a", marginTop: 10 }}>
        Bar height = observation count per year (hover for the observation-type breakdown). A genuine forming
        industry shows rising real-investment activity; a hype cluster spikes then fades.
      </p>
    </div>
  );
}
