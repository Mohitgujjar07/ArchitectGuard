import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import matplotlib.pyplot as plt
import networkx as nx
import streamlit as st

from core.graph_engine import ADIEGraphEngine
from core.models import Assumption, Decision, DependencyEdge, NodeStatus
from core.storage import ProjectStore
from core.validator import HybridAssumptionValidator

DATA_PATH = ROOT_DIR / "data" / "sample_scenario.json"
STORE_PATH = ROOT_DIR / ".architectguard" / "store.db"
LEGACY_STORE_PATH = ROOT_DIR / ".assumptionpulse" / "store.db"

st.set_page_config(page_title="ArchitectGuard | Architecture Watchdog", layout="wide")


@st.cache_resource
def load_validator() -> HybridAssumptionValidator:
    return HybridAssumptionValidator()


def init_engine() -> ADIEGraphEngine:
    if "engine" not in st.session_state:
        target_store = STORE_PATH if STORE_PATH.exists() else (
            LEGACY_STORE_PATH if LEGACY_STORE_PATH.exists() else STORE_PATH
        )
        store = ProjectStore(str(target_store))
        projects = store.list_projects()
        if projects:
            data = store.load_project_data(projects[0]["name"])
            engine = ADIEGraphEngine.from_project_data(data)
            engine.attach_storage(store)
        elif DATA_PATH.exists():
            engine = ADIEGraphEngine.from_json(str(DATA_PATH))
            engine.attach_storage(store)
            store.save_project(engine)
        else:
            engine = ADIEGraphEngine("Default Architecture")
            engine.attach_storage(store)
        st.session_state.engine = engine
    return st.session_state.engine


def render_graph(engine: ADIEGraphEngine):
    fig, ax = plt.subplots(figsize=(10, 5.5))
    fig.patch.set_facecolor("#0E1117")
    ax.set_facecolor("#0E1117")

    if len(engine.graph.nodes) == 0:
        ax.text(
            0.5, 0.5, "Empty graph. Add assumptions and decisions to visualize.",
            color="#94a3b8", ha="center", va="center"
        )
        ax.axis("off")
        st.pyplot(fig)
        plt.close(fig)
        return

    pos = nx.spring_layout(engine.graph, seed=42, k=1.4)

    node_colors = []
    labels = {}
    for node_id in engine.graph.nodes():
        if node_id in engine.assumptions:
            a = engine.assumptions[node_id]
            labels[node_id] = f"{node_id}\n(conf: {a.confidence:.2f})"
            node_colors.append("#ef4444" if a.status == NodeStatus.INVALID else "#3b82f6")
        elif node_id in engine.decisions:
            d = engine.decisions[node_id]
            labels[node_id] = f"{node_id}\n(risk: {d.risk_score:.2f})"
            if d.status == NodeStatus.ARCHIVED:
                node_colors.append("#64748b")
            elif d.status == NodeStatus.AT_RISK:
                node_colors.append("#f97316")
            else:
                node_colors.append("#22c55e")
        else:
            labels[node_id] = node_id
            node_colors.append("#94a3b8")

    nx.draw_networkx_nodes(
        engine.graph,
        pos,
        node_color=node_colors,
        edgecolors="#F8FAFC",
        linewidths=1.2,
        node_size=1850,
        alpha=0.95,
        ax=ax,
    )
    nx.draw_networkx_labels(
        engine.graph,
        pos,
        labels=labels,
        font_size=8.5,
        font_weight="bold",
        font_color="#FFFFFF",
        ax=ax,
    )
    nx.draw_networkx_edges(
        engine.graph,
        pos,
        edge_color="#94a3b8",
        arrows=True,
        arrowstyle="-|>",
        arrowsize=18,
        width=1.6,
        ax=ax,
    )
    edge_labels = {(u, v): f"w={d['weight']}" for u, v, d in engine.graph.edges(data=True)}
    nx.draw_networkx_edge_labels(
        engine.graph,
        pos,
        edge_labels=edge_labels,
        font_size=7.5,
        font_color="#E2E8F0",
        bbox=dict(boxstyle="round,pad=0.18", facecolor="#161B22", edgecolor="#334155", alpha=0.9),
        ax=ax,
    )

    ax.set_title(
        "Blue = Valid Assumption | Red = Broken Assumption | Green = Safe Decision | Orange = At-Risk Decision",
        fontsize=9,
        color="#CBD5E1",
        pad=10,
    )
    ax.axis("off")
    st.pyplot(fig)
    plt.close(fig)


