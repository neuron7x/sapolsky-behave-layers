"""python -m pytest tests/test_instrumentation_config.py -v"""

from pathlib import Path

import pytest

from cwc.instrumentation.config import InstrumentationConfig, InstrumentationMode


def test_default_is_off():
    config = InstrumentationConfig()
    assert config.mode is InstrumentationMode.OFF
    assert config.is_off


def test_off_does_not_require_output_dir():
    config = InstrumentationConfig(mode=InstrumentationMode.OFF)
    assert config.output_dir is None


def test_counters_requires_output_dir():
    with pytest.raises(ValueError, match="requires a writable output_dir"):
        InstrumentationConfig(mode=InstrumentationMode.COUNTERS)


def test_counters_with_output_dir_is_valid(tmp_path: Path):
    config = InstrumentationConfig(mode=InstrumentationMode.COUNTERS, output_dir=tmp_path)
    assert config.output_dir == tmp_path


def test_trace_requires_trace_every_n_steps(tmp_path: Path):
    with pytest.raises(ValueError, match="TRACE mode requires trace_every_n_steps"):
        InstrumentationConfig(mode=InstrumentationMode.TRACE, output_dir=tmp_path)


def test_trace_with_interval_is_valid(tmp_path: Path):
    config = InstrumentationConfig(
        mode=InstrumentationMode.TRACE, output_dir=tmp_path, trace_every_n_steps=10
    )
    assert config.trace_every_n_steps == 10


@pytest.mark.parametrize(
    "kwargs",
    [
        {"sample_rate_hz": 0},
        {"sample_rate_hz": -1.0},
        {"trace_buffer_records": 0},
        {"event_pool_size": 0},
        {"warmup_steps": -1},
        {"measurement_steps": 0},
        {"energy_min_window_sec": 0},
    ],
)
def test_invalid_numeric_fields_rejected(kwargs):
    with pytest.raises(ValueError):
        InstrumentationConfig(**kwargs)


def test_output_dir_must_be_a_directory(tmp_path: Path):
    a_file = tmp_path / "not_a_dir"
    a_file.write_text("x")
    with pytest.raises(ValueError, match="not a directory"):
        InstrumentationConfig(mode=InstrumentationMode.COUNTERS, output_dir=a_file)


def test_unknown_field_fails_closed():
    with pytest.raises(TypeError):
        InstrumentationConfig(not_a_real_field=True)  # type: ignore[call-arg]


def test_config_is_frozen():
    config = InstrumentationConfig()
    with pytest.raises(AttributeError):
        config.mode = InstrumentationMode.COUNTERS  # type: ignore[misc]


def test_energy_requires_cuda(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("cwc.instrumentation.config._cuda_available", lambda: False)
    with pytest.raises(ValueError, match="energy cannot be enabled without CUDA"):
        InstrumentationConfig(enable_energy=True)
