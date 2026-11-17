# ArchitectGuard Report: FinPay Authentication & Notification Architecture (2019–2026)

*Generated: 2026-11-17 18:39:10*

## 1. Assumptions Ledger

| ID | Statement | Category | Valid Until | Confidence | Status |
|---|---|---|---|---|---|
| A1 | SMS OTP gateway costs 0.25 INR per message within our 15,000 INR monthly budget | Financial | 2027-12-31 | 1.00 | VALID |
| A2 | Transactional Email API remains free up to 10,000 emails per day | Financial | 2028-01-01 | 1.00 | VALID |
| A3 | Legacy Telecom DLT template approval does not require annual renewal | Legal | 2028-12-31 | 1.00 | VALID |
| A4 | Redis session cache stays under 512 MB RAM on free tier | Technical | 2027-06-30 | 0.95 | VALID |

## 2. Architectural Decisions & Downstream Risk

| ID | Title | Criticality | Risk Score | Status |
|---|---|---|---|---|
| D2 | Stateless Zero-Cache Login Flow | 0.85 | 0.025 | VALID |
| D1 | Primary Login via SMS OTP | 0.95 | 0.000 | VALID |
| D3 | Skip Email Verification During Onboarding | 0.80 | 0.000 | VALID |
| D4 | Automated DLT SMS Alert Worker | 0.75 | 0.000 | VALID |
| D5 | SMS-Based Password & PIN Reset | 0.90 | 0.000 | VALID |

## 3. Dependency Mappings

```text
A1 ---> D1 (weight: 0.95) — Low SMS unit cost justifies SMS-first login
A1 ---> D4 (weight: 0.8) — High-frequency SMS alerts assume 0.25 INR tariff
A3 ---> D1 (weight: 0.7) — Relies on uninterrupted DLT SMS delivery
A3 ---> D4 (weight: 0.75) — Transactional templates require valid DLT status
A4 ---> D2 (weight: 0.6) — Avoids using Redis RAM for long-lived sessions
D1 ---> D2 (weight: 0.9) — Cheap per-login SMS removes need for session caching
D1 ---> D3 (weight: 0.85) — Phone number alone acts as verified identity
D3 ---> D5 (weight: 0.9) — Without verified emails, recovery must use SMS
```
