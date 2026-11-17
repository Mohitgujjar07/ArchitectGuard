import pytest
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


def test_cli_init_and_status(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    # Init
    result = runner.invoke(app, ["init", "Test Architecture"])
    assert result.exit_code == 0
    assert "Initialized AssumptionPulse project" in result.stdout

    # Status on empty project
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "Test Architecture" in result.stdout


def test_cli_add_and_link(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "Payment Flow"])

    # Add assumption
    res_a = runner.invoke(app, ["add", "assumption", "A1", "Stripe API uptime > 99.9%"])
    assert res_a.exit_code == 0
    assert "Added assumption A1" in res_a.stdout

    # Add decision
    res_d = runner.invoke(app, ["add", "decision", "D1", "Use Stripe Checkout", "Zero payment logic"])
    assert res_d.exit_code == 0
    assert "Added decision D1" in res_d.stdout

    # Link
    res_l = runner.invoke(app, ["link", "A1", "D1", "--weight", "0.9"])
    assert res_l.exit_code == 0
    assert "Linked A1 -> D1" in res_l.stdout

    # Status check
    res_s = runner.invoke(app, ["status"])
    assert res_s.exit_code == 0
    assert "Stripe API uptime" in res_s.stdout
    assert "Use Stripe Checkout" in res_s.stdout


def test_cli_check_command(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "CI Test Project"])

    # Add valid assumption
    runner.invoke(app, ["add", "assumption", "A1", "Valid premise until 2099", "--valid-until", "2099-01-01"])

    # ap check should pass
    res = runner.invoke(app, ["check"])
    assert res.exit_code == 0
    assert "All assumptions valid" in res.stdout

    # Add an already expired assumption
    runner.invoke(app, ["add", "assumption", "A2", "Expired premise in 2020", "--valid-until", "2020-01-01"])

    # ap check should now fail with exit code 1
    res_fail = runner.invoke(app, ["check", "--fail-on-expired"])
    assert res_fail.exit_code == 1
    assert "Expired Assumption" in res_fail.stdout


def test_cli_export(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "Export Project"])
    runner.invoke(app, ["add", "assumption", "A1", "Database stays small"])
    runner.invoke(app, ["add", "decision", "D1", "Single SQLite DB", "Simple deployment"])

    # Export markdown
    res_md = runner.invoke(app, ["export", "--format", "markdown"])
    assert res_md.exit_code == 0
    assert "# AssumptionPulse Report: Export Project" in res_md.stdout

    # Export json
    res_json = runner.invoke(app, ["export", "--format", "json"])
    assert res_json.exit_code == 0
    assert '"project_name": "Export Project"' in res_json.stdout