engine = init_engine()
validator = load_validator()

st.sidebar.title("ArchitectGuard 🛡️")
st.sidebar.caption("Architecture Decision Watchdog & Drift Monitor")
if st.sidebar.button("Reload Reference Scenario"):
    if DATA_PATH.exists():
        st.session_state.engine = ADIEGraphEngine.from_json(str(DATA_PATH))
        store = ProjectStore(str(STORE_PATH))
        st.session_state.engine.attach_storage(store)
        store.save_project(st.session_state.engine)
        st.rerun()

total_risk = round(sum(d.risk_score for d in engine.decisions.values() if d.status != NodeStatus.ARCHIVED), 3)
at_risk_count = sum(1 for d in engine.decisions.values() if d.status == NodeStatus.AT_RISK)
invalid_count = sum(1 for a in engine.assumptions.values() if a.status == NodeStatus.INVALID)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Assumptions", len(engine.assumptions))
col2.metric("Broken / Expired", invalid_count)
col3.metric("At-Risk Decisions", f"{at_risk_count} / {len(engine.decisions)}")
col4.metric("System Blast Radius", total_risk)

tab1, tab2, tab3, tab4 = st.tabs([
    "1. Dependency Graph & Impact",
    "2. Hybrid Fact & Expiry Monitor",
    "3. What-If Decision Simulator",
    "4. Extend Graph Manually",
])

with tab1:
    st.subheader(engine.project_name)
    left, right = st.columns([1.4, 1])
    with left:
        render_graph(engine)
    with right:
        if engine.assumptions:
            st.markdown("### Manual Assumption Stress-Test")
            selected_a = st.selectbox(
                "Select Assumption to Adjust",
                options=list(engine.assumptions.keys()),
                format_func=lambda k: f"{k}: {engine.assumptions[k].statement[:45]}...",
            )
            new_conf = st.slider(
                "Set Assumption Confidence (0.0 = Broken)",
                min_value=0.0,
                max_value=1.0,
                value=float(engine.assumptions[selected_a].confidence),
                step=0.05,
            )
            if st.button("Propagate Impact Across Graph"):
                impacted = engine.invalidate_assumption(selected_a, new_conf)
                st.rerun()

            st.markdown("### Downstream Impact Ranking")
            for d in sorted(engine.decisions.values(), key=lambda x: x.risk_score, reverse=True):
                badge = "🔴 AT RISK" if d.status == NodeStatus.AT_RISK else ("⚪ ARCHIVED" if d.status == NodeStatus.ARCHIVED else "🟢 VALID")
                st.write(f"**{d.id} — {d.title}** | {badge} | Risk: `{d.risk_score:.3f}`")
                if d.status == NodeStatus.AT_RISK:
                    for a_id, a_obj in engine.assumptions.items():
                        if a_obj.status == NodeStatus.INVALID:
                            paths = engine.get_impact_paths(a_id, d.id)
                            for p in paths:
                                st.caption(f"Causal chain: {' ➔ '.join(p)}")
        else:
            st.info("No assumptions in current project. Use Tab 4 to add some.")

