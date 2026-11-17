# 0002. Cache User Sessions in Redis

Date: 2024-04-01
Status: Accepted

## Context and Problem Statement
High read volume on user profile queries causes latency spikes on the primary database.
- Redis memory footprint must stay under 512 MB on free tier.
- Redis network latency must stay under 2ms for 99th percentile.

## Decision Outcome
Chosen option: Redis 7.2 cluster for caching user session tokens and hot profile data with 24-hour TTL.

## Consequences
- Requires fallback logic if Redis cluster is temporarily unreachable.
