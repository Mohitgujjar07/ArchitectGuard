import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Tuple

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from core.logger import get_logger
from core.models import Assumption, Decision, DependencyEdge, NodeStatus
from core.graph_engine import ADIEGraphEngine
from core.storage import ProjectStore

app = typer.Typer(
    name="ag",
    help="ArchitectGuard: Architectural decision watchdog and assumption drift monitor.",
    add_completion=False,
)
add_app = typer.Typer(help="Add assumptions or decisions to the project graph.")
app.add_typer(add_app, name="add")

console = Console()
err_console = Console(stderr=True)
logger = get_logger("cli")

DEFAULT_DIR = ".architectguard"
DEFAULT_DB = f"{DEFAULT_DIR}/store.db"


def _get_project_context() -> Tuple[ProjectStore, ADIEGraphEngine]:
    """Find the nearest .architectguard directory and load the active project."""
    curr = Path.cwd()
    for parent in [curr] + list(curr.parents):
        for candidate_dir in [".architectguard", ".assumptionpulse"]:
            db_path = parent / candidate_dir / "store.db"
            if db_path.exists():
                store = ProjectStore(str(db_path))
                projects = store.list_projects()
                if not projects:
                    err_console.print("[red]Error:[/red] No projects found in store. Run [cyan]ag init[/cyan] first.")
                    raise typer.Exit(code=1)
                active_name = projects[0]["name"]
                data = store.load_project_data(active_name)
                engine = ADIEGraphEngine.from_project_data(data)
                engine.attach_storage(store)
                return store, engine

    err_console.print(
        "[red]Error:[/red] Not in an ArchitectGuard repository. Run [cyan]ag init[/cyan] to initialize."
    )
    raise typer.Exit(code=1)


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose debug logging.")
):
    if verbose:
        os.environ["AP_LOG_LEVEL"] = "DEBUG"


@app.command("init")
def init_cmd(
    project_name: str = typer.Argument("Default Architecture", help="Name of the architecture project")
):
    """Initialize AssumptionPulse repository in the current directory."""
    ap_dir = Path.cwd() / DEFAULT_DIR
    ap_dir.mkdir(parents=True, exist_ok=True)

    config_path = ap_dir / "config.yml"
    if not config_path.exists():
        config_path.write_text(
            f"# ArchitectGuard Configuration\n"
            f"project_name: \"{project_name}\"\n"
            f"risk_threshold: 0.35\n"
            f"similarity_threshold: 0.55\n"
            f"fail_on_expired: true\n"
            f"fail_on_risk_above: 0.5\n",
            encoding="utf-8",
        )

    store = ProjectStore(str(ap_dir / "store.db"))
    if not store.project_exists(project_name):
        engine = ADIEGraphEngine(project_name=project_name)
        store.save_project(engine)
        console.print(f"[green]✓[/green] Initialized ArchitectGuard project '[bold]{project_name}[/bold]'.")
    else:
        console.print(f"[yellow]![/yellow] Project '[bold]{project_name}[/bold]' already exists.")

    console.print(f"Store: [dim]{ap_dir / 'store.db'}[/dim]")
    console.print("Run [cyan]ag add assumption --help[/cyan] to begin tracking premises.")


@add_app.command("assumption")
def add_assumption_cmd(
    id: str = typer.Argument(..., help="Unique ID, e.g., A1"),
    statement: str = typer.Argument(..., help="Core premise statement"),
    category: str = typer.Option("Technical", "--category", "-c", help="Technical, Financial, Legal, Operational"),
    valid_until: Optional[str] = typer.Option(None, "--valid-until", help="Expiry date (YYYY-MM-DD)"),
    scope: str = typer.Option("Global", "--scope", help="Applicable scope"),
    confidence: float = typer.Option(1.0, "--confidence", help="Confidence value (0.0 to 1.0)"),
    owner: Optional[str] = typer.Option(None, "--owner", help="Owner / team"),
):
    """Add a foundational assumption to the active project."""
    store, engine = _get_project_context()
    parsed_date = None
    if valid_until:
        try:
            parsed_date = date.fromisoformat(valid_until)
        except ValueError:
            err_console.print(f"[red]Error:[/red] Invalid date format '{valid_until}'. Use YYYY-MM-DD.")
            raise typer.Exit(code=1)

    try:
        a = Assumption(
            id=id,
            statement=statement,
            category=category,
            valid_until=parsed_date,
            scope=scope,
            confidence=confidence,
            owner=owner,
        )
        engine.add_assumption(a)
        console.print(f"[green]✓[/green] Added assumption [bold]{id}[/bold]: '{statement}'")
    except Exception as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@add_app.command("decision")
