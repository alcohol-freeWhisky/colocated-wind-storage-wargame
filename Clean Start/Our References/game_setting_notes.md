# Game-theoretic setting

The references describe two related models. The operating game studies dispatch through a shared connection. The inspection game studies strategic reports used to allocate that connection. They are not yet one integrated model.

**Color key.**

- <span style="color:#1971C2"><b>Decision variable</b></span>: chosen by a player.
- <span style="color:#E8590C"><b>Random quantity</b></span>: drawn by Nature.
- <span style="color:#2F9E44"><b>Parameter</b></span>: fixed and known before play.
- <span style="color:#9C36B5"><b>Derived quantity</b></span>: determined by the others through the model's rules.

---

## 1. Operating game (report §2, Workshop 1)

### 1.1 Players and assumptions

Players: owners $i\in\{1,\dots,N\}$, $N=5$. In the benchmark, one planner controls all owners. The market operator is not a player.

- **O1 Price taking.** Owners' actions do not affect prices.
- **O2 Fixed day-ahead.** Positions $b_{i,t}$ and prices $\pi^{DA}_t$ are cleared before the game.
- **O3 Hourly periods.** $t=1,\dots,T$ with $T=24$, so 1 MW for one period equals 1 MWh.
- **O4 Information.** *Perfect foresight*: the day's $W_{i,t}$ and $\pi^{RT}_t$ are known. *Forecast*: the current hour is known; later hours use the forecast $\widehat W_{i,t}$ and the price $\pi^{DA}_t$.
- **O5 Receding horizon.** Each hour, owners re-solve over the remaining hours and implement only the current action.
- **O6 Connection rule.** Stylized proportional rule, not ISO practice.
- **O7 Storage.** Grid charging is allowed ($g_{i,t}<0$ possible). Simultaneous charge and discharge is not excluded.

### 1.2 Quantities

