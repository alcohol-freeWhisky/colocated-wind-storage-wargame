# Assumptions, Calibration Steps, and Sources — Workshop 1

This file is the complete record of every parameter in `config/base.yaml`, how it was obtained, and whether it is
**observed** (taken directly from public data), **calibrated** (set from public data or literature with a documented rule),
or **designed** (a wargame variable chosen by us, with its experimental levels). Numbers are as of the dataset built on
2026-10-21 from ERCOT operating days 2025-03-01 to 2025-04-30. Section numbers refer to `docs/proposal.tex`.

## 1. Data pipeline (observed inputs)

| Step | What is done | Source / access | Notes |
|---|---|---|---|
| 1.1 Prices | Hourly DAM and RTM settlement point prices at hub `HB_WEST`, calendar year 2025. RTM 15-min SPPs are averaged to hourly. | ERCOT Historical DAM SPP (NP4-180-ER) and Historical RTM SPP (NP6-785-ER), via `gridstatus` [R1] | Observed. West hub chosen because all pool resources are in the ERCOT West weather zone. |
| 1.2 Available wind `W_it` | 5-min SCED `HSL` of each wind resource averaged to hourly. `HSL` is the telemetered *available* power, so curtailment is a decision variable in the model, not baked into the data. | ERCOT 60-Day SCED Disclosure (NP3-965-ER), table `sced_gen_resource`, `Resource Type == WIND` [R2] | Observed. Realised output (`Telemetered Net Output`) and `Base Point` are kept for diagnostics (observed curtailment at Anchor over the window is 0.1 % of available energy). |
| 1.3 Own forecast `Ŵ_it` | Hourly `High Sustained Limit` from the Current Operating Plan snapshot taken at the start of the Adjustment Period (day-ahead for most hours). | ERCOT 60-Day COP Adjustment Period Snapshot [R2] | Observed. This is the QSE's own availability forecast, i.e. exactly the agent's private forecast in §2. |
| 1.4 Baseline `b_it` | DAM energy award (`Awarded Quantity`) when positive; otherwise `Ŵ_it`. Only 27 of 385 ERCOT wind resources had DAM awards on 2025-04-15, none at Anchor, so in practice `b = Ŵ`. | ERCOT 60-Day DAM Disclosure (NP3-966-ER), `dam_gen_resource` [R2] | Observed + documented rule. |
| 1.5 Nameplate `N_i` | 99.5th percentile of hourly HSL over the window (robust to telemetry spikes); maximum kept as `hsl_max`. | derived from 1.2 | Calibrated rule. Cross-checked against EIA-860 2023 (Horse Hollow: 735.5 MW in EIA vs 848 MW of HSL across 5 ERCOT resources; ERCOT splits units differently from EIA generator IDs). |
| 1.6 Forecast-error samples | (a) System-wide and regional STWPF/WGRPP forecasts vs realised available HSL by horizon 1–168 h, normalised by a capacity proxy (max observed HSL per region in the snapshot window). (b) Resource-level COP HSL vs realised SCED HSL normalised by nameplate. | ERCOT Wind Power Production Hourly Averaged Actual and Forecasted Values (NP4-732-CD) and by Geographical Region (NP4-742-CD), rolling 8-day MIS window snapshotted 2026-10-13 … 10-20 [R3]; (b) from 1.2–1.3 | Observed. The system-level sample is from October 2026 because ERCOT does not archive these reports publicly; the resource-level sample is from the March–April 2025 window. Comparing STWPF to realised *HSL* rather than realised *output* avoids contaminating the error with curtailment (see `docs/DEVIATIONS.md`). |
| 1.7 Asset metadata | TX wind nameplate for Horse Hollow; distribution of TX battery duration (90 units, median 1.0 h); storage/wind power ratio of TX co-located wind+storage plants (4 plants in 2023: 0.04–0.24, median 0.08). | EIA-860 2023, sheets 3_2 (wind), 3_4 (energy storage), 3_1 (generators) [R4] | Observed. |
| 1.8 Observed co-located storage | ERCOT registers `ANCHOR_BESS1` (35.2 MW, 54 MWh) and `ANCHOR_BESS2` (36.3 MW, 59 MWh) at the Anchor Wind site and `VORTEX_BESS1` (121.8 MW, 184 MWh) at Vortex; `HSL` = power, COP `Maximum SOC` = usable energy. Horse Hollow has no storage resource. | ERCOT 60-Day COP snapshot, 2025-04-15 [R2]; Enel press material for the Azure Sky wind+storage plant confirms Enel operates wind+storage hybrids in Texas [R5] | Observed. |

