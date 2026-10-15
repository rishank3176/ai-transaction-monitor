from pathlib import Path


def test_dashboard_file_exists():
    """The Streamlit dashboard file should exist."""
    assert Path("frontend/app.py").is_file()


def test_dashboard_has_project_title():
    """The dashboard should display the project title."""
    content = Path("frontend/app.py").read_text(encoding="utf-8")
    assert "AI Transaction Monitor" in content


def test_dashboard_uses_streamlit():
    """The dashboard should use Streamlit."""
    content = Path("frontend/app.py").read_text(encoding="utf-8")
    assert "import streamlit as st" in content


def test_dashboard_uses_api_not_database_directly():
    """The dashboard should communicate through HTTP requests."""
    content = Path("frontend/app.py").read_text(encoding="utf-8")
    assert "requests.get" in content
    assert "requests.post" in content
    assert "data.db" not in content


def test_dashboard_has_supported_human_feedback_options():
    """The dashboard should offer the decisions supported by the API."""
    content = Path("frontend/app.py").read_text(encoding="utf-8")
    assert '"approve", "block"' in content
