# ArchitectGuard (ag) 🛡️

> Architectural decision watchdog and assumption drift monitor. Catch ADR decay before incidents happen.

Every engineering team writes Architecture Decision Records (ADRs). But ADRs almost always decay because the **underlying assumptions** change without anyone noticing:
- A vendor changes pricing or rate limits
- A regulatory framework changes compliance mandates
- Traffic exceeds the boundary conditions where the decision made sense
- A production database latency or connection pool begins exceeding planned thresholds

**ArchitectGuard** models assumptions and decisions as a Directed Acyclic Graph (DAG) and links them directly to **live operational probes** (HTTP latency, TLS expiry, database ports, JSON APIs). When an assumption breaks or expires, risk propagates downstream through your dependency chains to show exactly which architectural components are compromised in real time.

---

## Quickstart

### Installation

```bash
git clone https://github.com/Mohitgujjar07/ArchitectGuard.git
cd ArchitectGuard
pip install -e .
```

To include optional local neural embeddings, FastAPI, and the Streamlit dashboard:
```bash
pip install -e ".[all]"
```

Both `ag` and `architectguard` CLI commands are now available in your terminal.

---

### 1. Initialize a Project

In your repo root:
```bash
ag init "FinPay Payment Microservice"
```
This creates a local `.architectguard/` directory with a SQLite store and configuration.

### 2. Track Assumptions and Decisions

```bash
# Add foundational premises
ag add assumption A1 "Postgres connection pool handles up to 500 peak connections" \
  --category Technical \
  --valid-until 2026-12-31 \
  --scope "< 15k active users"

ag add assumption A2 "SMS gateway pricing stays under 0.20 INR per OTP" \
  --category Financial \
  --valid-until 2025-10-01

# Add architectural decisions
ag add decision D1 "Synchronous direct checkout" "Process orders synchronously on API thread" --criticality 0.9
ag add decision D2 "SMS OTP for checkout verification" "Verify each payment via SMS" --criticality 0.8

# Map dependencies
ag link A1 D1 --weight 0.85 --rationale "Fast DB required for synchronous checkout"
ag link A2 D2 --weight 0.90 --rationale "Low SMS cost justifies mandatory OTP"
```

### 3. Check Architecture Health

```bash
ag status
```
Outputs a colored overview showing valid, at-risk, and invalid assumptions alongside downstream decision risk scores.

### 4. Connect Live Operational Probes (Reality Watchdogs)

Connect your architectural premises to live infrastructure instead of just theoretical models:

```bash
# Real HTTP latency probe (< 250ms)
ag attach-probe A1 --type http --url "https://api.mycompany.com/health" --max-latency 250

# Real Postgres/Redis TCP port reachability probe
ag attach-probe A2 --type socket --host "db.internal" --port 5432

# Real TLS/SSL certificate expiration probe (> 30 days)
ag attach-probe A3 --type tls --host "auth.mycompany.com" --min-days 30

# Real JSON metrics assertion probe
ag attach-probe A4 --type json_api --url "https://api.github.com/repos/Mohitgujjar07/ArchitectGuard" --field "open_issues_count" --operator "<=" --threshold 512
```

Execute all live probes:
```bash
ag probe
```
If reality violates an assumption, ArchitectGuard **automatically trips the assumption** in your SQLite store and propagates risk down your architecture graph in real time!

### 5. CI/CD Pipeline Integration (GitHub Actions)

Add `ag check` to your CI/CD workflow:

```bash
ag check --fail-on-expired --fail-on-risk-above 0.5
```
Exits with code `1` if any assumption has passed its expiration date or if any decision's cumulative risk score exceeds your threshold, blocking the PR from merging.

### 6. Import Existing Markdown ADRs

If your team already writes Architecture Decision Records (e.g., in `docs/adr/`):

```bash
ag import-adr docs/adr/
```
ArchitectGuard automatically extracts decision titles, dates, descriptions, and parses premise statements into tracked assumptions.

### 7. What-If Counterfactual Simulation

Before committing a rewrite, simulate what happens when an assumption breaks:

```bash
ag simulate \
  --break A2 \
  --replace D2 \
  --alt-title "Switch to Authenticator App TOTP" \
  --support A1 \
  --dep-weight 0.4
```
Calculates whether the alternative design reduces your system's overall blast radius score without touching your active graph state.

### 8. Slack & Webhook Notifications

```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
ag notify --channel slack
```
Dispatches clean Slack alert blocks whenever assumptions expire or decisions become `AT_RISK`.

---

## CLI Command Reference

| Command | Description |
|---|---|
| `ag init [name]` | Initialize `.architectguard/` and create SQLite database |
| `ag add assumption` | Record a new architectural assumption or boundary condition |
| `ag add decision` | Record an architectural decision record (ADR) |
| `ag link` | Create a directed dependency edge with weight and rationale |
| `ag attach-probe` | Connect an assumption to a live HTTP, TLS, socket, or JSON probe |
| `ag probe` | Run live operational probes and auto-trip graph on failure |
| `ag status` | Display formatted summary table of all nodes and risk propagation |
| `ag check` | Validate assumption health (ideal for CI gates) |
| `ag import-adr` | Scan and parse Markdown ADR files into decisions & assumptions |
| `ag export` | Export report to formatted Markdown or JSON |
| `ag simulate` | Run counterfactual what-if replacement analysis |
| `ag notify` | Dispatch formatted Slack/webhook alerts when risks trigger |
| `ag load-demo` | Load the reference FinPay scenario for testing |

---

## How Risk Propagation Works

Risk propagates in topological order across the DAG:
1. When an assumption confidence degrades ($1.0 \to 0.0$), the failure rate is transmitted across each outgoing edge scaled by the edge `weight` ($w \in [0.1, 1.0]$).
2. For decisions with multiple dependencies, threats combine using independent survival probability:
   $$\text{survival} = \prod_i (1 - \text{transmitted\_risk}_i)$$
3. The raw threat $(1 - \text{survival})$ is scaled by the decision's `criticality` score to yield the final `risk_score`.
4. Any decision with a `risk_score \ge 0.35` is flagged as `AT_RISK`.

---

## Running Tests

ArchitectGuard includes a comprehensive `pytest` suite:

```bash
pytest
```

---

## License

MIT