Resources: one operating day is one episode (24 hourly steps). Every pool resource has 100 % coverage over the window (1,463 hours; 2025-03-09 has 23 hours because of the DST transition and is excluded from the regime runs).

## 2. Agents and site selection

| Item | Value | Status | Basis |
|---|---|---|---|
| Primary site | Anchor Wind, 5 ERCOT wind resources `ANCHOR_WIND1..5` (16, 99, 89, 39, 19 MW; 262 MW total), DME YENELT, QSE QENE11 | Observed | The only multi-unit wind plant in the pool that also has *observed* co-located storage sharing the same POI (1.8). Mean pairwise correlation of hourly availability among its units is 0.94. |
| Alternative sites | Vortex (`VORTEX_WIND1..4`, 337 MW, observed 121.8 MW / 184 MWh BESS); Horse Hollow (`HHGT_*`, 848 MW, no storage, units registered under three different QSEs) | Observed | `config/scenarios/vortex.yaml`, `config/scenarios/horse_hollow.yaml`. |
| Correlation pool | 37 wind resources from 8 multi-unit plants in the West zone (Horse Hollow, Capricorn Ridge, Anchor, Vera Wind, Wild Horse Mesa, Vortex, Lacy Creek, Canyon Wind) | Observed | Pairwise Pearson correlations of hourly available power over the 61-day window range from −0.06 to 0.98 (median 0.62), so low/medium/high-correlation agent sets can be formed from real series without any synthetic manipulation (§4, item 9 below). |

## 3. Battery parameters (§3)

| Parameter | Value | Status | Basis |
|---|---|---|---|
| Power ratio `p_ratio = P_i / N_i` | 0.29 | Calibrated | Anchor: 71.5 MW BESS / 245 MW wind HSL on 2025-04-15 (1.8). Context: Vortex 0.37; LBNL 2025 operating US wind+storage fleet weighted-average storage:generator ratio 18 % (20 plants, 3,177 MW wind, 569 MW storage) [R6]; EIA-860 2023 TX co-located wind+storage median 0.08 (1.7). |
| Duration `E_i / P_i` | 1.5 h | Calibrated | Anchor 113 MWh / 71.5 MW = 1.58 h; Vortex 1.51 h; LBNL 2025 wind+storage fleet average 1.2 h ("typically ~1 hr") [R6]; EIA-860 2023 TX battery median 1.0 h (1.7). |
| Round-trip efficiency | 85 % (η_c = η_d = 0.922) | Calibrated (literature) | NREL ATB utility-scale battery storage adopts 85 % as the representative round-trip efficiency, following Cole and Frazier (2019) / Cole et al. (2025) [R7]. |
| Degradation cost `C_deg` | 10 $/MWh discharged | Calibrated (literature) | Marginal degradation cost of lithium-ion storage in dispatch studies ranges from ≈7–13 $/MWh-throughput (optimal marginal cost over the first 15 years) to ≈17 $/MWh levelised at 200 $/kWh pack cost [R8]; a full-cycle amortisation at 2,000 cycles gives ≈100 $/MWh as an upper bound [R9]. The model charges this cost on discharge `d` only. |
| Initial / terminal SoC | 50 % of `E_i`; terminal SoC ≥ initial | Designed | Standard daily-cycle convention; prevents end-of-horizon dumping. Alternative `free` is implemented. |
| Grid charging | Allowed (`q_it` may be negative) | Designed | ERCOT ESRs may charge from the grid; relevant because 20 % of RT hours in the window have negative prices at HB_WEST. |
| Tie-break cost | 1e-3 $/MWh on c + d + r | Numerical | Removes LP degeneracy (simultaneous charge and discharge); changes profits by < 0.01 %. |

## 4. Shared POI and system constraints (§3): designed variables with empirical anchors