def add_decision_cmd(
    id: str = typer.Argument(..., help="Unique ID, e.g., D1"),
    title: str = typer.Argument(..., help="Short decision name"),
    description: str = typer.Argument(..., help="Decision rationale"),
    criticality: float = typer.Option(0.8, "--criticality", help="Criticality (0.1 to 1.0)"),
    owner: Optional[str] = typer.Option(None, "--owner", help="Decision owner"),
):
    """Add an architectural decision (ADR) to the active project."""
    store, engine = _get_project_context()
    try:
        d = Decision(
            id=id,
            title=title,
            description=description,
            criticality=criticality,
            owner=owner,
        )
        engine.add_decision(d)
        console.print(f"[green]✓[/green] Added decision [bold]{id}[/bold]: '{title}'")
    except Exception as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@app.command("link")
def link_cmd(
    source_id: str = typer.Argument(..., help="Parent Assumption or Decision ID"),
    target_id: str = typer.Argument(..., help="Downstream Decision ID"),
    weight: float = typer.Option(1.0, "--weight", "-w", help="Dependency strength (0.1 to 1.0)"),
    rationale: str = typer.Option("", "--rationale", "-r", help="Why target depends on source"),
):
    """Link a parent assumption or decision to a downstream decision."""
    store, engine = _get_project_context()
    try:
        edge = DependencyEdge(
            source_id=source_id,
            target_id=target_id,
            weight=weight,
            rationale=rationale,
        )
        engine.add_dependency(edge)
        engine.propagate_impact()
        engine.auto_save()
        console.print(f"[green]✓[/green] Linked [bold]{source_id}[/bold] -> [bold]{target_id}[/bold] (w={weight:.2f})")
    except Exception as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@app.command("status")
def status_cmd():
    """Display comprehensive status of assumptions, decisions, and risk propagation."""
    store, engine = _get_project_context()
    engine.propagate_impact()

    console.print(Panel(f"[bold cyan]{engine.project_name}[/bold cyan] — Architecture Health Overview", expand=False))

    # Assumptions Table
    a_table = Table(title="Foundational Assumptions", header_style="bold magenta")
    a_table.add_column("ID", style="bold", width=6)
    a_table.add_column("Statement", width=40)
    a_table.add_column("Category", width=12)
    a_table.add_column("Valid Until", width=12)
    a_table.add_column("Confidence", justify="right", width=12)
    a_table.add_column("Status", width=10)

    for a in engine.assumptions.values():
        status_color = "green" if a.status == NodeStatus.VALID else "red"
        a_table.add_row(
            a.id,
            a.statement,
            a.category,
            str(a.valid_until or "None"),
            f"{a.confidence:.2f}",
            f"[{status_color}]{a.status.value}[/{status_color}]",
        )
    console.print(a_table)

    # Decisions Table
    d_table = Table(title="Architectural Decisions", header_style="bold cyan")
    d_table.add_column("ID", style="bold", width=6)
    d_table.add_column("Title", width=30)
    d_table.add_column("Criticality", justify="right", width=12)
    d_table.add_column("Risk Score", justify="right", width=12)
    d_table.add_column("Status", width=12)

    for d in sorted(engine.decisions.values(), key=lambda x: x.risk_score, reverse=True):
        if d.status == NodeStatus.AT_RISK:
            status_str = "[yellow]AT_RISK[/yellow]"
        elif d.status == NodeStatus.ARCHIVED:
            status_str = "[dim]ARCHIVED[/dim]"
        else:
            status_str = "[green]VALID[/green]"
        d_table.add_row(
            d.id,
            d.title,
            f"{d.criticality:.2f}",
            f"{d.risk_score:.3f}",
            status_str,
        )
    console.print(d_table)

    total_blast = round(sum(d.risk_score for d in engine.decisions.values() if d.status != NodeStatus.ARCHIVED), 4)
    at_risk_count = sum(1 for d in engine.decisions.values() if d.status == NodeStatus.AT_RISK)
    invalid_count = sum(1 for a in engine.assumptions.values() if a.status == NodeStatus.INVALID)

    console.print(f"\n[bold]System Blast Radius Score:[/bold] [bold red]{total_blast}[/bold red]")
    console.print(f"Broken Assumptions: [bold]{invalid_count}[/bold] | At-Risk Decisions: [bold]{at_risk_count}/{len(engine.decisions)}[/bold]\n")


