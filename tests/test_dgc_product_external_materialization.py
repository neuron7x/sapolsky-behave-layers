from __future__ import annotations

import pytest

from cwc.governance.external_materialization import canonical_sha256, parse_terminal_dataset_manifest


def test_terminal_manifest_parses_and_hashes_deterministically():
    text = '''
[dataset]
name="terminal-bench/test"
[[tasks]]
name="b"
digest="sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
[[tasks]]
name="a"
digest="sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
'''
    got = parse_terminal_dataset_manifest(text, expected_count=2)
    assert got.task_count == 2
    assert got.tasks[0][0] == "a"
    assert got.canonical_task_digest == canonical_sha256(got.tasks)


def test_terminal_manifest_rejects_count_mismatch():
    text = '''[dataset]\nname="x"\n[[tasks]]\nname="a"\ndigest="sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"\n'''
    with pytest.raises(ValueError, match="count mismatch"):
        parse_terminal_dataset_manifest(text, expected_count=2)


def test_terminal_manifest_rejects_duplicate_names():
    text = '''[dataset]\nname="x"\n[[tasks]]\nname="a"\ndigest="sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"\n[[tasks]]\nname="a"\ndigest="sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"\n'''
    with pytest.raises(ValueError, match="unique"):
        parse_terminal_dataset_manifest(text, expected_count=2)


def test_terminal_manifest_rejects_non_sha_digest():
    text = '''[dataset]\nname="x"\n[[tasks]]\nname="a"\ndigest="md5:deadbeef"\n'''
    with pytest.raises(ValueError, match="invalid terminal task digest"):
        parse_terminal_dataset_manifest(text, expected_count=1)