| Symbol | Meaning | Type |
|---|---|---|
| ${\color{#1971C2}r_{i,t}},\ {\color{#1971C2}c_{i,t}},\ {\color{#1971C2}d_{i,t}}$ | curtailment, charge, requested discharge | decision |
| ${\color{#E8590C}W_{i,t}}$ | available wind | random |
| ${\color{#E8590C}\pi^{RT}_t}$ | real-time price | random |
| ${\color{#2F9E44}\widehat W_{i,t}},\ {\color{#2F9E44}\pi^{DA}_t},\ {\color{#2F9E44}b_{i,t}}$ | wind forecast (COP), day-ahead price, day-ahead position | parameter |
| ${\color{#2F9E44}K}$ | connection capacity, $0.6\times$ total wind nameplate | parameter |
| ${\color{#2F9E44}E_i},\ {\color{#2F9E44}P_i}$ | battery energy (MWh) and power (MW) capacity | parameter |
| ${\color{#2F9E44}\eta^c_i},\ {\color{#2F9E44}\eta^d_i}$ | charge and discharge efficiency, each $\sqrt{0.85}$ | parameter |
| ${\color{#2F9E44}\gamma_i}$ | wear cost per MWh discharged, 10 | parameter |
| ${\color{#2F9E44}\delta_D},\ {\color{#2F9E44}\lambda^-},\ {\color{#2F9E44}\lambda^+}$ | delivery fraction 0.5, shortfall charge 250, overflow charge 100 (per MWh) | parameter (design) |
| ${\color{#9C36B5}g_{i,t}},\ {\color{#9C36B5}\widehat q_{i,t}}$ | wind offered, requested net export | derived |
| ${\color{#9C36B5}\alpha_t},\ {\color{#9C36B5}\tilde q_{i,t}},\ {\color{#9C36B5}\tilde g_{i,t}},\ {\color{#9C36B5}\tilde d_{i,t}}$ | scaling factor, realized export, wind, discharge | derived |
| ${\color{#9C36B5}s_{i,t}},\ {\color{#9C36B5}D_t}$ | stored energy, delivery target | derived |

### 1.3 Model

Requests and their limits:
$$
{\color{#9C36B5}g_{i,t}}={\color{#E8590C}W_{i,t}}-{\color{#1971C2}c_{i,t}}-{\color{#1971C2}r_{i,t}},\qquad
{\color{#9C36B5}\widehat q_{i,t}}={\color{#9C36B5}g_{i,t}}+{\color{#1971C2}d_{i,t}},
$$
$$
0\le c_{i,t},d_{i,t}\le P_i,\qquad 0\le r_{i,t}\le W_{i,t},\qquad d_{i,t}\le\eta^d_i s_{i,t}.
$$

Connection rule. If some request is positive,
$$
{\color{#9C36B5}\alpha_t}=\min\left\{1,\frac{{\color{#2F9E44}K}}{\sum_j \widehat q_{j,t}^{+}}\right\},
$$
and $\alpha_t=1$ otherwise. For $\widehat q_{i,t}>0$:
$$
\tilde q_{i,t}=\alpha_t\widehat q_{i,t},\qquad
\tilde g_{i,t}=\min\{g_{i,t},\tilde q_{i,t}\},\qquad
\tilde d_{i,t}=\tilde q_{i,t}-\tilde g_{i,t}.
$$
For $\widehat q_{i,t}\le0$ nothing is scaled: $\tilde q_{i,t}=\widehat q_{i,t}$ and $\tilde d_{i,t}=d_{i,t}$. Hence $\sum_i\tilde q_{i,t}\le K$. Rejected wind is curtailed; unexecuted discharge stays in storage.

Battery:
$$
{\color{#9C36B5}s_{i,t+1}}=s_{i,t}+\eta^c_i c_{i,t}-\frac{\tilde d_{i,t}}{\eta^d_i},\qquad
0\le s_{i,t}\le E_i,\qquad s_{i,1}=\tfrac12E_i,\qquad s_{i,T+1}\ge s_{i,1}.
$$

**Minimal payoff** (two-settlement):
$$
U_i=\sum_{t=1}^{T}\Big[\pi^{DA}_t b_{i,t}+\pi^{RT}_t(\tilde q_{i,t}-b_{i,t})-\gamma_i\tilde d_{i,t}\Big].
$$
The terms in $b_{i,t}$ do not depend on dispatch, so they change payoffs but not optimal actions.

**Implemented payoff** (designed extension). With delivery target $D_t=\delta_D\sum_i\widehat W_{i,t}$, owner $i$ also pays:

- *EQ rule:* $\frac1N\big[\lambda^-(D_t-\sum_j\tilde q_{j,t})^+ +\lambda^+(\sum_j\widehat q_{j,t}-K)^+\big]$.
- *INJ rule:* $\lambda^-(\delta_D\widehat W_{i,t}-\widehat q_{i,t})^+ +\lambda^+\frac{\widehat q_{i,t}^+}{\sum_j\widehat q_{j,t}^+}(\sum_j\widehat q_{j,t}-K)^+$.

The overflow term uses *requested* exports and is a planning charge only.

**Information regimes.**
- *FULL:* owner $i$ sees the others' plans and best-responds.
- *PRICE:* a coordinator posts a congestion price $\mu_t$, raised until $\sum_i\widehat q_{i,t}\le K$. It replaces the overflow charge.
- *NONE:* owner $i$ sees nothing about the others and limits its export to its nameplate share of $K$.

**System score** (realized; transfers and planning charges excluded):
$$
J=\sum_{i,t}\Big[\pi^{DA}_t b_{i,t}+\pi^{RT}_t(\tilde q_{i,t}-b_{i,t})-\gamma_i\tilde d_{i,t}\Big]-\lambda^-\sum_t\Big(D_t-\sum_i\tilde q_{i,t}\Big)^+.
$$

### 1.4 Equilibrium and designs

- **Nash equilibrium.** A profile $\sigma^\ast$ such that $U_i(\sigma_i^\ast,\sigma_{-i}^\ast)\ge U_i(\sigma_i,\sigma_{-i}^\ast)$ for every $i$ and feasible $\sigma_i$. It is computed by damped best-response iteration, stopped when no owner gains more than 1 USD.
- **Which designs are equilibria.** Only converged FULL fixed points are equilibrium candidates. PRICE and NONE are coordination rules, not equilibria.
- **Designs.** There are $2+2\times2\times3=14$: the planner under perfect or forecast information, plus 12 owner designs (foresight $\times$ EQ/INJ $\times$ FULL/PRICE/NONE). FULL and PRICE differ in mechanism as well as information, so their gap is not a pure information effect.
- **Scope.** The 60-day comparison holds for its data and assumptions only.

**Toy example.** Two owners, two hours, $K=1$. (Charge, Charge) is the unique equilibrium of the two-action game, with joint payoff 95; a planner earns 115. This illustrates congestion; it is not an equilibrium of the continuous-action game.

---

## 2. Reporting and inspection game (`main.pdf`)

### 2.1 Players and assumptions

Players: owners $i\in\mathcal I=\{1,\dots,N\}$, $N\ge2$, and one monitor.

- **I1 Private capability.** $h_{i,t}$ is known to owner $i$ before it reports. The monitor never observes it directly. $h_t$ may be correlated across owners and over time.
- **I2 Public information.** Reports, allocations, metered exports, past audit outcomes, and the remaining budget $m_t$.
- **I3 Exact metering.** $x_{i,t}$ is measured without error.
- **I4 Gaussian evidence.** $\varepsilon_t\sim N(0,\Sigma)$ with $\Sigma\succ0$ known. It is independent of $h_t$ and of everything the owners observe.
- **I5 No underreporting.** $\ell_t\ge h_t$; underreporting is weakly dominated in the one-period game (§2.5).
- **I6 Imperfect proof.** $\eta_i$ is continuous, $\eta_i=0$ on $[0,\tau_i]$, and strictly increasing on $[\tau_i,\infty)$. Audit outcomes are independent. An unproved audit has no consequence.
- **I7 Pre-announced sanctions.** $F_i(d)\in[0,\bar F_i]$.

Assumptions used by specific results:

- **A1 Linear revenue.** $R_i(x;\omega)=px$ with a common price $p>0$.
- **A2 Metered self-incrimination.** If $x_{i,t}<k_{i,t}$ and $\ell_{i,t}-x_{i,t}>\tau_i$, owner $i$ pays $\bar F_i$ with probability one.
- **A3 i.i.d. capabilities.** $h_1,\dots,h_T$ are independent and identically distributed.

### 2.2 Quantities

| Symbol | Meaning | Type |
|---|---|---|
| ${\color{#1971C2}\ell_{i,t}}\in[0,\bar\ell_i]$ | reported capability (owner $i$) | decision |
| ${\color{#1971C2}A_t}\subseteq\mathcal I$ or ${\color{#1971C2}\mu}$ | audit set (no commitment) or announced audit policy (commitment) | decision (monitor) |
| ${\color{#E8590C}h_{i,t}}\in[0,\bar h_i]$ | feasible export (capability), private | random |
| ${\color{#E8590C}\varepsilon_t}$ | diagnostic error, $N(0,\Sigma)$ | random |
| ${\color{#E8590C}\omega_t}$ | prices and other public market variables | random |
| proof outcome | success with probability $\eta_i(d_{i,t})$ | random |
| ${\color{#2F9E44}N},\ {\color{#2F9E44}K},\ {\color{#2F9E44}T},\ {\color{#2F9E44}M},\ {\color{#2F9E44}\beta}$ | owners, capacity, horizon, audit budget, discount factor | parameter |
| ${\color{#2F9E44}\bar h_i},\ {\color{#2F9E44}\bar\ell_i}$ | capability and report caps, $\bar\ell_i\ge\bar h_i$ | parameter |
| ${\color{#2F9E44}\tau_i}$ | permitted tolerance | parameter |
| ${\color{#2F9E44}F_i(\cdot)},\ {\color{#2F9E44}\bar F_i}$ | sanction schedule and legal cap | parameter |
| ${\color{#2F9E44}c_i},\ {\color{#2F9E44}B_i(\cdot)}$ | audit cost, monitor's direct benefit of a proof | parameter |
| ${\color{#2F9E44}\eta_i(\cdot)},\ {\color{#2F9E44}\kappa_i}$ | proof probability; slope when $\eta_i(d)=\kappa_i d$ | parameter |
| ${\color{#2F9E44}\Sigma},\ {\color{#2F9E44}\theta},\ {\color{#2F9E44}\gamma},\ {\color{#2F9E44}p}$ | error covariance, screen threshold, weight on wasted headroom, price under A1 | parameter |
| ${\color{#9C36B5}d_{i,t}}$ | inflation $(\ell_{i,t}-h_{i,t})^+$ | derived |
| ${\color{#9C36B5}L_t},\ {\color{#9C36B5}L_{-i,t}},\ {\color{#9C36B5}Q_t}$ | total report, rivals' report, total capability | derived |
| ${\color{#9C36B5}\rho_t},\ {\color{#9C36B5}k_{i,t}},\ {\color{#9C36B5}x_{i,t}}$ | scaling factor, allocated headroom, metered export | derived |
| ${\color{#9C36B5}\widehat h_t},\ {\color{#9C36B5}z_t}$ | capability estimate, residual | derived |
| ${\color{#9C36B5}a_{i,t}},\ {\color{#9C36B5}m_t}$ | audit indicator $\mathbf 1\{i\in A_t\}$, remaining budget | derived |
| ${\color{#9C36B5}U_t},\ {\color{#9C36B5}H_t},\ {\color{#9C36B5}G_i}$ | unused headroom, harm, unilateral gain | derived |

### 2.3 Model

Allocation and export:
$$
{\color{#9C36B5}\rho_t}=\min\left\{1,\frac{{\color{#2F9E44}K}}{L_t}\right\},\qquad
{\color{#9C36B5}k_{i,t}}=\rho_t\,{\color{#1971C2}\ell_{i,t}},\qquad
{\color{#9C36B5}x_{i,t}}=\min\{{\color{#E8590C}h_{i,t}},k_{i,t}\}.
$$
Reports matter only when $L_t>K$. Raising $\ell_i$ raises $k_i$ and lowers every rival's $k_j$.

Evidence:
$$
{\color{#9C36B5}\widehat h_t}={\color{#E8590C}h_t}+{\color{#E8590C}\varepsilon_t},\qquad
{\color{#9C36B5}z_t}=\widehat h_t-{\color{#1971C2}\ell_t}=-d_t+\varepsilon_t.
$$

- **Screen.** $S_\theta=\mathbf 1\{z_t^\top\Sigma^{-1}z_t>\theta\}$. For fixed $d$, $z^\top\Sigma^{-1}z\sim\chi^2_N(\lambda)$ with $\lambda(d)=d^\top\Sigma^{-1}d$.
- **Screen probabilities.** False alarm $q_0=\Pr(S_\theta=1\mid d=0)$; detection $q_1(d)=\Pr(S_\theta=1\mid d)$. These differ from the audit probability and from the proof probability $\eta_i$. An alarm is a lead, not proof.
- **Audits.** At most $m_t$ audits in period $t$, with $m_1=M$, $|A_t|\le m_t$, and $m_{t+1}=m_t-|A_t|$. Each audit costs $c_i$. A proof triggers $F_i(d_{i,t})$.

Payoffs (owner $V_i$, monitor $V_M$):
$$
V_i=\mathbb E\sum_{t=1}^T\beta^{t-1}\Big[R_i(x_{i,t};\omega_t)-a_{i,t}\eta_i(d_{i,t})F_i(d_{i,t})\Big]\quad(\text{minus A2 sanctions, if imposed}),
$$
$$
V_M=\mathbb E\sum_{t=1}^T\beta^{t-1}\Big[-H_t+\sum_i a_{i,t}\big(\eta_i(d_{i,t})B_i(d_{i,t})-c_i\big)\Big].
$$
Baseline: $B_i\equiv0$, so a fine is not a benefit to the monitor.

Harm, relative to all-truthful reports (superscript tr):
$$
H_t=\gamma\big(U_t-U^{tr}_t\big)+\sum_i\big[R_i(x^{tr}_{i,t};\omega_t)-R_i(x_{i,t};\omega_t)\big]^+,\qquad
U_t=K-\sum_i x_{i,t},\quad U^{tr}_t=(K-Q_t)^+.
$$
The second term counts losers' losses and does not net out winners' gains. It is a chosen harm measure, not net welfare loss.

Unilateral gain (rivals' reports fixed; compared with $i$ reporting truthfully):
$$
G_i(\ell_i,\ell_{-i};h)=R_i\big(x_i(\ell_i,\ell_{-i};h)\big)-R_i\big(x_i(h_i,\ell_{-i};h)\big).
$$

### 2.4 Timing and solution concepts

Each period $t$:

1. Nature draws $h_t$; each owner observes its own $h_{i,t}$.
2. Owners report $\ell_t$ simultaneously.
3. The rule gives $k_t$ and $x_t$; the monitor observes $x_t$ and $z_t$.
4. The monitor chooses $A_t$ with $|A_t|\le m_t$.
5. Proofs and sanctions are realized (including A2 sanctions); outcomes become public; $m_{t+1}=m_t-|A_t|$.

Solution concepts:

- **No commitment.** The monitor picks $A_t$ after seeing the evidence. Solution concept: perfect Bayesian equilibrium, or Markov PBE with state $(t,m_t)$.
- **Commitment.** The monitor announces $\mu$ (public history $\to$ distribution over audit sets) at $t=0$. Owners then play a PBE of the induced game.
- **Simultaneous inspection game** (report, App. A.5 and B.2). A third timing assumption, not the same as no commitment.

### 2.5 How inflation works

Inflation changes the *report used by the allocation rule*, not physical capability: $\ell_{i,t}=h_{i,t}+d_{i,t}$ with $d_{i,t}\ge0$ and $\ell_{i,t}\le\bar\ell_i$.

**Example.** $K=100$ MW and $h_1=h_2=80$ MW.
- *Truthful reports* $(80,80)$: $k=(50,50)$ and $x=(50,50)$.
- *Owner 1 reports* $(120,80)$: $k=(60,40)$, both deliverable, so $x=(60,40)$.
- *Effect:* at 50 USD/MWh for one hour, owner 1 gains 500 USD and owner 2 loses 500 USD. The meter sees owner 1 deliver its full allocation, which does not reveal whether $h_1$ was 80 or 120. No capacity is created; only its division changes.
- *Detection limit:* owner 1 stays hidden while $k_1\le h_1$, i.e. $d_1\le\bar d_1=80\cdot60/20=240$ MW. Beyond that, $x_1=h_1<k_1$ reveals $h_1$, and A2 applies if $\ell_1-x_1>\tau_1$.

**Why inflation and not underreporting.** With rivals fixed, $k_i$ and $x_i=\min\{h_i,k_i\}$ are nondecreasing in $\ell_i$. If revenue is nondecreasing and nothing else rewards a low report, underreporting is weakly dominated in one period. If $h_i+L_{-i}\le K$, a truthful report already exports $h_i$.

Underreporting can matter if it lets an owner avoid an obligation, withhold supply, save storage, or benefit another asset or financial position. These motives need explicit rules and payoffs. A low forecast is not by itself deliberate withholding.

**Which curve is changed.**
- *Availability profile* $\ell_{i,1},\dots,\ell_{i,T}$: this is the attack modeled here. It changes connection shares, provided the reporting time and the truthful benchmark are defined.
- *Market offer curve* (price–quantity bids): this is not modeled. Prices are exogenous (O1), so price-moving attacks need an explicit clearing model.

### 2.6 Results in `main.pdf`

Each result holds only under its stated conditions.

- **Inflation pays only under congestion (Prop. 2).** If $h_i+L_{-i}\le K$, then $G_i\le0$ for every report.
- **What the meter reveals (Lemma 3).**
  - If $x_i<k_i$, then $h_i=x_i$ and $d_i=\ell_i-x_i$ become public.
  - If $h_i<K$ and $h_i+L_{-i}>K$, then $k_i\le h_i$ iff
  $$d_i\le\bar d_i(\ell_{-i})=\frac{h_i(h_i+L_{-i}-K)}{K-h_i}.$$
  - Inflation beyond $\bar d_i$ earns nothing more.
- **Stealth set and redistribution (Cor. 4, Prop. 5).**
  - The stealth set is $\mathcal S(h)=\{\ell:\ k_i\le h_i\ \forall i\}$.
  - Under A2, reports with $d_i>\max\{\bar d_i,\tau_i\}$ are weakly dominated.
  - Under A1 with $\ell\in\mathcal S(h)$ and $d\ne0$: $Q\ge K$, $U=U^{tr}=0$, and $H=\tfrac p2\sum_i\lvert x_i-x_i^{tr}\rvert$, independent of $\gamma$.
  - The $\chi^2$ screen can still flag such reports; "stealth" means hidden from the meter only.
- **Unilateral gain (Lemma 6).** Under A1, truthful rivals, $Q>K$, $h_i<K$, and $d\in[0,\bar d_i]$ with $\bar d_i=h_i(Q-K)/(K-h_i)$:
  $$G_i(d)=\frac{pK(Q-h_i)\,d}{Q(Q+d)},\qquad G_i'(0)=\frac{pK(Q-h_i)}{Q^2},\qquad G_i(\bar d_i)=\frac{ph_i(Q-K)}{Q}.$$
  The gain is increasing and concave. At most, an owner undoes its own curtailment, and rivals lose exactly $G_i(d)$.
- **No commitment (Prop. 8).**
  - With $B_i\equiv0$ and $c_i>0$, $A_T=\emptyset$ in every PBE.
  - Under A3, in a Markov PBE with state $(t,m_t)$ and budget-independent tie-breaking, $A_t=\emptyset$ for all $t$.
  - This comes from the monitor's payoff, not from inspection games in general. The remedies are commitment or $B_i>0$.
- **Truthful incentive constraint (Prop. 10).** Under commitment with truthful rivals, truth is optimal at every history iff
  $$G_i(\ell_i,h_{-i};h)\le\pi_i(\ell_i;\mu)\quad\text{for all }\ell_i\ge h_i,$$
  where $\pi_i$ is the expected current sanction, including A2. For a non-truthful target profile, add the deviation's continuation effect $\beta\,\mathbb E[\Delta V_i]$.
- **Deterrence (Thm. 12).** Conditions: A1, A2, truthful rivals, $Q>K$, $h_i<K$, $\tau_i=0$, and $\eta_i(d)=\kappa_i d$ with $\kappa_i\bar d_i\le1$. Let $\alpha_i(d)$ be the audit probability.
  - *Necessary:* if $\alpha_i$ is continuous at 0, then
  $$\alpha_i(0)\ge\alpha_i^\ast(h)=\frac{pK(Q-h_i)}{\kappa_i\bar F_iQ^2}.$$
  If $\alpha_i^\ast>1$, deterrence is impossible.
  - *Sufficient:* $F_i\equiv\bar F_i$, $\alpha_i(d)\ge\alpha_i(0)\ge\alpha_i^\ast$, and $\bar F_i\ge ph_i(Q-K)/Q$.
  - *Minimal fine:*
  $$F_i^{\min}(d)=\frac{pK(Q-h_i)}{\kappa_i\alpha_i(d)Q(Q+d)}.$$
  If $\alpha_i$ is nondecreasing, the smallest *nondecreasing* deterrent schedule is the flat fine $\lim_{d\downarrow0}F_i^{\min}(d)$.
- **Small deviations (Prop. 13).** Under A1, truthful rivals, $Q>K$, $h_i<K$:
  - if $\eta_i(d)F_i(d)=o(d)$, no policy deters small inflation. For example, a proportional fine with linear $\eta_i$ gives expected sanction of order $d^2$ against a gain of order $d$;
  - if $\tau_i>0$, every best response has $d_i\ge\min\{\tau_i,\bar d_i\}$, so the tolerance is used in full.
- **Audit budget (Prop. 14).** Conditions: commitment, public budget, A1, A2, $\tau_i=0$, $\kappa_i=\kappa$, $F_i\equiv\bar F$, $h_i<K$ a.s., and audit probabilities continuous at $d=0$. Then
  $$M\ge\operatorname{ess\,sup}\sum_{t=1}^T\mathbf 1\{Q_t>K\}\lceil s(h_t)\rceil,\qquad s(h)=\frac{pK(N-1)}{\kappa\bar FQ}.$$
  If $p(N-1)\le\kappa\bar F$, this means one audit per congested period. The bound is necessary, not a full audit recursion.
- **Symmetric rat race (Prop. 16, Cor. 17).** Conditions: $T=1$, A1, $h_i=h$ common knowledge, $Nh>K$, $\bar\ell_i=\bar\ell$, $\eta(d)=\kappa(d-\tau)^+$, $F\equiv\bar F$, and audit probability $\alpha$ independent of reports and evidence. The unique symmetric equilibrium is
  $$d^\ast=\min\left\{\bar\ell-h,\ \max\left\{\tau,\ \frac{pK(N-1)}{N^2\alpha\kappa\bar F}-h\right\}\right\},$$
  with the fraction set to $+\infty$ when $\alpha=0$.
  - Each owner exports $K/N=x_i^{tr}$, so $H=0$ and every owner pays $\alpha\kappa\bar F(d^\ast-\tau)^+$.
  - Truth is the equilibrium iff $\tau=0$ and $\alpha\ge pK(N-1)/(N^2h\kappa\bar F)$.
  - The monitor's payoff is $-N\alpha c$, so $\alpha=0$ is optimal. Monitoring has value only with heterogeneous owners or with costs that $H_t$ omits.
- **Detection geometry (Prop. 18).**
  - $\lambda(d)\ge\lVert d\rVert^2/\lambda_{\max}(\Sigma)$, so inflation is least visible along the top eigenvector of $\Sigma$.
  - For equicorrelated errors with correlation $r$, $\lambda(\delta\mathbf 1)/\lambda(\delta e_i)=N(1-r)/(1+(N-2)r)$, which is $<1$ iff $r>1/2$.
  - The $\chi^2$ screen has zero first-order power at $d=0$; a one-sided screen $w^\top(-z)>c\sqrt{w^\top\Sigma w}$ with $w\ge0$ does not.
- **Attribution (Prop. 19).** Under the hypothesis that only owner $i$ inflates, by $\delta_i$:
  $$T_i=\frac{[\Sigma^{-1}(-z)]_i}{\sqrt{(\Sigma^{-1})_{ii}}}\sim N\!\left(\frac{(\Sigma^{-1}d)_i}{\sqrt{(\Sigma^{-1})_{ii}}},1\right),\qquad
  \log\Lambda_i=\delta_i[\Sigma^{-1}(-z)]_i-\tfrac12\delta_i^2(\Sigma^{-1})_{ii}.$$
  The largest raw residual need not identify the likeliest violator (Example 20). Likelihood alone ignores audit cost, proof probability, and the value of saving budget.
- **Camouflage (Prop. 21).** The monitor audits $i$ iff $T_i>c$, the budget does not bind, and $F_i\equiv\bar F_i$. If $(\Sigma^{-1})_{ij}<0$ (e.g. positive correlation) and $\mathbb E[T_i]\le c$, a rival's inflation lowers both the level and the marginal of $i$'s expected sanction.
- **Audit targeting (Prop. 22).** Without commitment, under A3, with $B_i\ge0$: audit the owners with the largest indices
  $$I_{i,t}=\mathbb E[\eta_iB_i\mid y_t]-c_i,\qquad y_t=(\ell_t,x_t,z_t),$$
  up to the point where the next index falls below the shadow value of an audit, $\beta[W_{t+1}(m_t-k+1)-W_{t+1}(m_t-k)]$. Here $W_{t+1}$ is the monitor's continuation value; the cutoff rule needs $W_{t+1}$ concave.

**Class of game.** The owners play a proportional-share (Tullock/Kelly-type) contest for $K$. In Prop. 16 the payoff is $p\min\{h,K\ell_i/L\}-\alpha\kappa\bar F(\ell_i-h-\tau)^+$. Where $x_i=k_i$ (which includes the equilibrium) it equals
$$
p\,\frac{K\ell_i}{L}-\alpha\kappa\bar F\,(\ell_i-h-\tau)^+,
$$
a contest with linear cost. The full model adds private types, signal-dependent audits, a budget, and the stealth bound, which makes it a budgeted dynamic Bayesian inspection game (Dresher / von Stengel type) whose inspectees play such a contest. It should not be identified unconditionally with a standard Tullock game.

---

## 3. Points to resolve before combining the models

1. **Capability and storage.** In `main.pdf`, $h_{i,t}$ is exogenous (I1). In the operating game, feasible export depends on chosen dispatch and battery state. An integrated model must say what is known, chosen, and reported, and when.
2. **Inflation versus withholding.** `main.pdf` studies $\ell>h$. Workshop slide 11 monitors withholding via $v_{i,t}=\tilde q_{i,t}-b_{i,t}$, but the report says deviating from $b_{i,t}$ is not a violation. Fix the report, obligation, and prohibited behavior before choosing a signal.
3. **Audit incentives and termination.** In App. A.5, detection ends the episode and prevents future harm. So an early audit has value even with $B_i\equiv0$ (audit probability $1/3$ at state $(2,1)$). Prop. 8 has no termination, hence no audits. The results are consistent but rest on different continuation payoffs.
4. **Forecast timing.** Remark 7: if reports precede the realization of $h$, then $x_i<k_i$ can result from forecast error and no longer proves inflation. Wind fits this case, which `main.pdf` leaves open.
5. **Tolerance vs. truthfulness.** $d_i\le\tau_i$ is compliant but not truthful, and by Prop. 13 owners use the tolerance in full.
6. **Curtailment order.** The report's rule cuts battery discharge first ($\tilde g=\min\{g,\tilde q\}$), but slide 3 says "wind is cut first." Check the code.
7. **Penalty rules.** Slide 5 says both rules sum to the site's total charges. Under INJ, individual shortfall charges need not sum to the aggregate shortfall charge.
8. **Notation clashes across documents.**
   - $\alpha$: connection factor (report), audit probability (`main.pdf`), test size (slide 11).
   - $d$: discharge vs. inflation.
   - $U$: profit (report) vs. unused headroom (`main.pdf`).
   - $\gamma$: wear cost vs. weight on wasted headroom.
   - $\mu$: congestion price vs. audit policy.
   
   In this note, inspection payoffs are written $V_i, V_M$.

## 4. Candidate simulations

- Clarify what $Q_0$ denotes in the code, then remove it and rerun. Do not assume it is the false-alarm probability $q_0$; in `main.pdf`, $Q_t$ is total capability.
- Compute reporting equilibria for heterogeneous owners (open problem 1), including report caps, proof probabilities, and audit policies.
- Simulate correlated signals to measure screen power, ranking reversals, and camouflage under explicit policies.
- Compare a committed budgeted audit policy with the no-commitment game, stating whether detection ends the episode and what $B_i$ is.

## References

- `workshop1_recreated.pdf`: operating-game presentation and preliminary results.
- `6_s974_1016 (4).pdf`: operating model, monitoring extension, and inspection examples.
- `congestion_coupled_stealth_inspection_game.pdf`: earlier inspection-game formulation.
- `main.pdf`: developed inspection-game formulation and results.
- `last_meeting_todos.md`: outstanding project tasks.


---


1. Nonlinear Optimization
	1. Convex opti
2. Gradient Descent 
3. NOT: Newton (?)
4. 