@app.command("check")
def check_cmd(
    fail_on_expired: bool = typer.Option(True, "--fail-on-expired", help="Exit with non-zero code if any assumption is expired"),
    fail_on_risk_above: float = typer.Option(0.5, "--fail-on-risk-above", help="Exit with non-zero code if any decision exceeds risk"),
):
    """CI Check: Verify assumption health and fail if expired or high risk detected."""
    store, engine = _get_project_context()
    engine.propagate_impact()

    today = date.today()
    expired = []
    for a in engine.assumptions.values():
        if a.valid_until and today > a.valid_until and a.status != NodeStatus.INVALID:
            expired.append(a)

    high_risk = [d for d in engine.decisions.values() if d.risk_score >= fail_on_risk_above]

    has_failure = False

    if expired:
        console.print(f"[red]✗ {len(expired)} Expired Assumption(s) Found:[/red]")
        for a in expired:
            console.print(f"  - [bold]{a.id}[/bold]: '{a.statement}' (Expired {a.valid_until})")
        if fail_on_expired:
            has_failure = True

    if high_risk:
        console.print(f"\n[red]✗ {len(high_risk)} High-Risk Decision(s) Exceeding {fail_on_risk_above}:[/red]")
        for d in high_risk:
            console.print(f"  - [bold]{d.id}[/bold] '{d.title}': Risk Score = [red]{d.risk_score:.3f}[/red]")
        has_failure = True

    if has_failure:
        err_console.print("\n[bold red]CI CHECK FAILED: Architectural risk threshold exceeded.[/bold red]")
        raise typer.Exit(code=1)
    else:
        console.print("[bold green]✓ All assumptions valid and architectural decisions healthy.[/bold green]")


