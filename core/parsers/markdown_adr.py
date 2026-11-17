import re
from datetime import date
from pathlib import Path
from typing import List, Optional, Tuple

from core.logger import get_logger
from core.models import Assumption, Decision, DependencyEdge

logger = get_logger("adr_parser")


class ADRParseResult:
    def __init__(
        self,
        decision: Decision,
        assumptions: List[Assumption],
        dependencies: List[DependencyEdge],
    ):
        self.decision = decision
        self.assumptions = assumptions
        self.dependencies = dependencies


class MarkdownADRParser:
    """Parses Architecture Decision Records (ADRs) written in Markdown.
    Supports MADR, Nygard, and generic Markdown ADR templates.
    """

    ASSUMPTION_CUES = [
        r"\bassum(?:e|ing|ption|ptions)\b",
        r"\bcost[s]?\b",
        r"\blimit[s]?\b",
        r"\bbudget\b",
        r"\bunder\s+\d+",
        r"\bless\s+than\b",
        r"\brequires?\b",
        r"\bdepends?\s+on\b",
        r"\bfree\s+tier\b",
        r"\bsla\b",
        r"\buptime\b",
    ]

    def __init__(self):
        self._cue_pattern = re.compile("|".join(self.ASSUMPTION_CUES), re.IGNORECASE)

    def parse_file(self, filepath: Path) -> ADRParseResult:
        """Parse a single ADR markdown file."""
        text = filepath.read_text(encoding="utf-8")
        filename = filepath.stem

        # Extract ID (e.g. 0001-use-postgres -> D_0001 or ADR_0001)
        id_match = re.match(r"^(\d+)", filename)
        if id_match:
            decision_id = f"D_{id_match.group(1).zfill(3)}"
        else:
            decision_id = f"D_{re.sub(r'[^a-zA-Z0-9_]', '_', filename)[:10].upper()}"

        # Extract Title (H1 header # Title)
        title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()
            # Clean leading number if present (e.g. "# 1. Record architecture decisions")
            title = re.sub(r"^\d+\.\s*", "", title)
        else:
            title = filename.replace("-", " ").replace("_", " ").title()

        # Extract Date
        date_match = re.search(r"(?:Date|date):\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", text)
        decision_date = date.today()
        if date_match:
            try:
                decision_date = date.fromisoformat(date_match.group(1))
            except ValueError:
                pass

        # Extract Sections
        sections = self._extract_sections(text)

        # Build Description from Context / Decision
        desc_parts = []
        if "decision" in sections:
            desc_parts.append(sections["decision"])
        elif "decision outcome" in sections:
            desc_parts.append(sections["decision outcome"])

        if "context" in sections:
            desc_parts.append(f"Context: {sections['context']}")
        elif "context and problem statement" in sections:
            desc_parts.append(f"Context: {sections['context and problem statement']}")

        description = "\n\n".join(desc_parts) if desc_parts else text[:300].strip()

        decision = Decision(
            id=decision_id,
            title=title[:80],
            description=description[:500],
            created_at=decision_date,
            criticality=0.8,
        )

        # Extract Assumptions
        extracted_assumptions: List[Assumption] = []
        dependencies: List[DependencyEdge] = []

        # Check explicit Assumptions section first
        explicit_assumptions = []
        for sec_name, sec_content in sections.items():
            if "assumption" in sec_name or "considered option" in sec_name:
                explicit_assumptions.extend(self._extract_bullet_items(sec_content))

        # Check Context section for implicit assumption cues
        context_text = sections.get("context", "") or sections.get("context and problem statement", "")
        context_bullets = self._extract_bullet_items(context_text)
        implicit_assumptions = [
            b for b in context_bullets if self._cue_pattern.search(b)
        ]

        raw_assumptions = explicit_assumptions + [
            b for b in implicit_assumptions if b not in explicit_assumptions
        ]

        for idx, stmt in enumerate(raw_assumptions, start=1):
            if len(stmt) < 5:
                continue
            a_id = f"A_{decision_id}_{idx}"
            category = "Financial" if re.search(r"\b(cost|price|budget|inr|usd|\$|euro|fee)\b", stmt, re.I) else (
                "Legal" if re.search(r"\b(compliance|gdpr|dlt|law|policy|legal)\b", stmt, re.I) else "Technical"
            )
            assumption = Assumption(
                id=a_id,
                statement=stmt[:150],
                category=category,
                confidence=1.0,
            )
            extracted_assumptions.append(assumption)
            dependencies.append(
                DependencyEdge(
                    source_id=a_id,
                    target_id=decision_id,
                    weight=0.85,
                    rationale=f"Derived from ADR: {filename}",
                )
            )

        logger.info(f"Parsed {filepath.name}: Decision {decision.id}, {len(extracted_assumptions)} assumptions")
        return ADRParseResult(decision, extracted_assumptions, dependencies)

    def parse_directory(self, dirpath: Path) -> List[ADRParseResult]:
        """Scan directory and parse all markdown files."""
        results = []
        for file in sorted(dirpath.glob("*.md")):
            if file.name.lower() in ("readme.md", "template.md"):
                continue
            try:
                results.append(self.parse_file(file))
            except Exception as e:
                logger.warning(f"Skipping {file.name} due to parse error: {e}")
        return results

    @staticmethod
    def _extract_sections(text: str) -> dict:
        """Split markdown by H2 headers (## Header)."""
        sections = {}
        pattern = re.compile(r"^##\s+(.+)$", re.MULTILINE)
        matches = list(pattern.finditer(text))

        for i, match in enumerate(matches):
            header = match.group(1).strip().lower()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            sections[header] = text[start:end].strip()

        return sections

    @staticmethod
    def _extract_bullet_items(text: str) -> List[str]:
        """Extract lines starting with -, *, or number bullet."""
        items = []
        for line in text.splitlines():
            line = line.strip()
            bullet_match = re.match(r"^[-*•]\s+(.+)$", line) or re.match(r"^\d+\.\s+(.+)$", line)
            if bullet_match:
                items.append(bullet_match.group(1).strip())
        return items
