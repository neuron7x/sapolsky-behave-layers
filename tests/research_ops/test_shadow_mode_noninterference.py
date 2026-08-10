from cwc.inference.shadow_observer import ShadowObserver, run_shadow_observed_generate_batch


class DeterministicEngine:
    def __init__(self):
        self.calls = 0

    def generate_batch(self, prompt_tokens, **kwargs):
        self.calls += 1
        seed = int(kwargs.get("seed", 0))
        return [list(prompt_tokens) + [seed, 17]]


def test_shadow_mode_on_off_produce_identical_base_generation():
    off_engine = DeterministicEngine()
    on_engine = DeterministicEngine()
    traces = []
    kwargs = {"seed": 123, "max_tokens": 2, "temperature": 0.0, "top_k": 1}
    off = run_shadow_observed_generate_batch(off_engine, [1, 2, 3], observer=None, run_id="off", **kwargs)
    observer = ShadowObserver(sink=traces.append)
    on = run_shadow_observed_generate_batch(on_engine, [1, 2, 3], observer=observer, run_id="on", **kwargs)
    assert on == off
    assert off_engine.calls == on_engine.calls == 1
    assert len(traces) == 1


def test_observer_failure_cannot_mutate_or_fail_base_generation():
    class SinkFailure(RuntimeError):
        pass

    def failing_sink(_):
        raise SinkFailure("sidecar failure")

    engine = DeterministicEngine()
    observer = ShadowObserver(sink=failing_sink)
    result = run_shadow_observed_generate_batch(engine, [5, 6], observer=observer, run_id="failure", seed=9)
    assert result == [[5, 6, 9, 17]]
    assert engine.calls == 1