| Parameter | Value | Status | Basis |
|---|---|---|---|
| POI limit `K = kappa_K · Σ N_i` | kappa_K = 0.6 (base, designed stress level); 0.9 = empirically anchored value | Designed, anchored | LBNL 2025 [R6]: in CAISO's queue, the median combined wind+storage capacity is 142 % of the POI limit and wind capacity alone equals or exceeds the POI limit in 73 % of wind+storage plants. With a 0.29 storage ratio this implies K ≈ 0.9 × wind nameplate [R10]. At 0.9 the Anchor POI binds in only 18 % of hours, so the base design uses 0.6, where it binds in 49 % of hours. |
| Minimum delivery `D_t = delta_D · Σ_i b_it` | delta_D = 0.5 | Designed | Represents a market or contractual delivery commitment (§3). There is no ERCOT rule that imposes a minimum delivery on wind; ERCOT exempts intermittent renewable resources from the Base Point Deviation Charge in Protocols §6.6.5 [R11]. Kept as a stylized commitment and held fixed in the design matrix. |
| Under-delivery penalty `lambda_minus` | 250 $/MWh | Designed, anchored | The economic exposure of an ERCOT resource that under-delivers against its day-ahead position is the RT price (two-settlement). 250 $/MWh lies between the 99th percentile (150 $/MWh) and the maximum (1,541 $/MWh) of HB_WEST RT prices in the window, and far below the ERCOT system-wide offer cap of 5,000 $/MWh and the Brattle survey VOLL of 35,685 $/MWh [R12]. |
| Overflow penalty `lambda_plus` | 100 $/MWh | Designed | Applies only in the strategic layer (what agents *attempt*); physically the plant controller curtails pro rata above K (`solvers/realize.py`), so realised exports never exceed K. The value represents the controller's/QSE's internal enforcement price. |
| Penalty allocation | `INJ` or `EQ` | Designed | INJ uses causal positive-injection overflow shares and own-deficit shortfall charges. EQ uses equal shares of system overflow and shortfall penalties. This is factor F3. |
| Settlement price | `pi_RT` | Designed | Agents are price takers at RT; the DA price is used only as the agents' price forecast. |

## 5. Part I design matrix (§4)

| Factor | Levels | Status | Implementation |
|---|---|---|---|
| F1 control | `C`, `D` | Designed | Central planner or independent decision makers. |
| F2 foresight | `P`, `F` | Designed | True remaining-horizon wind/RT price or current truth followed by COP wind/DA price. |
| F3 penalty allocation | `INJ`, `EQ` | Designed | Causal injection/own-deficit charges or equal system-penalty shares. |
| F4 market information | `FULL`, `PRICE`, `NONE` | Designed | Other agents' plans, a coordinator congestion price, or neither. |

The canonical 14 cells are `C_P`, `C_F`, and `D_{P|F}_{INJ|EQ}_{FULL|PRICE|NONE}`. All are hourly receding-horizon policies with the same realization layer and terminal SoC rule. Effects are matched daily contrasts on realized J. See `docs/DESIGN.md` section 4 for the complete contract.

## 6. Design-matrix solver parameters

| Parameter | Value | Status | Basis |
|---|---:|---|---|
| FULL maximum best-response sweeps | 200 | Designed | Upper limit for each hourly game. |
| FULL residual tolerance | `1e-5 × ΣN` | Designed | Undamped best-response residual. |
| FULL maximum unilateral gain | $1 | Designed | Required together with the residual test for convergence. |
| PRICE proximal coefficient `tau` | 2.0 | Designed | Grid-selected numerical regularizer; excluded from reported economic costs. |
| PRICE coordination step `rho` | 0.2 $/MWh per MW, constant | Designed | Grid-selected predictor-corrector dual step. |
| PRICE maximum iterations | 60 | Designed | Upper limit for each hourly coordinator solve. |
| PRICE overflow tolerance | `1e-3 × ΣN` MW | Designed | Maximum positive aggregate overflow stopping test. |
| PRICE complementary-slackness tolerance | $1/hour | Designed | Maximum `mu × (K-Q)+` stopping test. |
| PRICE price-change tolerance | $0.01/MWh | Designed | Used with the aggregate-injection-change alternative stopping test. |
| Warm starts | enabled | Designed | Prior-hour plan and price tails initialize the next receding-horizon solve. |

## 7. Monitor calibration (§4, Part III)

| Parameter | Value | Status | Basis |
|---|---|---|---|
| Noise regimes | low = system-wide STWPF, horizon ≤ 6 h; medium = resource-level COP; high = resource-level worst quartile or system horizon ≥ 24 h | Calibrated | Empirical σ from 1.6. Historical ERCOT reference values for STWPF MAPE as a % of installed capacity: hour-ahead ≈ 3–4 %, day-ahead ≈ 4–7 % (2013–2016) [R13]. |
| Withholding grid `m` | {0.02, 0.05, 0.10, 0.20} × nameplate | Designed | Physical units so that noisier regimes visibly degrade detection. |
| Thresholds | σ-multiples {0.5 … 3} and absolute {0.02, 0.05, 0.10, 0.15} | Designed | |
| Discount δ, delay d | 0.98 per period; d ∈ {1, 4, 12} | Designed | §4 formulas for F* and T*. |
| Fine cap, correction loss | F̄ = 3 g; ℓ = 0.25 g per period | Designed | |
| Enforceability | κ(σ) = exp(−2σ) | Designed | §4 "enforcement friction". |

