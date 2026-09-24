from __future__ import annotations

import pytest

from cwc.governance.provider_trace import ProviderUsageTrace, TraceAuthority


def _trace(**overrides):
    payload = {
        "trace_id": "trace-1",
        "decision_id": "task::policy::0",
        "policy_id": "DGC",
        "authority": TraceAuthority.PROVIDER_LIVE,
        "provider": "openai",
        "model": "model",
        "rate_card_digest": "a" * 64,
        "input_tokens": 10,
        "cached_input_tokens": 0,
        "cache_write_tokens": 0,
        "long_cache_write_tokens": 0,
        "output_tokens": 5,
    }
    payload.update(overrides)
    return ProviderUsageTrace(**payload)


def test_live_trace_accepts_real_request_id():
    trace = _trace(provider_request_id="req_123")
    assert trace.provider_correlation_kind == "REQUEST_ID"
    assert trace.provider_correlation_id == "req_123"
    assert trace.provider_response_id is None


def test_live_trace_accepts_real_response_id():
    trace = _trace(provider_response_id="resp_123")
    assert trace.provider_correlation_kind == "RESPONSE_ID"
    assert trace.provider_correlation_id == "resp_123"
    assert trace.provider_request_id is None


def test_live_trace_rejects_missing_correlation_id():
    with pytest.raises(ValueError, match="provider_request_id or provider_response_id"):
        _trace()


def test_live_trace_rejects_both_correlation_id_types():
    with pytest.raises(ValueError, match="exactly one correlation"):
        _trace(provider_request_id="req_1", provider_response_id="resp_1")


@pytest.mark.parametrize(
    "field",
    ["provider_request_id", "provider_response_id"],
)
def test_blank_correlation_id_is_rejected(field: str):
    with pytest.raises(ValueError, match="non-empty string"):
        _trace(**{field: "   "})


def test_trace_digest_distinguishes_request_from_response_identity():
    request = _trace(provider_request_id="same-id")
    response = _trace(provider_response_id="same-id")
    assert request.digest != response.digest
