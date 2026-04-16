"""Tests for #488 — session-file existence gate on _resolve_resume().

The bug: claude-code stores sessions at /root/.claude/projects/<hash>/<id>.jsonl.
When a workspace container is recreated, the in-memory session_id from a prior
instance references a file that's gone — passing it as resume=<id> crashes the
CLI with "No conversation found with session ID" on every call.

The fix (in HermesA2AExecutor — wait, claude_sdk_executor): _resolve_resume()
gates self._session_id on glob-matching the session file in any of the known
locations. If no match, drop the id (set self._session_id = None) AND return
None so the SDK starts a fresh session.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

# claude_agent_sdk + a2a stubs live in tests/conftest.py so every test
# module shares one consistent stub set (see the conftest for why).
from molecule_runtime.claude_sdk_executor import ClaudeSDKExecutor


@pytest.fixture
def executor():
    """Build an executor with the minimum to exercise _resolve_resume()."""
    e = ClaudeSDKExecutor.__new__(ClaudeSDKExecutor)
    e._session_id = None
    return e


def test_resolve_resume_returns_none_when_no_session_id(executor):
    """Baseline: no session set → no resume, no glob calls (cheap path)."""
    executor._session_id = None
    with patch("molecule_runtime.claude_sdk_executor.glob.glob") as mock_glob:
        result = executor._resolve_resume()
    assert result is None
    mock_glob.assert_not_called()


def test_resolve_resume_keeps_id_when_session_file_exists(executor):
    """Session id matches a real file → keep the id, return it for resume."""
    sid = "abcd1234-fake-session-id"
    executor._session_id = sid
    with patch("molecule_runtime.claude_sdk_executor.glob.glob") as mock_glob:
        # First pattern matches; later patterns shouldn't be probed (short-circuit).
        mock_glob.side_effect = [[f"/root/.claude/projects/-app/{sid}.jsonl"], [], [], []]
        result = executor._resolve_resume()
    assert result == sid
    assert executor._session_id == sid  # not cleared
    # Only one glob call needed (early-exit on first match)
    assert mock_glob.call_count == 1


def test_resolve_resume_drops_id_when_session_file_missing(executor):
    """Stale session id (file gone) → drop in-memory + return None."""
    sid = "stale-session-from-prior-container"
    executor._session_id = sid
    with patch("molecule_runtime.claude_sdk_executor.glob.glob", return_value=[]):
        result = executor._resolve_resume()
    assert result is None
    assert executor._session_id is None  # cleared


def test_resolve_resume_probes_all_patterns_until_match(executor):
    """Late-pattern match is still found — agent-uid layout works alongside root."""
    sid = "found-only-in-agent-home"
    executor._session_id = sid
    call_log = []

    def fake_glob(pattern):
        call_log.append(pattern)
        # Match only the third pattern (/home/agent/.claude/projects/*/...)
        if pattern.startswith("/home/agent/.claude/projects"):
            return [f"/home/agent/.claude/projects/-app/{sid}.jsonl"]
        return []

    with patch("molecule_runtime.claude_sdk_executor.glob.glob", side_effect=fake_glob):
        result = executor._resolve_resume()

    assert result == sid
    assert executor._session_id == sid
    # First two patterns probed and missed, then third hit
    assert len(call_log) == 3


def test_resolve_resume_log_message_includes_session_id(executor, caplog):
    """When dropping a stale id, log message includes the id for operator triage."""
    import logging
    sid = "specific-id-for-log-check"
    executor._session_id = sid
    with patch("molecule_runtime.claude_sdk_executor.glob.glob", return_value=[]):
        with caplog.at_level(logging.INFO, logger="molecule_runtime.claude_sdk_executor"):
            executor._resolve_resume()
    # At least one log record mentions the dropped session id
    assert any(sid in r.message for r in caplog.records), \
        f"expected log message mentioning {sid}, got: {[r.message for r in caplog.records]}"


def test_resolve_resume_log_references_488(executor, caplog):
    """Log line references #488 so future debuggers find the issue history."""
    import logging
    executor._session_id = "any-stale-id"
    with patch("molecule_runtime.claude_sdk_executor.glob.glob", return_value=[]):
        with caplog.at_level(logging.INFO, logger="molecule_runtime.claude_sdk_executor"):
            executor._resolve_resume()
    assert any("#488" in r.message for r in caplog.records)
