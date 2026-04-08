"""
Test suite for Technical Video Intelligence Bot
Run: pytest tests/ -v --cov=backend
"""

import os
import json
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


# ── Health ──────────────────────────────────────────────────────────────────

def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── Job endpoints ────────────────────────────────────────────────────────────

def test_get_unknown_job_returns_404():
    resp = client.get("/jobs/nonexistent-id")
    assert resp.status_code == 404


def test_youtube_endpoint_creates_job():
    with patch("main.run_pipeline", new_callable=AsyncMock):
        resp = client.post("/process/youtube", json={"url": "https://youtube.com/watch?v=test"})
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "queued"


def test_upload_rejects_bad_extension():
    from io import BytesIO
    resp = client.post(
        "/process/upload",
        files={"file": ("malware.exe", BytesIO(b"fake"), "application/octet-stream")}
    )
    assert resp.status_code == 400


def test_upload_accepts_mp4():
    with patch("main.run_pipeline", new_callable=AsyncMock):
        from io import BytesIO
        resp = client.post(
            "/process/upload",
            files={"file": ("meeting.mp4", BytesIO(b"fake video content"), "video/mp4")}
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"


# ── OutputGenerator unit tests ───────────────────────────────────────────────

from agents.output_generator import OutputGenerator


SAMPLE_ANALYSIS = {
    "summary": "Team decided to migrate auth from JWT to PASETO.",
    "speakers": ["Alice", "Bob"],
    "decisions": [{
        "timestamp": "00:14:22",
        "title": "Migrate JWT to PASETO",
        "description": "Replace JWT tokens with PASETO for better security.",
        "rationale": "Eliminate algorithm confusion attacks.",
        "alternatives_rejected": ["Keep JWT", "Use opaque tokens"],
        "impact": "high"
    }],
    "constraints": [{
        "timestamp": "00:18:00",
        "type": "performance",
        "description": "Auth latency must stay under 50ms p99",
        "metric": "50ms p99"
    }],
    "magic_to_system": [{
        "timestamp": "00:31:08",
        "vague_statement": "We'll handle rate limiting magically",
        "concrete_resolution": "Redis sliding window at 1000 req/min per user",
        "component_affected": "api-gateway"
    }],
    "action_items": [{
        "timestamp": "00:45:00",
        "task": "Write schema migration script for PASETO",
        "owner": "alice",
        "deadline": "2026-04-15",
        "priority": "high",
        "jira_story_points": 5,
        "jira_issue_type": "Task",
        "jira_labels": ["auth", "security"],
        "jira_component": "auth-service"
    }],
    "concepts": ["PASETO", "JWT", "Redis", "rate-limiting"]
}

SAMPLE_METADATA = {
    "title": "Auth Service Migration Design Review",
    "duration_seconds": 3600,
    "source": "youtube"
}


def test_markdown_contains_title():
    gen = OutputGenerator()
    md = gen.to_markdown(SAMPLE_ANALYSIS, SAMPLE_METADATA)
    assert "Auth Service Migration" in md


def test_markdown_contains_decisions():
    gen = OutputGenerator()
    md = gen.to_markdown(SAMPLE_ANALYSIS, SAMPLE_METADATA)
    assert "PASETO" in md
    assert "00:14:22" in md


def test_markdown_contains_action_items():
    gen = OutputGenerator()
    md = gen.to_markdown(SAMPLE_ANALYSIS, SAMPLE_METADATA)
    assert "alice" in md
    assert "2026-04-15" in md


def test_markdown_contains_magic_section():
    gen = OutputGenerator()
    md = gen.to_markdown(SAMPLE_ANALYSIS, SAMPLE_METADATA)
    assert "Magic" in md
    assert "rate limiting" in md.lower()


def test_jira_json_structure():
    gen = OutputGenerator()
    jira = gen.to_jira_json(SAMPLE_ANALYSIS, SAMPLE_METADATA)
    assert "issues" in jira
    assert "bulk_payload" in jira
    assert isinstance(jira["issues"], list)
    assert len(jira["issues"]) >= 1


def test_jira_json_epic_created():
    gen = OutputGenerator()
    jira = gen.to_jira_json(SAMPLE_ANALYSIS, SAMPLE_METADATA)
    issue_types = [i["fields"]["issuetype"]["name"] for i in jira["issues"]]
    assert "Epic" in issue_types


def test_jira_json_task_has_required_fields():
    gen = OutputGenerator()
    jira = gen.to_jira_json(SAMPLE_ANALYSIS, SAMPLE_METADATA)
    tasks = [i for i in jira["issues"] if i["fields"]["issuetype"]["name"] == "Task"]
    assert len(tasks) >= 1
    task = tasks[0]
    assert "summary" in task["fields"]
    assert "description" in task["fields"]
    assert "priority" in task["fields"]


def test_jira_project_key_derived_from_title():
    gen = OutputGenerator()
    jira = gen.to_jira_json(SAMPLE_ANALYSIS, SAMPLE_METADATA)
    # "Auth Service Migration Design Review" → first chars of alpha words
    assert len(jira["project_key"]) <= 4
    assert jira["project_key"].isupper()


def test_empty_action_items_no_crash():
    gen = OutputGenerator()
    analysis_no_items = {**SAMPLE_ANALYSIS, "action_items": []}
    jira = gen.to_jira_json(analysis_no_items, SAMPLE_METADATA)
    assert jira["issues_count"] == 0


# ── TranscriptionAgent unit tests ────────────────────────────────────────────

from agents.transcriber import TranscriptionAgent


def test_seconds_to_hms():
    assert TranscriptionAgent._seconds_to_hms(0) == "00:00:00"
    assert TranscriptionAgent._seconds_to_hms(61) == "00:01:01"
    assert TranscriptionAgent._seconds_to_hms(3661) == "01:01:01"
    assert TranscriptionAgent._seconds_to_hms(7322) == "02:02:02"


def test_seconds_to_hms_fractional():
    # Should floor fractional seconds
    result = TranscriptionAgent._seconds_to_hms(90.7)
    assert result == "00:01:30"