## References

- [R1] ERCOT. *Historical DAM Load Zone and Hub Prices* (NP4-180-ER) and *Historical RTM Load Zone and Hub Prices* (NP6-785-ER). ERCOT Market Information System, https://www.ercot.com/mp/data-products. Accessed via the `gridstatus` Python package (v0.36), https://github.com/gridstatus/gridstatus.
- [R2] ERCOT. *60-Day SCED Disclosure Reports* (NP3-965-ER), *60-Day DAM Disclosure Reports* (NP3-966-ER), and *60-Day COP Adjustment Period Snapshot*. https://www.ercot.com/mp/data-products.
- [R3] ERCOT. *Wind Power Production – Hourly Averaged Actual and Forecasted Values* (NP4-732-CD) and *… by Geographical Region* (NP4-742-CD). https://www.ercot.com/mp/data-products.
- [R4] U.S. Energy Information Administration. *Form EIA-860, Annual Electric Generator Report, 2023 final release.* https://www.eia.gov/electricity/data/eia860/archive/xls/eia8602023.zip.
- [R5] Enel North America (2022). *As Texas energy demand increases, Enel Green Power installs more renewable and storage capacity* (Azure Sky: 350 MW wind + 136.5 MW / 204.6 MWh storage). https://www.enelnorthamerica.com/about-us/newsroom/search-press/press/2022/07/enel-green-power-installs-more-renewable-and-storage-capacity.
- [R6] Gorman, W., et al. (2025). *Hybrid Power Plants: Status of Operating and Proposed Plants, 2025 Data Update.* Lawrence Berkeley National Laboratory. https://emp.lbl.gov/sites/default/files/2025-10/Hybrid_Plant_Tracking_2025_final_v1.pdf (local copy: `docs/references/LBNL_Hybrid_Plant_Tracking_2025.pdf`; wind+storage fleet table p. 8/19; POI-limit statistics slide 54).
- [R7] National Renewable Energy Laboratory. *Annual Technology Baseline 2024 – Utility-Scale Battery Storage.* https://atb.nrel.gov/electricity/2024/utility-scale_battery_storage; Cole, W., and Frazier, A. W. (2019). *Cost Projections for Utility-Scale Battery Storage.* NREL/TP-6A20-73222; Cole, W., et al. (2025). *Cost Projections for Utility-Scale Battery Storage: 2025 Update.* NREL.
- [R8] Xu, B., Zhao, J., Zheng, T., Litvinov, E., and Kirschen, D. S. (2018). Factoring the cycle aging cost of batteries participating in electricity markets. *IEEE Transactions on Power Systems*, 33(2), 2248–2259; He, G., et al. (2020). Power system dispatch with marginal degradation cost of battery storage. *IEEE Transactions on Power Systems* (arXiv:1904.07771).
- [R9] Cole, W., and Karmakar, A. (2023). *Cost Projections for Utility-Scale Battery Storage: 2023 Update.* NREL/TP-6A40-85332 (pack cost and cycle-life assumptions used for the ≈100 $/MWh upper bound).
- [R10] California ISO (2020). *Hybrid Resources Phase 1 – Decision on co-located resources proposal* (aggregate capability constraint at the POI). https://www.caiso.com/documents/decisiononhybridco-locatedresourcesproposal-presentation-july2020.pdf.
- [R11] ERCOT. *Nodal Protocols, Section 6.6.5 Base Point Deviation Charges* (intermittent renewable resources exempt; tolerances in §6.6.5.1.1). https://www.ercot.com/mktrules/nprotocols.
- [R12] The Brattle Group (2024). *Value of Lost Load Study for the ERCOT Region.* https://brattle.com/wp-content/uploads/2024/09/Value-of-Lost-Load-Study-for-the-ERCOT-Region.pdf; Public Utility Commission of Texas, system-wide offer cap 5,000 $/MWh (16 TAC §25.505).
- [R13] Texas RE and ERCOT (2016). *Wind Operations Issues* (STWPF day-ahead and hour-ahead MAPE as % of installed capacity). https://www.texasre.org/Documents/Reliability%20Services/Weatherization%20Presenations/Texas%20RE%20and%20ERCOT%20Wind%20Operations%20Issues%20-%202016.pdf.
- [R14] Salazar-Peña, N., Tabares, A., and González-Mancera, A. (2026). MARLEM. *Applied Energy*, 412, 127546; von Stengel, B. (2016). Recursive inspection games. *Mathematics of Operations Research*, 41(3); and the other references in `docs/proposal.tex`.
