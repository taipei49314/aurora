import { useQuery } from "@tanstack/react-query";
import { NavLink, Route, Routes } from "react-router-dom";
import { getHealth } from "./api";
import { Dashboard } from "./pages/Dashboard";
import { DataExplorer } from "./pages/DataExplorer";
import { HypothesisExplorer } from "./pages/HypothesisExplorer";
import { DiscoveryMap } from "./pages/DiscoveryMap";
import { Timeline } from "./pages/Timeline";
import { BottleneckLab } from "./pages/BottleneckLab";
import { BacktestLab } from "./pages/BacktestLab";
import { RunComparison } from "./pages/RunComparison";

const nav = [
  ["/", "Dashboard"],
  ["/hypotheses", "Hypothesis Explorer"],
  ["/map", "Discovery Map"],
  ["/timeline", "Timeline"],
  ["/bottlenecks", "Bottleneck Lab"],
  ["/backtest", "Backtest Lab"],
  ["/data", "Data Explorer"],
  ["/compare", "Run Comparison"],
] as const;

export function App() {
  const health = useQuery({ queryKey: ["health"], queryFn: getHealth, staleTime: 60_000 });
  const engine = health.data?.engine ?? "…";

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", color: "#1f2328" }}>
      <header
        style={{
          borderBottom: "1px solid #d0d7de",
          padding: "12px 24px",
          display: "flex",
          gap: 20,
          alignItems: "baseline",
          flexWrap: "wrap",
        }}
      >
        <strong style={{ fontSize: 18 }}>AURORA</strong>
        <span style={{ color: "#57606a", fontSize: 13 }}>Unknown Industry Discovery</span>
        <span
          title="ENGINE_VERSION from /api/health"
          style={{
            fontSize: 11,
            color: "#0969da",
            background: "#ddf4ff",
            padding: "2px 8px",
            borderRadius: 12,
            fontWeight: 600,
          }}
        >
          engine {engine}
        </span>
        <nav style={{ display: "flex", gap: 14, marginLeft: "auto", flexWrap: "wrap" }}>
          {nav.map(([to, label]) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              style={({ isActive }) => ({
                textDecoration: "none",
                fontSize: 13,
                color: isActive ? "#0969da" : "#57606a",
                fontWeight: isActive ? 600 : 400,
              })}
            >
              {label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main style={{ maxWidth: 1040, margin: "0 auto", padding: 24 }}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/hypotheses" element={<HypothesisExplorer />} />
          <Route path="/map" element={<DiscoveryMap />} />
          <Route path="/timeline" element={<Timeline />} />
          <Route path="/bottlenecks" element={<BottleneckLab />} />
          <Route path="/backtest" element={<BacktestLab />} />
          <Route path="/data" element={<DataExplorer />} />
          <Route path="/compare" element={<RunComparison />} />
        </Routes>
      </main>
    </div>
  );
}