with tab2:
    st.subheader("Neuro-Symbolic Drift & Temporal Audit")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### Inject Real-World Observation")
        fact_input = st.text_input(
            "Enter new fact or vendor update:",
            value="Vendor increased SMS OTP rate to 0.85 INR per message",
        )
        if st.button("Analyze & Auto-Propagate"):
            alerts = validator.evaluate_incoming_fact(engine, fact_input, auto_propagate=True)
            if not alerts:
                st.info("No contradictions or numeric drift detected against current assumptions.")
            else:
                for alert in alerts:
                    st.error(f"[{alert.trigger_type}] {alert.assumption_id}: {alert.details}")
                st.rerun()

    with col_b:
        st.markdown("#### Temporal Expiry Audit")
        if st.button("Run Expiry Date Check"):
            exp_alerts = validator.check_temporal_validity(engine)
            if not exp_alerts:
                st.success("All assumptions are within their valid date windows.")
            for ea in exp_alerts:
                engine.invalidate_assumption(ea.assumption_id, ea.recommended_confidence)
                st.warning(f"[EXPIRED] {ea.assumption_id}: {ea.details}")
            if exp_alerts:
                st.rerun()

    st.markdown("### Current Assumption Ledger")
    st.table([
        {
            "ID": a.id,
            "Statement": a.statement,
            "Category": a.category,
            "Valid Until": str(a.valid_until or "None"),
            "Confidence": a.confidence,
            "Status": a.status.value,
        }
        for a in engine.assumptions.values()
    ])

with tab3:
    st.subheader("Counterfactual 'What-If' Decision Evaluator")
    st.write("Simulate replacing an at-risk decision with a candidate alternative when a core assumption fails.")

    if engine.assumptions and engine.decisions:
        broken_a = st.selectbox("Target Broken Assumption:", list(engine.assumptions.keys()), key="sim_a")
        target_d = st.selectbox("Decision to Replace:", list(engine.decisions.keys()), key="sim_d")
        alt_title = st.text_input("Alternative Decision Title:", value="Switch Primary Login to Email OTP + 30-Day Session Token")
        support_a = st.selectbox("Supporting Assumption for Alternative:", list(engine.assumptions.keys()), index=min(1, len(engine.assumptions)-1), key="sim_sup")
        dep_weight = st.slider("Dependency Strength on Supporting Assumption", 0.1, 1.0, 0.75)

        if st.button("Run Counterfactual Simulation"):
            cand = Decision(id="D_ALT", title=alt_title, description="Simulated replacement", criticality=0.85)
            deps = [DependencyEdge(source_id=support_a, target_id="D_ALT", weight=dep_weight)]
            blast_score, remaining_risks = engine.simulate_what_if(
                broken_assumption_id=broken_a,
                candidate_decision=cand,
                candidate_dependencies=deps,
                replaced_decision_id=target_d,
            )
            st.success(f"Simulated Total Blast Radius with '{alt_title}': **{blast_score:.3f}** (vs current `{total_risk}`)")
            if remaining_risks:
                st.warning("Remaining Decisions Still At Risk:")
                for r in remaining_risks:
                    st.write(f"- **{r.id} ({r.title})**: Risk = `{r.risk_score:.3f}`")
            else:
                st.write("Zero decisions remain at high risk!")
    else:
        st.info("Add both assumptions and decisions to unlock what-if simulations.")

with tab4:
    st.subheader("Extend Graph Manually")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Add Assumption")
        a_id = st.text_input("Assumption ID", value="A5")
        a_stmt = st.text_input("Assumption Statement", value="Server hosting stays below 2000 INR/month")
        if st.button("Add Assumption"):
            engine.add_assumption(Assumption(id=a_id, statement=a_stmt))
            st.success(f"Added {a_id}")
            st.rerun()
    with c2:
        st.markdown("#### Link Dependency Edge")
        if engine.graph.nodes() and engine.decisions:
            src = st.selectbox("Parent Node", list(engine.graph.nodes()), key="edge_src")
            dst = st.selectbox("Child Decision", list(engine.decisions.keys()), key="edge_dst")
            w = st.slider("Edge Weight", 0.1, 1.0, 0.8, key="edge_w")
            if st.button("Add Dependency"):
                try:
                    engine.add_dependency(DependencyEdge(source_id=src, target_id=dst, weight=w))
                    engine.propagate_impact()
                    st.success(f"Linked {src} -> {dst}")
                    st.rerun()
                except ValueError as err:
                    st.error(str(err))
        else:
            st.caption("Add at least one assumption and one decision first.")
