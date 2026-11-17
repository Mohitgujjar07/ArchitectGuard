# 0001. Use PostgreSQL for Transactional Payment Ledger

Date: 2024-03-15
Status: Accepted

## Context and Problem Statement
We need an ACID compliant database for recording financial transactions and ledger entries.
- Assuming database server costs remain under $150 per month on AWS RDS.
- Database connection pool must scale up to 300 active connections.
- We require high availability with 99.99% SLA uptime.

## Decision Outcome
Chosen option: PostgreSQL 16 on Amazon RDS Multi-AZ.
We will route all financial debit/credit balance changes through strict row-level transactions.

## Consequences
- Requires persistent database connection management.
- Dependent on AWS RDS pricing staying within initial tier limits.
