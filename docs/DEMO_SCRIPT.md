# ArchitectGuard (ag) — 5-Minute Demo Script

Use this script to present or demo **ArchitectGuard** to colleagues, engineering leads, interviewers, or evaluators.

---

## ⏱️ Minute 1: The Pitch & The Problem

> *"Every engineering team writes Architecture Decision Records (ADRs). We decide to use Redis for caching, SMS OTP for logins, or synchronous APIs instead of queues.*
>
> *The problem is: **decisions don't fail because the code was bad. Decisions fail because the real-world assumptions underneath them changed quietly.***
>
> *For example: You chose SMS login in 2020 because telecom rates were cheap. Three years later, vendor prices increase by 400%, and telecom compliance rules change. Nobody tracks that original financial assumption, so the decision quietly turns toxic until an unexpected ₹500,000 AWS bill or an outage hits production.*
>
> *I built **ArchitectGuard** to solve this. It models architecture decisions and real-world premises as a Directed Acyclic Graph (DAG) and mathematically propagates risk downstream whenever assumptions degrade, expire, or fail live operational probes."*

---

## ⏱️ Minute 2: The Core Architecture

> *"Under the hood, ArchitectGuard has four key engineering pillars:*
>
> 1. * **Topological Risk Propagation**: Built with NetworkX. When an assumption breaks, failure probability propagates in topological order across multi-hop dependencies, scaling with each decision's criticality.
> 2. * **Live Reality Probes**: Instead of theoretical simulations, assumptions can be linked directly to live HTTP latency probes, TLS certificate expiry checks, and TCP database socket pings.
> 3. * **SQLite Persistence & CLI First**: Powered by an intuitive terminal CLI (`ag`) backed by SQLite so your architecture state survives reboots and team workflows.
> 4. * **Markdown ADR Auto-Ingestion**: Ingests standard Markdown ADR files (`ag import-adr docs/adr/`), automatically parsing premise statements into tracked graph nodes."*

---

## ⏱️ Minute 3: Live Terminal Demonstration

### Command 1: Inspect Current Architecture
```bash
ag status
```
> *"Notice the terminal output. We see our foundational assumptions, their expiration dates, live probe statuses, and downstream decisions with their calculated risk scores."*

### Command 2: Execute Live Reality Probes
```bash
ag probe
```
> *"Here, ArchitectGuard makes real network calls to production endpoints and database ports. If any service fails its latency or reachability SLA, it automatically trips the assumption and flags all compromised decisions!"*

### Command 3: Simulate What-If
```bash
ag simulate --break A1 --replace D1 --alt-title "Switch to Email OTP + Persistent Sessions" --support A2 --dep-weight 0.4
```
> *"Before we commit to a rewrite, we run a counterfactual what-if simulation to measure whether the proposed design actually reduces our total system blast radius."*

---

## ⏱️ Minute 4: Developer Workflow & CI/CD Gate

### Command 4: Ingest Existing ADRs
```bash
ag import-adr docs/adr/
```
> *"Teams don't have to manually enter data. ArchitectGuard parses Markdown ADR files, extracts premise statements, and wires up dependency edges automatically."*

### Command 5: The CI Gate
```bash
ag check --fail-on-expired --fail-on-risk-above 0.5
```
> *"This is the killer feature. In our GitHub Actions pipeline, `ag check` runs on every Pull Request. If an engineer introduces a decision that relies on an expired or compromised assumption, CI exits with code 1 and blocks the PR from merging."*

---

## ⏱️ Minute 5: Summary & Vision

> *"To summarize: ArchitectGuard bridges the gap between static architecture documentation and living production reality. It gives teams an automated early-warning radar for architectural debt before it becomes an incident.*
>
> *The project is open-source, fully tested with pytest, supports SQLite persistence, CLI (`ag`), REST API via FastAPI, and an interactive Streamlit dashboard."*

---

## 🎯 Anticipated Questions & Answers

| Question | Winning Answer |
|---|---|
| **"Why not just use Jira or Confluence?"** | *"Confluence is static text where documentation goes to die. It cannot compute multi-hop risk propagation, cannot run live network probes, and cannot block a GitHub pull request when an assumption expires."* |
| **"How does risk propagate across multiple parents?"** | *"We use an independent survival probability model: $\text{survival} = \prod (1 - \text{transmitted\_risk}_i)$. Threats combine probabilistically, and the raw threat is scaled by the decision's criticality."* |
| **"Can this run in our private VPC?"** | *"Yes. ArchitectGuard is 100% local and offline. It requires zero cloud APIs, stores everything in local SQLite, and runs cleanly inside private CI/CD runners."* |