@app.command("export")
def export_cmd(
    format: str = typer.Option("markdown", "--format", "-f", help="Output format: markdown or json"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Target output file path"),
):
    """Export project graph to formatted Markdown or JSON."""
    store, engine = _get_project_context()
    engine.propagate_impact()

    if format.lower() == "json":
        edges = [
            DependencyEdge(
                source_id=u, target_id=v, weight=data["weight"], rationale=data.get("rationale", "")
            )
            for u, v, data in engine.graph.edges(data=True)
        ]
        from core.models import ProjectGraphData
        payload = ProjectGraphData(
            project_name=engine.project_name,
            assumptions=list(engine.assumptions.values()),
            decisions=list(engine.decisions.values()),
            dependencies=edges,
        )
        content = payload.model_dump_json(indent=2)
    else:
        lines = [
            f"# AssumptionPulse Report: {engine.project_name}",
            f"\n*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n",
            "## 1. Assumptions Ledger\n",
            "| ID | Statement | Category | Valid Until | Confidence | Status |",
            "|---|---|---|---|---|---|",
        ]
        for a in engine.assumptions.values():
            lines.append(f"| {a.id} | {a.statement} | {a.category} | {a.valid_until or 'N/A'} | {a.confidence:.2f} | {a.status.value} |")

        lines.extend([
            "\n## 2. Architectural Decisions & Downstream Risk\n",
            "| ID | Title | Criticality | Risk Score | Status |",
            "|---|---|---|---|---|",
        ])
        for d in sorted(engine.decisions.values(), key=lambda x: x.risk_score, reverse=True):
            lines.append(f"| {d.id} | {d.title} | {d.criticality:.2f} | {d.risk_score:.3f} | {d.status.value} |")

        lines.extend([
            "\n## 3. Dependency Mappings\n",
            "```text",
        ])
        for u, v, data in engine.graph.edges(data=True):
            rat = f" — {data['rationale']}" if data.get("rationale") else ""
            lines.append(f"{u} ---> {v} (weight: {data.get('weight', 1.0)}){rat}")
        lines.append("```\n")
        content = "\n".join(lines)

    if output:
        Path(output).write_text(content, encoding="utf-8")
        console.print(f"[green]✓[/green] Exported to [bold]{output}[/bold]")
    else:
        console.print(content)


@app.command("simulate")
def simulate_cmd(
    broken_assumption: str = typer.Option(..., "--break", help="Assumption ID to break"),
    replace_decision: str = typer.Option(..., "--replace", help="Decision ID to replace"),
    alt_title: str = typer.Option(..., "--alt-title", help="Title of alternative decision"),
    support_assumption: str = typer.Option(..., "--support", help="Supporting assumption ID"),
    dep_weight: float = typer.Option(0.75, "--dep-weight", help="Weight of dependency on supporting assumption"),
):
    """Simulate a what-if architecture replacement without altering production graph."""
    store, engine = _get_project_context()

    cand = Decision(
        id=f"{replace_decision}_ALT",
        title=alt_title,
        description=f"Alternative replacing {replace_decision}",
        criticality=0.85,
    )
    deps = [DependencyEdge(source_id=support_assumption, target_id=cand.id, weight=dep_weight)]

    blast_radius, remaining = engine.simulate_what_if(
        broken_assumption_id=broken_assumption,
        candidate_decision=cand,
        candidate_dependencies=deps,
        replaced_decision_id=replace_decision,
    )

    console.print(Panel(f"Simulation: Replacing [bold]{replace_decision}[/bold] with candidate alternative", title="What-If Analysis"))
    console.print(f"Simulated Blast Radius Score: [bold cyan]{blast_radius:.4f}[/bold cyan]")
    if remaining:
        console.print("\n[yellow]Remaining Decisions Still At Risk:[/yellow]")
        for d in remaining:
            console.print(f"  - [bold]{d.id}[/bold]: {d.title} (Risk: {d.risk_score:.3f})")
    else:
        console.print("\n[bold green]✓ Zero decisions remain at high risk with this alternative![/bold green]")


@app.command("load-demo")
def load_demo_cmd():
    """Load the reference FinPay Authentication scenario into the store."""
    store = ProjectStore(DEFAULT_DB)
    curr = Path.cwd()
    data_path = curr / "data" / "sample_scenario.json"
    if not data_path.exists():
        err_console.print(f"[red]Error:[/red] Could not find reference data at {data_path}")
        raise typer.Exit(code=1)

    engine = ADIEGraphEngine.from_json(str(data_path))
    engine.attach_storage(store)
    store.save_project(engine)
    console.print(f"[green]✓[/green] Loaded reference scenario '[bold]{engine.project_name}[/bold]' into store.")
    console.print("Run [cyan]ap status[/cyan] to inspect.")


@app.command("import-adr")
def import_adr_cmd(
    target_path: str = typer.Argument(..., help="Path to an ADR Markdown file or directory containing ADRs")
):
    """Import architecture decisions and premises from Markdown ADR files."""
    from core.parsers.markdown_adr import MarkdownADRParser
    store, engine = _get_project_context()

    p = Path(target_path)
    if not p.exists():
        err_console.print(f"[red]Error:[/red] Path '{target_path}' does not exist.")
        raise typer.Exit(code=1)

    parser = MarkdownADRParser()
    results = []
    if p.is_dir():
        results = parser.parse_directory(p)
    else:
        results = [parser.parse_file(p)]

    if not results:
        console.print("[yellow]No ADR files found or parsed.[/yellow]")
        return

    added_d = 0
    added_a = 0
    added_e = 0

    for res in results:
        # Add Decision
        if res.decision.id not in engine.decisions:
            engine.add_decision(res.decision)
            added_d += 1

        # Add Assumptions
        for a in res.assumptions:
            if a.id not in engine.assumptions:
                engine.add_assumption(a)
                added_a += 1

        # Add Dependencies
        for dep in res.dependencies:
            try:
                engine.add_dependency(dep)
                added_e += 1
            except ValueError:
                pass

    engine.propagate_impact()
    engine.auto_save()

    console.print(
        f"[green]✓[/green] Successfully imported from [bold]{target_path}[/bold]:\n"
        f"  • [bold]{added_d}[/bold] Decisions\n"
        f"  • [bold]{added_a}[/bold] Extracted Assumptions\n"
        f"  • [bold]{added_e}[/bold] Dependency Mappings"
    )
    console.print("Run [cyan]ap status[/cyan] to see your imported architecture graph.")


@app.command("notify")
def notify_cmd(
    webhook_url: Optional[str] = typer.Option(None, "--webhook-url", "-w", help="Slack or generic webhook endpoint"),
    channel: str = typer.Option("slack", "--channel", help="Notification channel: slack or generic"),
):
    """Dispatch Slack/webhook notification if any expired assumptions or at-risk decisions exist."""
    from core.notifications import NotificationService
    store, engine = _get_project_context()
    engine.propagate_impact()

    today = date.today()
    expired = [
        a for a in engine.assumptions.values()
        if a.valid_until and today > a.valid_until and a.status != NodeStatus.INVALID
    ]
    at_risk = [d for d in engine.decisions.values() if d.status == NodeStatus.AT_RISK]
    total_blast = round(sum(d.risk_score for d in engine.decisions.values() if d.status != NodeStatus.ARCHIVED), 3)

    if not expired and not at_risk:
        console.print("[green]✓[/green] Architecture healthy. No alerts need to be dispatched.")
        return

    url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
    if not url:
        err_console.print("[red]Error:[/red] No webhook URL provided. Pass --webhook-url or set SLACK_WEBHOOK_URL.")
        raise typer.Exit(code=1)

    if channel.lower() == "slack":
        ok = NotificationService.send_slack_alert(
            webhook_url=url,
            project_name=engine.project_name,
            expired_assumptions=expired,
            at_risk_decisions=at_risk,
            total_blast_radius=total_blast,
        )
    else:
        ok = NotificationService.send_generic_webhook(
            webhook_url=url,
            project_name=engine.project_name,
            expired_assumptions=expired,
            at_risk_decisions=at_risk,
            total_blast_radius=total_blast,
        )

    if ok:
        console.print(f"[green]✓ Alert successfully sent to {channel} webhook.[/green]")
    else:
        err_console.print(f"[red]Failed to send alert to {channel} webhook.[/red]")
        raise typer.Exit(code=1)


@app.command("attach-probe")
def attach_probe_cmd(
    assumption_id: str = typer.Argument(..., help="Assumption ID to attach live probe to"),
    probe_type: str = typer.Option(..., "--type", "-t", help="Probe type: http, tls, socket, or json_api"),
    url: Optional[str] = typer.Option(None, "--url", help="Target URL for http or json_api"),
    host: Optional[str] = typer.Option(None, "--host", help="Target hostname for socket or tls"),
    port: Optional[int] = typer.Option(None, "--port", help="Target port for socket or tls"),
    max_latency_ms: Optional[float] = typer.Option(None, "--max-latency", help="Maximum latency threshold in ms"),
    min_days: Optional[int] = typer.Option(None, "--min-days", help="Minimum remaining certificate days"),
    field_path: Optional[str] = typer.Option(None, "--field", help="JSON field path for json_api probe"),
    operator: Optional[str] = typer.Option("<=", "--operator", help="Comparison operator (<=, <, >=, >, ==)"),
    threshold: Optional[str] = typer.Option(None, "--threshold", help="Threshold value for json_api comparison"),
):
    """Attach a live network/operational probe to an assumption."""
    store, engine = _get_project_context()

    if assumption_id not in engine.assumptions:
        err_console.print(f"[red]Error:[/red] Assumption '{assumption_id}' not found.")
        raise typer.Exit(code=1)

    cfg = {}
    pt = probe_type.lower()
    if pt == "http":
        if not url:
            err_console.print("[red]Error:[/red] HTTP probe requires --url.")
            raise typer.Exit(code=1)
        cfg["url"] = url
        if max_latency_ms:
            cfg["max_latency_ms"] = max_latency_ms
    elif pt == "tls":
        if not host:
            err_console.print("[red]Error:[/red] TLS probe requires --host.")
            raise typer.Exit(code=1)
        cfg["host"] = host
        cfg["port"] = port or 443
        if min_days:
            cfg["min_days_remaining"] = min_days
    elif pt == "socket":
        if not port:
            err_console.print("[red]Error:[/red] Socket probe requires --port.")
            raise typer.Exit(code=1)
        cfg["host"] = host or "localhost"
        cfg["port"] = port
        if max_latency_ms:
            cfg["max_connect_time_ms"] = max_latency_ms
    elif pt == "json_api":
        if not url:
            err_console.print("[red]Error:[/red] json_api probe requires --url.")
            raise typer.Exit(code=1)
        cfg["url"] = url
        cfg["field_path"] = field_path
        cfg["operator"] = operator or "<="
        cfg["threshold"] = threshold
    else:
        err_console.print(f"[red]Error:[/red] Unknown probe type '{probe_type}'. Choose http, tls, socket, or json_api.")
        raise typer.Exit(code=1)

    a = engine.assumptions[assumption_id]
    a.probe_type = pt
    a.probe_config = cfg
    engine.auto_save()
    console.print(f"[green]✓ Attached live {pt.upper()} probe to [bold]{assumption_id}[/bold]: {cfg}[/green]")


@app.command("probe")
def run_probes_cmd(
    auto_trip: bool = typer.Option(True, "--auto-trip/--no-auto-trip", help="Automatically break assumption if probe fails"),
):
    """Execute live probes across reality, verify premises, and trip graph if reality violates assumptions."""
    from core.probes.registry import run_all_probes
    store, engine = _get_project_context()

    probed_assumptions = [a for a in engine.assumptions.values() if a.probe_type]
    if not probed_assumptions:
        console.print("[yellow]No live probes configured on any assumptions.[/yellow]")
        console.print("Attach one using: [cyan]ap attach-probe <ID> --type http --url <URL>[/cyan]")
        return

    console.print(f"\n🔍 [bold cyan]Executing {len(probed_assumptions)} live operational probes...[/bold cyan]\n")

    results = run_all_probes(engine, auto_trip=auto_trip)

    table = Table(title="Live Reality Probes vs Architectural Assumptions", header_style="bold cyan")
    table.add_column("ID", style="bold", width=6)
    table.add_column("Probe", width=10)
    table.add_column("Result", width=10)
    table.add_column("Measured vs Limit", width=22)
    table.add_column("Message", width=42)

    any_failed = False
    for r in results:
        status_str = "[bold green]PASS[/bold green]" if r["success"] else "[bold red]FAIL[/bold red]"
        if not r["success"]:
            any_failed = True
        measured = f"{r['measured_value']} (limit: {r['threshold']})" if r['threshold'] else str(r['measured_value'])
        table.add_row(
            r["assumption_id"],
            r["probe_type"].upper(),
            status_str,
            measured,
            r["message"][:40],
        )

    console.print(table)

    if any_failed:
        if auto_trip:
            console.print("\n[bold red]⚠️ Reality Violation Detected: Associated assumptions broken and risk propagated![/bold red]")
            engine.propagate_impact()
            at_risk = [d for d in engine.decisions.values() if d.status == NodeStatus.AT_RISK]
            if at_risk:
                console.print("[yellow]Downstream Decisions Now Compromised in Production:[/yellow]")
                for d in at_risk:
                    console.print(f"  - [bold]{d.id}[/bold]: {d.title} (Risk Score: {d.risk_score:.3f})")
        raise typer.Exit(code=1)
    else:
        console.print("\n[bold green]✓ All live operational probes passed. Reality conforms to architecture assumptions.[/bold green]")


