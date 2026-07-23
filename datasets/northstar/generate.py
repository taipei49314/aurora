"""Northstar Corpus generator (spec §23).

Deterministic (seeded) synthetic corpus that embeds the acceptance archetypes:

* 3 genuinely-forming latent industries (dispersed cross-source signals)
* 2 mature industries wearing new names (existing-industry variants)
* 2 high-volume hype clusters (loud, hollow, syndicated, spike-then-fade)
* 1 early-stage cluster that fails (counterevidence arrives later)
* 1 single-giant pseudo-cluster (no independent followers)
* reprints/duplicates, contradictory sources, missing dates, aliases

Ground truth is written to ``tests/ground_truth/`` and is NEVER read by the
runtime engine (spec §23, §5.10). This module only produces data; it encodes no
industry answer into the engine.

Scaled down from the full 3000-observation target for a fast, verifiable MVP;
``--scale`` multiplies activity counts to approach the full corpus size.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
GT_DIR = HERE.parent.parent / "tests" / "ground_truth"

# --- archetype definitions -------------------------------------------------

LATENT = {
    "iron_air_storage": {
        "vocab": ["iron-air", "oxygen-electrode", "long-duration", "multi-day", "grid-dispatch",
                  "alkaline-electrolyte", "rust-cycle", "reversible-oxidation", "hundred-hour",
                  "depth-discharge", "dispatchable-firming"],
        "companies": ["FerroGrid Power", "LongHaul Energy", "OxaCell Systems", "IronField Storage",
                      "MegaHour Grid", "TerraDurance"],
        "tech": "reversible iron oxidation",
        "component": "porous iron electrode",
        "supplier": "FerroPore Labs",   # small critical bottleneck supplier
        "material": "food-grade iron powder",
        "application": "grid firming",
        "market": "regional utility",
        "standard": "grid interconnection working group",
    },
    "mycelium_materials": {
        "vocab": ["mycelium", "fungal-composite", "structural-panel", "precision-fermentation",
                  "chitin-matrix", "load-bearing", "biofabricated", "substrate-lattice",
                  "fire-retardant-bio", "carbon-negative-panel"],
        "companies": ["MycoStructural", "FungiForm Materials", "HyphaeBuild", "RootLattice", "SporeWorks"],
        "tech": "solid-state fungal fermentation",
        "component": "chitin binder",
        "supplier": "PureChitin Bio",
        "material": "agricultural substrate",
        "application": "green construction",
        "market": "modular builder",
        "standard": "building materials certification board",
    },
    "neuromorphic_sensing": {
        "vocab": ["neuromorphic", "compute-in-memory", "event-camera", "spiking-network",
                  "analog-inference", "edge-sensor", "memristor-array", "sub-milliwatt",
                  "asynchronous-spikes", "in-sensor-compute"],
        "companies": ["SpikeEdge", "MemSense", "NeuroPixel", "AnalogCortex", "EventSight", "SynapseIC"],
        "tech": "analog compute-in-memory",
        "component": "memristor crossbar",
        "supplier": "CrossbarFab",
        "material": "phase-change film",
        "application": "always-on vision",
        "market": "industrial iot integrator",
        "standard": "edge inference consortium",
    },
}

MATURE = {
    "cloud_synergy_fabric": {  # rebranded data_center_services
        "vocab": ["colocation", "rack", "server", "cooling", "uptime", "bandwidth", "hosting",
                  "datacenter", "provisioning", "redundancy", "sla", "synergy", "cloud-native", "fabric"],
        "companies": ["SynergyCloud Fabric", "NextGen Colo", "HyperRack Systems", "UptimeFabric", "CloudNative Halls"],
        "application": "enterprise hosting", "market": "enterprise tenant",
    },
    "next_gen_mobility": {  # rebranded auto_components
        "vocab": ["chassis", "brake", "powertrain", "assembly", "stamping", "tier-one", "oem",
                  "drivetrain", "axle", "casting", "mobility", "next-gen"],
        "companies": ["MobilityForge", "NextAxle Systems", "DriveCore Solutions", "ChassisWorks Mobility", "BrakeNova"],
        "application": "vehicle assembly", "market": "vehicle oem",
    },
}

HYPE = {
    "metaverse_retail": {
        "vocab": ["metaverse", "virtual-storefront", "avatar-shopping", "immersive-retail",
                  "spatial-commerce", "digital-twin-mall", "nft-checkout", "virtual-fitting"],
        "companies": ["MetaMart", "AvatarAisle", "ImmersaShop", "VirtualBoutique", "SpatialCart"],
    },
    "quantum_blockchain": {
        "vocab": ["quantum-blockchain", "entangled-ledger", "qubit-consensus", "post-quantum-token",
                  "superposition-hash", "quantum-mining"],
        "companies": ["QubitChain", "EntangleLedger", "QuantumMint", "SuperposePay", "QChainWorks"],
    },
}

FAILED = {
    "algae_jet_fuel": {
        "vocab": ["algae-biofuel", "photobioreactor", "lipid-extraction", "strain-engineering",
                  "drop-in-jetfuel", "cultivation-pond", "triacylglycerol"],
        "companies": ["AlgaJet", "GreenLipid Fuels", "PhycoWing", "PondToPlane", "BioKerosene"],
    },
}

SINGLE_GIANT = {
    "ambient_holographics": {
        "vocab": ["ambient-holography", "lightfield-projection", "volumetric-display",
                  "holographic-mesh", "free-space-optics"],
        "company": "Monolith Corp",
        "tech": "free-space lightfield engine",
        "product": "ambient holographic wall",
    },
}


class Builder:
    def __init__(self, seed: int, scale: float):
        self.rng = random.Random(seed)
        self.scale = scale
        self.entities: list[dict] = []
        self.sources: list[dict] = []
        self.observations: list[dict] = []
        self._seen_entities: set[str] = set()
        self._src_i = 0
        self.gt_clusters: dict[str, list[str]] = {}
        self.gt_status: dict[str, str] = {}

    # -- entity/source/obs helpers --
    def ent(self, name, etype, vocab=None, aliases=None):
        if name not in self._seen_entities:
            self._seen_entities.add(name)
            self.entities.append({
                "entity_type": etype, "canonical_name": name,
                "aliases": aliases or [],
                "description": " ".join(self.rng.sample(vocab, min(5, len(vocab)))) if vocab else "",
                "country": self.rng.choice(["US", "DE", "TW", "JP", "KR", "NL"]),
            })
        return name

    def _text(self, vocab, k=4):
        return " ".join(self.rng.sample(vocab, min(k, len(vocab))))

    def obs(self, subject, otype, vocab, mode, *, obj=None, indep=None, publisher=None,
            source_type="NEWS", tier="C", conf=0.7, numeric=None, unit=None, reprints=0,
            missing_date=False, year=None):
        y = year if year is not None else self._pick_year(mode)
        m = self.rng.randint(1, 12)
        d = self.rng.randint(1, 28)
        date = None if missing_date else f"{y:04d}-{m:02d}-{d:02d}"
        excerpt = self._text(vocab)
        pub = publisher or f"{source_type.title()}Wire-{self.rng.randint(1, 40)}"
        ref = f"s{self._src_i}"
        self._src_i += 1
        indep_group = indep if indep is not None else f"grp-{self.rng.randint(1, 10**6)}"
        title = f"{subject}: {excerpt}"
        self.sources.append({
            "ref": ref, "source_type": source_type, "publisher": pub, "title": title,
            "excerpt": excerpt, "published_at": date, "independence_group": indep_group,
            "reliability_tier": tier, "url_or_local_path": f"local://{ref}",
        })
        self.observations.append({
            "source_ref": ref, "observation_type": otype, "subject": subject, "object": obj,
            "observed_at": date, "text_excerpt": excerpt, "confidence": conf,
            "numeric_value": numeric, "unit": unit,
        })
        # reprints: same title/excerpt, same wire (declared independence group) -> not independent
        for r in range(reprints):
            rref = f"s{self._src_i}"
            self._src_i += 1
            self.sources.append({
                "ref": rref, "source_type": "NEWS", "publisher": f"Outlet-{self.rng.randint(1, 200)}",
                "title": title, "excerpt": excerpt, "published_at": date,
                "independence_group": indep_group, "reliability_tier": "D",
                "url_or_local_path": f"local://{rref}",
            })
            self.observations.append({
                "source_ref": rref, "observation_type": otype, "subject": subject, "object": obj,
                "observed_at": date, "text_excerpt": excerpt, "confidence": conf * 0.9,
            })

    def _pick_year(self, mode):
        r = self.rng
        if mode == "rising":
            return r.choices([2019, 2020, 2021, 2022, 2023, 2024, 2025],
                             weights=[1, 2, 3, 4, 6, 8, 9])[0]
        if mode == "spike_fade":
            return r.choices([2020, 2021, 2022, 2023, 2024, 2025],
                             weights=[3, 9, 8, 2, 1, 1])[0]
        if mode == "fail_pos":
            return r.choices([2019, 2020, 2021], weights=[3, 5, 6])[0]
        if mode == "fail_neg":
            return r.choices([2022, 2023, 2024, 2025], weights=[4, 6, 6, 5])[0]
        return r.choices([2019, 2020, 2021, 2022, 2023, 2024, 2025], weights=[1] * 7)[0]

    def n(self, base):
        return max(1, int(round(base * self.scale)))

    # -- archetype emitters --
    def emit_latent(self, key, spec):
        v = spec["vocab"]
        members = []
        tech = self.ent(spec["tech"], "TECHNOLOGY", v)
        comp = self.ent(spec["component"], "COMPONENT", v)
        mat = self.ent(spec["material"], "MATERIAL", v)
        app = self.ent(spec["application"], "APPLICATION", v)
        market = self.ent(spec["market"], "MARKET", v)
        std = self.ent(spec["standard"], "STANDARD_BODY", v)
        supplier = self.ent(spec["supplier"], "COMPANY", v)
        members += [tech, comp, mat, app, supplier]
        for co in spec["companies"]:
            self.ent(co, "COMPANY", v)
            members.append(co)
            # real investment, accelerating, independent sources, cross source-type
            for _ in range(self.n(3)):
                self.obs(co, "PATENT_ACTIVITY", v, "rising", source_type="PATENT", tier="A", conf=0.85)
            for _ in range(self.n(3)):
                self.obs(co, "HIRING_ACTIVITY", v, "rising", source_type="JOB_POSTING", tier="B", conf=0.8)
            for _ in range(self.n(2)):
                self.obs(co, "CAPEX_ACTIVITY", v, "rising", source_type="COMPANY_FILING", tier="A",
                         conf=0.85, numeric=self.rng.randint(20, 200), unit="MUSD")
            self.obs(co, "SUPPLIER_RELATIONSHIP", v, "rising", obj=supplier, source_type="COMPANY_FILING", tier="A", conf=0.8)
            self.obs(co, "TECHNICAL_DEPENDENCY", v, "rising", obj=comp, source_type="PAPER", tier="B", conf=0.75)
            self.obs(co, "CUSTOMER_RELATIONSHIP", v, "rising", obj=market, source_type="COMPANY_FILING", tier="A", conf=0.8)
            self.obs(co, "ADOPTION_SIGNAL", v, "rising", obj=app, source_type="NEWS", tier="C", conf=0.6, reprints=1)
        # supplier is small: few own signals + is the shared dependency (bottleneck)
        self.obs(supplier, "PATENT_ACTIVITY", v, "rising", source_type="PATENT", tier="A", conf=0.85)
        self.obs(supplier, "HIRING_ACTIVITY", v, "rising", source_type="JOB_POSTING", tier="B", conf=0.8)
        self.obs(supplier, "CAPACITY_EXPANSION", v, "rising", source_type="COMPANY_FILING", tier="A",
                 conf=0.8, numeric=self.rng.randint(1, 3), unit="line")
        self.obs(supplier, "LEAD_TIME_PRESSURE", v, "rising", source_type="NEWS", tier="C", conf=0.7, numeric=18, unit="months")
        # standards + demand-pull
        self.obs(spec["companies"][0], "STANDARD_ACTIVITY", v, "rising", obj=std, source_type="STANDARD", tier="A", conf=0.8)
        self.obs(spec["companies"][1], "DEMAND_SIGNAL", v, "rising", obj=market, source_type="NEWS", tier="C", conf=0.65)
        self.gt_clusters[key] = members
        self.gt_status[key] = "EMERGING_OR_CANDIDATE"

    def emit_mature(self, key, spec):
        v = spec["vocab"]
        app = self.ent(spec["application"], "APPLICATION", v)
        market = self.ent(spec["market"], "MARKET", v)
        members = [app]
        for co in spec["companies"]:
            self.ent(co, "COMPANY", v)
            members.append(co)
            for _ in range(self.n(3)):
                self.obs(co, "CAPEX_ACTIVITY", v, "flat", source_type="COMPANY_FILING", tier="A", conf=0.8,
                         numeric=self.rng.randint(50, 300), unit="MUSD")
            for _ in range(self.n(3)):
                self.obs(co, "HIRING_ACTIVITY", v, "flat", source_type="JOB_POSTING", tier="B", conf=0.75)
            self.obs(co, "PRODUCT_LAUNCH", v, "flat", source_type="NEWS", tier="C", conf=0.6)
            self.obs(co, "CUSTOMER_RELATIONSHIP", v, "flat", obj=market, source_type="COMPANY_FILING", tier="A", conf=0.8)
            self.obs(co, "SUPPLIER_RELATIONSHIP", v, "flat", obj=spec["companies"][0], source_type="COMPANY_FILING", tier="B", conf=0.7)
        self.gt_clusters[key] = members
        self.gt_status[key] = "EXISTING_INDUSTRY_VARIANT"

    def emit_hype(self, key, spec):
        v = spec["vocab"]
        members = []
        for co in spec["companies"]:
            self.ent(co, "COMPANY", v)
            members.append(co)
            # Each announcement is its own release (independent group) but is
            # massively reprinted (reprints share the group). So the cluster has
            # enough independent releases to pass the sparsity gate, yet a very
            # low independence RATIO -> the hype filter, not the insufficiency
            # gate, is what catches it.
            for _ in range(self.n(6)):
                self.obs(co, "PRODUCT_LAUNCH", v, "spike_fade", source_type="NEWS", tier="D",
                         conf=0.5, reprints=4)
            for _ in range(self.n(3)):
                self.obs(co, "STRATEGIC_INVESTMENT", v, "spike_fade", source_type="NEWS", tier="D",
                         conf=0.5, reprints=2)
        self.gt_clusters[key] = members
        self.gt_status[key] = "HYPE_CLUSTER"

    def emit_failed(self, key, spec):
        v = spec["vocab"]
        members = []
        for co in spec["companies"]:
            self.ent(co, "COMPANY", v)
            members.append(co)
            for _ in range(self.n(2)):
                self.obs(co, "PATENT_ACTIVITY", v, "fail_pos", source_type="PATENT", tier="A", conf=0.8)
                self.obs(co, "CAPEX_ACTIVITY", v, "fail_pos", source_type="COMPANY_FILING", tier="A",
                         conf=0.8, numeric=self.rng.randint(10, 80), unit="MUSD")
                self.obs(co, "HIRING_ACTIVITY", v, "fail_pos", source_type="JOB_POSTING", tier="B", conf=0.75)
            # counterevidence dominates later
            for _ in range(self.n(3)):
                self.obs(co, "CANCELLATION_SIGNAL", v, "fail_neg", source_type="NEWS", tier="B", conf=0.8)
            for _ in range(self.n(2)):
                self.obs(co, "SHUTDOWN_SIGNAL", v, "fail_neg", source_type="COMPANY_FILING", tier="A", conf=0.85)
                self.obs(co, "PRICE_PRESSURE", v, "fail_neg", source_type="NEWS", tier="C", conf=0.7)
        self.gt_clusters[key] = members
        self.gt_status[key] = "DORMANT_OR_REJECTED"

    def emit_single_giant(self, key, spec):
        v = spec["vocab"]
        co = spec["company"]
        wire = "monolith-pr"
        self.ent(co, "COMPANY", v, aliases=["Monolith Corporation", "MonolithCorp"])
        tech = self.ent(spec["tech"], "TECHNOLOGY", v)
        prod = self.ent(spec["product"], "PRODUCT", v)
        for _ in range(self.n(8)):
            self.obs(co, "PATENT_ACTIVITY", v, "rising", obj=tech, source_type="PATENT", tier="A", conf=0.85, indep=wire)
        for _ in range(self.n(5)):
            self.obs(co, "HIRING_ACTIVITY", v, "rising", source_type="JOB_POSTING", tier="B", conf=0.8, indep=wire)
        for _ in range(self.n(4)):
            self.obs(co, "PRODUCT_LAUNCH", v, "rising", obj=prod, source_type="NEWS", tier="C", conf=0.6, indep=wire, reprints=3)
        self.gt_clusters[key] = [co, tech, prod]
        self.gt_status[key] = "INSUFFICIENT_EVIDENCE"

    def emit_background(self, n_companies=64, obs_per=36):
        """Realistic background noise: many unrelated companies with scattered
        activity and their own idiosyncratic vocab. These must NOT coalesce into
        clusters — they pad entity/observation counts toward the full-corpus
        target and stress the engine's ability to ignore noise."""
        generic = ["logistics", "packaging", "retail", "consulting", "catering",
                   "insurance", "printing", "textile", "furniture", "plumbing",
                   "signage", "landscaping", "bakery", "hardware", "apparel"]
        otypes = ["PRODUCT_LAUNCH", "HIRING_ACTIVITY", "CAPEX_ACTIVITY",
                  "CUSTOMER_RELATIONSHIP", "PATENT_ACTIVITY"]
        stypes = ["NEWS", "JOB_POSTING", "COMPANY_FILING", "PATENT"]
        for i in range(self.n(n_companies)):
            # each background company has its own unique two-word vocab so it is
            # dissimilar from every other entity (won't cluster).
            w = [f"bg{i}-{generic[i % len(generic)]}", f"bg{i}-{generic[(i * 7) % len(generic)]}",
                 f"bg{i}-widget", f"bg{i}-service"]
            co = f"Background Co {i:03d}"
            self.ent(co, "COMPANY", w)
            tech = self.ent(f"bg{i} process", "TECHNOLOGY", w)
            for _ in range(self.n(obs_per)):
                ot = self.rng.choice(otypes)
                st = self.rng.choice(stypes)
                obj = tech if ot in ("PATENT_ACTIVITY",) else None
                self.obs(co, ot, w, "flat", obj=obj, source_type=st, tier=self.rng.choice(["B", "C", "D"]))

    def emit_noise(self):
        # a few undated / low-quality observations and an exact-duplicate press release
        v = ["general", "market", "update", "report"]
        self.ent("MiscHoldings", "COMPANY", v)
        self.obs("MiscHoldings", "PRODUCT_LAUNCH", v, "flat", source_type="NEWS", tier="D",
                 conf=0.3, missing_date=True)
        # exact duplicate: emit identical source twice (same publisher+title+excerpt)
        for _ in range(2):
            ref = f"s{self._src_i}"; self._src_i += 1
            self.sources.append({"ref": ref, "source_type": "NEWS", "publisher": "DupPress",
                                 "title": "MiscHoldings: general market update report",
                                 "excerpt": "general market update report", "published_at": "2023-05-05",
                                 "independence_group": "", "reliability_tier": "D",
                                 "url_or_local_path": f"local://{ref}"})
            self.observations.append({"source_ref": ref, "observation_type": "PRODUCT_LAUNCH",
                                      "subject": "MiscHoldings", "object": None, "observed_at": "2023-05-05",
                                      "text_excerpt": "general market update report", "confidence": 0.3})

    def build(self):
        for k, s in LATENT.items():
            self.emit_latent(k, s)
        for k, s in MATURE.items():
            self.emit_mature(k, s)
        for k, s in HYPE.items():
            self.emit_hype(k, s)
        for k, s in FAILED.items():
            self.emit_failed(k, s)
        for k, s in SINGLE_GIANT.items():
            self.emit_single_giant(k, s)
        self.emit_background()
        self.emit_noise()
        return {"entities": self.entities, "sources": self.sources, "observations": self.observations}


def generate(seed: int = 20240115, scale: float = 1.0):
    b = Builder(seed, scale)
    package = b.build()
    return package, {"clusters": b.gt_clusters, "expected_status": b.gt_status}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20240115)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--out", default=str(HERE / "package.json"))
    args = ap.parse_args()
    package, gt = generate(args.seed, args.scale)
    Path(args.out).write_text(json.dumps(package, indent=2, ensure_ascii=False), encoding="utf-8")
    GT_DIR.mkdir(parents=True, exist_ok=True)
    (GT_DIR / "labels.json").write_text(json.dumps(gt, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"entities={len(package['entities'])} sources={len(package['sources'])} "
          f"observations={len(package['observations'])}")
    print(f"ground truth -> {GT_DIR / 'labels.json'}")


if __name__ == "__main__":
    main()
