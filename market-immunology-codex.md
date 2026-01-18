# Market Immunology Lab Codex

## Invariant Core (Non-Negotiable System Law)

- **Purpose:** Detect pre-price liquidity infections and regime shifts; never produce trades or price predictions.
- **Focus:** Pre-price substrate (mempool, LP mechanics, wallet-graph dynamics, bridge latency, stablecoin velocity).
- **Model:** Markets as living systems; liquidity = blood, volatility = fever, capital rotation = metabolism.
- **Output:** Capital Health Index (CHI), incubation windows, regime-shift warnings, and traceable diagnostics.
- **Architecture:** Immune-cell micro-agent swarm + adversarial infection simulator + antibody rule evolution.
- **Operational Doctrine:** LLMs are semantic compressors and pattern translators, not predictors.

## System Architecture (Five Planes)

1. **Interstitial Liquidity Ingestion (Pre-Price Signals)**
   - Mempool streams (pending tx clustering, gas escalation, replace/cancel patterns).
   - LP mechanics (mint/burn velocity, tick-range shifts, fee discontinuities).
   - Wallet-graph dynamics (centrality churn, entropy drift, clustering spikes).
   - Bridge latency + stablecoin velocity divergence.

2. **Antigenization (Raw Signals → Antigen Objects)**
   - Normalize anomalies into a standard “antigen” schema:
     - Numeric vector (rates, curvatures, deltas).
     - Semantic epitopes (LLM-labeled: e.g., `LP_HEMORRHAGE`, `BRIDGE_HYPOXIA`).
     - Provenance (tx hashes, addresses, logs).

3. **Immune-Cell Micro-Agent Swarm (Role-Separated)**
   - **Macrophage:** nominates anomalies from raw feeds.
   - **Dendritic:** converts anomalies → antigen + epitope candidates.
   - **T-Cell:** classifies benign/opportunistic/pathogenic + severity + window.
   - **B-Cell:** proposes antibody rules (compiled detectors).
   - **Memory Cell:** persists rare lethal patterns + counterfactuals.

4. **Adversarial Infection Simulator (Evolution Pressure)**
   - Inject synthetic infections (rug cascades, flash crashes, whale exits, bridge hypoxia).
   - Reward earliest detection, correct epitope classification, and low false positives.

5. **Capital Metabolism Model (Outputs Only)**
   - **CHI:** perfusion, inflammation, coagulation risk, neural stress, hypoxia.
   - **Alerts:** incubation windows and regime-shift warnings with full provenance.

## Operational Outputs (Never Trades)

- `INCUBATION_ALERT(chain, pool, severity, window_estimate, epitope_set)`
- `CAPITAL_HEALTH_INDEX(components + overall score)`
- `REGIME_SHIFT_WARNING(classification + rationale)`

## Antigen Schema (Canonical)

```json
{
  "antigen_id": "uuid",
  "ts": "2026-01-18T00:00:00Z",
  "chain": "ethereum",
  "locus": {
    "pool": "0xPOOL",
    "protocol": "uniswap_v3",
    "token_set": ["0xTOKEN0", "0xTOKEN1"]
  },
  "vector": {
    "mempool_cluster_density": 0.0,
    "gas_escalation_curvature": 0.0,
    "replacement_rate": 0.0,
    "lp_remove_velocity": 0.0,
    "tick_range_shift_rate": 0.0,
    "collect_discontinuity": 0.0,
    "centrality_churn": 0.0,
    "graph_entropy_drift": 0.0,
    "bridge_latency_z": 0.0,
    "stablecoin_velocity_divergence": 0.0
  },
  "epitopes": ["LP_HEMORRHAGE", "WHALE_EXIT_REHEARSAL"],
  "tcell": {
    "class": "pathogenic",
    "severity": 0.0,
    "incubation_window_minutes": [0, 0],
    "confidence": 0.0
  },
  "provenance": {
    "tx_hashes": ["0x..."],
    "addresses": ["0x..."],
    "logs": ["topic0:..."]
  }
}
```

## Antibody Rule Format (Declarative → Compiled)

```yaml
id: AB_LP_HEMORRHAGE_V1
when:
  all:
    - metric: lp_remove_velocity
      op: ">"
      value: "P99_30D"
    - metric: tick_range_shift_rate
      op: ">"
      value: "P95_30D"
    - metric: collect_discontinuity
      op: ">"
      value: "P95_30D"
then:
  epitope: LP_HEMORRHAGE
  severity: "scale_z(lp_remove_velocity)*0.5 + scale_z(tick_range_shift_rate)*0.3 + scale_z(collect_discontinuity)*0.2"
  incubation_window_minutes: [20, 240]
  explain:
    - "Liquidity removed at extreme rate"
    - "Positions relocating away from active tick"
    - "Fee collection discontinuity suggests strategic exit"
```

## Evaluation Metrics (Early-Warning Advantage)

- **Time advantage:** minutes between first alert and first symptom proxy (slippage/spread/LP depth rupture).
- **Signal quality:** precision/recall per epitope, false-positive rate by regime.
- **Stability:** alert volatility index; concept drift sensitivity.
- **Provenance completeness:** share of alerts with sufficient evidence for audit.
- **Generalization:** cross-chain antibody performance.

## Build Sequence (Minimal Viable Asymmetry)

1. **Wallet Graph Entropy Sentinel** (no price data).
2. **LP Hemorrhage Detector** (concentrated liquidity exits).
3. **Mempool Incubation Detector** (replace/cancel + cluster density).

## Integration Priorities (Autonomous AI Ecosystem)

- Create an event bus that connects all apps (indexer, agents, simulator, dashboard).
- Enforce a closed-loop evolution gate: antibodies must pass generalization, alarm-fatigue, and provenance checks.
- Publish a weekly immune repertoire diff (what evolved, what died, new epitopes).
