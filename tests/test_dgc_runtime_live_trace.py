from __future__ import annotations

import pytest

from cwc.governance.provider_trace import ProviderUsageTrace, TraceAuthority


def _base(**overrides):
    values = {
        "trace_id": "trace-1",
        "decision_id": "task::DGC::0",
        "policy_id": "DGC",
        "authority": TraceAuthority.RUNTIME_LIVE,
        "provider": "openai",
        "model": "gpt-snapshot",
        "rate_card_digest": "a" * 64,
        "input_tokens": 100,
        "cached_input_tokens": 20,
        "cache_write_tokens": 0,
        "long_cache_write_tokens": 0,
        "output_tokens": 10,
        "runtime_call_id": "harbor-atif:session-1:aggregate",
        "source_artifact_digest": "b" * 64,
    }
    values.update(overrides)
    return ProviderUsageTrace(**values)


def test_runtime_live_requires_source_bound_runtime_identity():
    trace = _base()
    assert trace.authority is TraceAuthority.RUNTIME_LIVE
    assert trace.provider_request_id is None
    assert len(trace.digest) == 64


@pytest.mark.parametrize(
    "overrides",
    [
        {"runtime_call_id": None},
        {"source_artifact_digest": None},
        {"source_artifact_digest": "bad"},
    ],
)
def test_runtime_live_missing_source_identity_fails_closed(overrides):
    with pytest.raises(ValueError):
        _base(**overrides)


def test_runtime_live_digest_changes_with_source_artifact():
    first = _base(source_artifact_digest="b" * 64)
    second = _base(source_artifact_digest="c" * 64)
    assert first.digest != second.digest


def test_provider_live_still_requires_real_provider_request_id():
    with pytest.raises(ValueError, match="provider_request_id"):
        _base(
            authority=TraceAuthority.PROVIDER_LIVE,
            runtime_call_id=None,
            source_artifact_digest=None,
        )
