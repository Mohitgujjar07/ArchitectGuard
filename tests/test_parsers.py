from pathlib import Path
import pytest

from core.parsers.markdown_adr import MarkdownADRParser


def test_markdown_adr_parser(tmp_path):
    sample_adr = """# 0001. Use PostgreSQL for Transactional Storage

Date: 2024-03-15

## Status
Accepted

## Context and Problem Statement
We need an ACID compliant database for order processing.
- Assuming database server costs remain under $150 per month on AWS RDS.
- Database connection pool must scale up to 300 active connections.
- We require high availability with 99.99% SLA uptime.

## Decision Outcome
Chosen option: PostgreSQL 16 on Amazon RDS.
"""
    adr_file = tmp_path / "0001-use-postgresql.md"
    adr_file.write_text(sample_adr, encoding="utf-8")

    parser = MarkdownADRParser()
    res = parser.parse_file(adr_file)

    # Check Decision
    assert res.decision.id == "D_0001"
    assert "Use PostgreSQL" in res.decision.title
    assert "Amazon RDS" in res.decision.description

    # Check Assumptions extracted
    assert len(res.assumptions) >= 2
    statements = [a.statement for a in res.assumptions]
    assert any("costs remain under $150" in s for s in statements)
    assert any("connection pool must scale" in s for s in statements)

    # Check Dependencies mapped
    assert len(res.dependencies) == len(res.assumptions)
    for dep in res.dependencies:
        assert dep.target_id == res.decision.id


def test_markdown_adr_parser_directory(tmp_path):
    adr1 = tmp_path / "0001-auth.md"
    adr1.write_text("# 1. Auth via JWT\n\n## Context\n- Must stay under 100ms verification latency.\n\n## Decision\nUse JWT.", encoding="utf-8")

    adr2 = tmp_path / "0002-cache.md"
    adr2.write_text("# 2. Redis Caching\n\n## Context\n- Redis RAM usage stays under 512MB.\n\n## Decision\nUse Redis.", encoding="utf-8")

    parser = MarkdownADRParser()
    results = parser.parse_directory(tmp_path)
    assert len(results) == 2
    ids = [r.decision.id for r in results]
    assert "D_0001" in ids
    assert "D_0002" in ids
