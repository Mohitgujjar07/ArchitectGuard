import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from core.models import ProjectGraphData

logger = get_logger("storage")


class ProjectStore:
    """SQLite persistence layer for ArchitectGuard project graphs."""

    def __init__(self, db_path: str = ".architectguard/store.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        try:
            with self._get_connection() as conn:
                conn.execute("PRAGMA foreign_keys = ON;")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS projects (
                        name TEXT PRIMARY KEY,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS graph_data (
                        project_name TEXT PRIMARY KEY,
                        data_json TEXT NOT NULL,
                        FOREIGN KEY (project_name) REFERENCES projects (name) ON DELETE CASCADE
                    )
                    """
                )
                conn.commit()
            logger.debug(f"Initialized SQLite store at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database at {self.db_path}: {e}")
            raise

    def save_project(self, engine: Any) -> None:
        """Serialize an ADIEGraphEngine instance and persist to SQLite."""
        try:
            data = ProjectGraphData(
                project_name=engine.project_name,
                assumptions=list(engine.assumptions.values()),
                decisions=list(engine.decisions.values()),
                dependencies=[
                    engine.models_dependency(u, v, d) if hasattr(engine, 'models_dependency')
                    else engine.get_edge_model(u, v, d)
                    for u, v, d in engine.graph.edges(data=True)
                ] if hasattr(engine, 'get_edge_model') else [
                    from_edge_data(u, v, d) for u, v, d in engine.graph.edges(data=True)
                ]
            )
            now = datetime.now().isoformat()
            data_json = data.model_dump_json(indent=2)

            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO projects (name, created_at, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET updated_at = excluded.updated_at
                    """,
                    (engine.project_name, now, now),
                )
                conn.execute(
                    """
                    INSERT INTO graph_data (project_name, data_json)
                    VALUES (?, ?)
                    ON CONFLICT(project_name) DO UPDATE SET data_json = excluded.data_json
                    """,
                    (engine.project_name, data_json),
                )
                conn.commit()
            logger.debug(f"Saved project '{engine.project_name}' to {self.db_path}")
        except Exception as e:
            logger.error(f"Error saving project '{getattr(engine, 'project_name', 'unknown')}': {e}")
            raise

    def load_project_data(self, project_name: str) -> ProjectGraphData:
        """Load and return raw ProjectGraphData for a given project."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT data_json FROM graph_data WHERE project_name = ?",
                (project_name,),
            )
            row = cursor.fetchone()
            if not row:
                raise KeyError(f"Project '{project_name}' not found in store.")
            raw = json.loads(row["data_json"])
            return ProjectGraphData(**raw)

    def list_projects(self) -> List[Dict[str, str]]:
        """List all stored projects with metadata."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT name, created_at, updated_at FROM projects ORDER BY updated_at DESC"
            )
            return [dict(row) for row in cursor.fetchall()]

    def project_exists(self, project_name: str) -> bool:
        """Check if project exists in store."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM projects WHERE name = ?", (project_name,)
            )
            return cursor.fetchone() is not None

    def delete_project(self, project_name: str) -> bool:
        """Delete project and associated graph data."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM projects WHERE name = ?", (project_name,)
            )
            conn.commit()
            return cursor.rowcount > 0


def from_edge_data(u: str, v: str, data: dict):
    from core.models import DependencyEdge
    return DependencyEdge(
        source_id=u,
        target_id=v,
        weight=data.get("weight", 1.0),
        rationale=data.get("rationale", "")
    )
