"""Exact historical evidence admission for the EXP05 engineering corpus.

A green integration audit certifies the frozen source and archived dispositions,
including negative ones. It grants no scientific or blind-cohort authority.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import itertools
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import zipfile

from scripts import cneh_promotion_gate as promotion

REPO = "neuron7x/sapolsky-behave-layers"
MAIN_BASE = "a2f9bc79c0e87f7316ba13441e83e5a05b52c95a"
INTEGRATION_PARENT = "8f923aac1747b8aa40d6d7577ba52dd92fa34961"
R0_HEAD = "60f76c2514ff21c23444fff08f6a7dc74bc691e4"
R1_HEAD = "ae9c3b28914773de16be825010f755508d08389e"
MANIFEST = "cdd4a4b03af103436346c78aeb928241cef95e4c660f0ecb3dbcd2601568376d"
# PR, experiment suffix, exact historical head, targeted run, conclusion.
LINEAGES = (
    (56, "a", "2a965db70fc80fefc7b1afaf581158eab7be53f2", 45331664726, "failure"),
    (57, "m", "589e53eab2c743a571b07d112af5733524fbc6a1", 45332121141, "success"),
    (58, "r", "8bf8900452b68b7c4f8790675e5a3a268ef3df2c", 45332488595, "success"),
    (61, "q", "1e81ef7a1c8027360077af91f37880aead06e0a3", 45340223643, "success"),
    (62, "s", "f851387421a59c2d4feb90385425f98b32e0f6e7", 45340614062, "success"),
    (63, "n", "4e33f71cd0b863ec150991830fa2aad53ee84ccc", 45341075614, "failure"),
    (64, "t", "68a4d9a9287401fdaa934732e490e9c4295edf75", 45342827067, "success"),
    (65, "d", "d226e5116f81b423c0678cac7838d52fbf96b110", 45343365851, "success"),
    (66, "v", "fcee15741f55aa8288a82662ee73d68fc4ac79d9", 45344209777, "success"),
    (67, "h", "7e2d8de6ef8ffd4864db96bf436dc00bec8176c1", 45345400854, "failure"),
    (68, "k", "70840944e12f0168868900f432fe61f1283fe61a", 45345321453, "success"),
    (69, "j", "4bd086660462cb148c5eab43af7a279e2d261d07", 45348096448, "success"),
    (70, "x", "2eaecb663ad053c77d833771b0893b9498b6c796", 45349858855, "failure"),
    (71, "y", R1_HEAD, 45356915631, "success"),
)
BY_SUFFIX = {x[1]: x for x in LINEAGES}
# label, experiment suffix (y0 is R0), artifact id, immutable outer SHA, data members.
ARCHIVES = (
    ("a_dual", "a", 14892441541, "18b50cbf3e17cfb4e00af1a7df4e57d49c9dbd6ad5cf4908446923029349a73d", ("report.json",)),
    ("a_info", "a", 14892800714, "0f7fa301261dc8dbb9089b4506bdb6ba0d2d994c461a074c9ea5465f9c2538bb", ("report.json",)),
    ("a_control", "a", 14892457206, "ffe2d9e627525ad775724714b0c559646d46037e232e15f6cc12d53312b4744b", ("report.json",)),
    ("a_fixed", "a", 14892082232, "0f59562c9ed0ffd7ef0c706f3adf9a98d51598d7ccbd098c6dbe89a2a9463cdb", ("report.json",)),
    ("m", "m", 14892153226, "e6eee7dcb187b72eacfb920d8054cef5cf8fc8f69880f258777ccd642eb9f333", ("report.json",)),
    ("r", "r", 14891899809, "0cd33d41eb7b0c2de85096f4d65bce30b9b7089b889d0e90ab8de07622cbfdf7", ("report.json.gz",)),
    ("q", "q", 14894699781, "763d34739ab03b45ce2a60986e220ce8b4f15ed8e96be80c474041eac390a4d5", ("report.json", "replay.json")),
    ("s", "s", 14895748442, "1da2f18464bd02ec5159312bda1ebfea32efbeb0f24070558d0c36385b2f9220", ("report.json",)),
    ("n", "n", 14896181291, "c3caa1cb704cc595b6e6be3aebdafcac1f6841c45ac44404a9dc082d226ac656", ("report.json",)),
    ("t", "t", 14896353416, "c5fa0c5dcd961fdd5845f9ea81b2d71e1cf0e9bc035372c00dd74f5b2feb9f50", ("report.json",)),
    ("t_admission", "t", 14896353288, "23ce99b3b0b7f2fcd16f93a0eca4b3c9cb36617d140389fe2785e1e3e50949cb", ("report.json", "attacks.json")),
    ("d", "d", 14896977776, "da12476c2e8d26fdf35d825d42e3a82fee42b6da504d764209e5b18723a112c6", ("report.json",)),
    ("v", "v", 14897018650, "f22afda8a548489d943f1f246575a64acbcb61c306b57cf71e6eb94e1f722725", ("report.json",)),
    ("h", "h", 14898206091, "55cdc7928aba9162c51247dc5e53791e70b5ab3dad59a34d13c3b975315ea3cd", ("report.json",)),
    ("k", "k", 14898085907, "ed08a3c64e158e70bd5b7dbf1f9872249802a53255fa47721e0141420c07a6cc", ("report.json", "replay.json")),
    ("j", "j", 14898972357, "d037a45361b04a7fa2a2b5d3c7995f8e0b95ab04cf931c3ddce6523397e88009", ("report.json",)),
    ("x", "x", 14900278518, "a7b06de29ff929f543d2ae3aebe57272bc55fdf405fe27ace51eec3be0d48b13", ("report.json",)),
    ("y0", "y0", 14902157446, "83d48aa600a45d42508f614b7e6cd8906fadcac8be2846693919d05971f43691", ("report.json",)),
    ("y", "y", 14904511434, "b6fec832e38e6aca61ffa35388cf3b45b32cf86a61000f719a49c966a0632266", ("report.json",)),
    ("y_transport", "y", 14904900502, "a9695ebefc3e0ed77c1e08caf34dde39a53613c3b99e15095e0c3c6fe175b4eb", ("report.json",)),
)
MAX_MEMBER = 16 * 1024 * 1024


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def archived_workflow(raw):
    """Remove only the automatic PR trigger; keep every execution step."""
    text = raw.decode("utf-8")
    start = text.index("on:\n")
    end = text.index("  workflow_dispatch: {}\n", start)
    need(text[start:end].startswith("on:\n  pull_request:\n"), "unexpected workflow trigger")
    return (text[:start] + "on:\n" + text[end:]).encode()


def source_audit(repo):
    head = git(repo, "rev-parse", "HEAD").decode().strip()
    for commit in (MAIN_BASE, INTEGRATION_PARENT, R0_HEAD):
        git(repo, "merge-base", "--is-ancestor", commit, head)
    git(repo, "diff", "--exit-code", MAIN_BASE, head, "--",
        "experiments/cneh_exp_01", "experiments/cneh_exp_04g", "experiments/cneh_exp_05",
        "scripts/cneh_promotion_gate.py", "scripts/cneh_history_guard.py", "scripts/truth_gate.py")
    receipts = []
    for pr, suffix, original, run, status in LINEAGES:
        git(repo, "merge-base", "--is-ancestor", original, head)
        root = f"experiments/cneh_exp_05{suffix}"
        all_tests = git(repo, "ls-tree", "-r", "--name-only", original, "--", "tests").decode().splitlines()
        tests = sorted(x for x in all_tests if Path(x).name.startswith(f"test_cneh_exp_05{suffix}"))
        current_tests = sorted(x for x in git(repo, "ls-files", "--", "tests").decode().splitlines()
                               if Path(x).name.startswith(f"test_cneh_exp_05{suffix}"))
        need(tests == current_tests, "frozen test roster changed: " + suffix)
        paths = [root, *tests]
        if suffix == "y":
            paths.extend(("scripts/cneh_artifact_transport.py", "tests/test_cneh_artifact_transport.py",
                          ".github/workflows/cneh-artifact-transport-audit.yml"))
        git(repo, "diff", "--exit-code", original, head, "--", *paths)
        git(repo, "diff", "--exit-code", head, "--", *paths)
        need(not git(repo, "ls-files", "--others", "--exclude-standard", "--", *paths), "untracked frozen input")
        workflow = f".github/workflows/cneh-exp-05{suffix}.yml"
        anchor = R1_HEAD if suffix in ("x", "y") else original
        expected = archived_workflow(git(repo, "show", anchor + ":" + workflow))
        need((repo / workflow).is_file() and not (repo / workflow).is_symlink()
             and (repo / workflow).read_bytes() == expected, "archived workflow body changed: " + workflow)
        receipts.append({"pr": pr, "experiment": suffix, "head": original, "run": run,
                         "original_conclusion": status, "source": "EXACT_ARCHIVED_BYTES",
                         "workflow_sha256": sha(expected)})
    need(git(repo, "rev-parse", "HEAD").decode().strip() == head, "head moved")
    return receipts


def read_archive(raw, expected, members):
    need(sha(raw) == expected, "external archive SHA256 mismatch")
    names = set(members) | {"SHA256SUMS"}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos = z.infolist()
        need(len(infos) == len(names) and {i.filename for i in infos} == names, "ZIP member roster")
        need(all(not i.is_dir() and i.file_size <= MAX_MEMBER
                 and stat.S_IFMT(i.external_attr >> 16) in (0, stat.S_IFREG) for i in infos), "invalid ZIP member")
        files = {i.filename: z.read(i) for i in infos}
    actual = {}
    for line in files["SHA256SUMS"].decode("ascii").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
        need(match is not None and match[2] not in actual, "invalid or duplicate manifest entry")
        actual[match[2]] = match[1]
    need(actual == {name: sha(files[name]) for name in members}, "inner manifest mismatch")
    reports = {}
    for name in members:
        if name.endswith(".gz"):
            with gzip.GzipFile(fileobj=io.BytesIO(files[name])) as f:
                decoded = f.read(MAX_MEMBER + 1)
            need(len(decoded) <= MAX_MEMBER, "decompressed report size")
        else:
            decoded = files[name]
        value = promotion.strict_json(decoded)
        need(type(value) is dict and value.get("scientific_promotion_authorized") is False,
             "missing explicit negative authority")
        promotion.reject_positive_claims(value)
        reports[name] = value
    if "replay.json" in files:
        need(files["replay.json"] == files["report.json"], "archived exact report replay mismatch")
    return reports, {name: sha(files[name]) for name in members}


def cpu_report(value, exact, head, run):
    need(value["head_sha"] == head and value["run_id"] == str(run)
         and value["manifest_sha256"] == MANIFEST and value["complete_evidence"] is True
         and value["complete_by_arch"] == {"aarch64": 1000, "x86_64": 1000}
         and value["paired_comparisons"] == 1000 and value["sentinel_repeat_pass"] is True
         and value["missing_or_invalid_shards"] == [] and value["blind_causal_cohort"] == "BLOCKED",
         "CPU complete scope")
    rows = value["reports"]
    need([r["id"] for r in rows] == list(range(1000)), "CPU episode roster")
    for r in rows:
        need(not r["failures"] and set(r["audits"]) == {"aarch64", "x86_64"}
             and all(v["status"] == "PASS" for v in r["audits"].values()), "CPU boundary audit")
        c = r["comparison"]
        need(c["numerical_close"] is True and c["exact"] is exact
             and c["event_tape_exact"] is exact and c["raw_samples_exact"] is exact
             and c["step_schedule_exact"] is exact, "CPU exact/numerical distinction")
        if exact:
            need(c["first_difference"] is None and c["max_event_time_error_ms"] == 0.
                 and all(x == 0. for x in c["max_full_errors"].values()), "CPU raw equality")
        else:
            need(c["first_difference"] is not None, "missing historical divergence")
    for arch in ("aarch64", "x86_64"):
        totals = value["counts_by_arch"][arch]
        need(totals["synaptic_stops"] == 216280
             and all(sum(r["audits"][arch][k] for r in rows) == v for k,v in totals.items()),
             "CPU counter reaggregation")
        repeats = value["sentinel_repeats"][arch]
        need([x["id"] for x in repeats] == [0,250,500,750] and all(x["status"] == "PASS" for x in repeats),
             "CPU sentinel roster")
    need(value["cross_cpu_deterministic_replay"] == ("PASS_FINITE_ONLY" if exact else "FAIL")
         and all(value[k] == (1000 if exact else 0) for k in
                 ("exact_pairs","exact_event_tapes","exact_raw_samples","exact_step_schedules")),
         "CPU verdict inflation")


def verify_semantics(reports, hashes):
    def get(label):
        files = reports[label]
        return files["report.json.gz"] if "report.json.gz" in files else files["report.json"]
    for label, suffix, _, _, _ in ARCHIVES:
        if label == "y_transport":
            continue
        expected = "CNEH-EXP-05" + ("Y" if suffix == "y0" else suffix.upper())
        for obj in reports[label].values():
            promotion.check_verdict(expected, obj)
    a = [get(x) for x in ("a_dual","a_info","a_control","a_fixed")]
    need([x["arm"] for x in a] == ["DUAL","INFO_ONLY","CONTROL_ONLY","FIXED_ALTERNATE"]
         and all(len(x["episodes"]) == 16 for x in a)
         and all(sorted(e["seed"] for e in x["episodes"]) == sorted(e["seed"] for e in a[0]["episodes"]) for x in a),
         "A arm/world roster")
    need(a[0]["aggregate_status"] == "BLOCKED_NO_SURVIVOR_AVERAGING"
         and a[0]["all_instrument_checks_passed"] is False
         and all(e["valid"] is False and e["unmodified_parent_replay"]["comparison"]["exact_match"] is False
                 for e in a[0]["episodes"])
         and all(x["all_instrument_checks_passed"] is True and all(e["valid"] is True for e in x["episodes"]) for x in a[1:]),
         "A historical failed shard erased")
    m = get("m")
    need(m["episodes"] == 80 and m["worlds"] == 16 and m["unique_arms"] == 4
         and len(m["per_world"]) == 80 and m["external_replication"] == "NOT_TESTED", "M scope")
    r = get("r")
    need(set(r["profiles"]) == {"A/BASELINE","A/DEFAULT","B/BASELINE","B/DEFAULT"}
         and all(len(v["archive_comparisons"]) == 10 and all(x["exact"] is False for x in v["archive_comparisons"])
                 for v in r["profiles"].values())
         and len(r["pairwise"]) == 6 and all(len(p["episodes"]) == 10 and all(e["exact"] is True for e in p["episodes"]) for p in r["pairwise"]),
         "R historical mismatch versus current agreement")
    q = get("q")
    need(q["historical_domain"] == "HISTORICAL_DOMAIN_UNRESOLVED" and q["historical_native_replay"] == "FAIL_PRESERVED"
         and q["replay_rerun_authorized"] is False and len(q["locked_wheel_roster"]) == 7
         and len(q["unestablished_execution_domain_fields"]) == 5, "Q unresolved provenance")
    s = get("s")
    need(s["total_equivalence_pair_checks"] == 7086987 and s["total_scenarios"] == 549
         and len(s["fixtures"]) == 8 and s["native_replay"] == s["physical_control"] == "NOT_TESTED", "S toy scope")
    n = get("n")
    need(n["native_panel_status"] == "FAIL_PANEL" and n["reports"] == 8
         and len(n["comparisons"]) == 8 and sum(x["first_difference"] is not None for x in n["comparisons"]) == 2,
         "N failed native panel")
    t, ta = get("t"), get("t_admission")
    witnesses = [x for x in t["results"] if x["status"] == "SEALED_TRANSITION_REPRODUCED"]
    need(len(witnesses) == t["reproduced_onsets"] == 6 and t["historical_native_panel"] == "FAIL_PRESERVED",
         "T causal witness roster")
    for x in witnesses:
        tests = {v["name"]: v["matches_baseline"] for v in x["substitutions"]}
        need(tests == {"NMDA_ONLY":False,"ADEX_ONLY":True,"BOTH":True}, "T local substitution")
    attacks = reports["t_admission"]["attacks.json"]
    need(ta["mismatched_ticks"] == 38 and ta["mismatched_episodes"] == 5 and len(ta["comparisons"]) == 28
         and len(attacks["rejected_attacks"]) == 14 and all(v is True for v in attacks["rejected_attacks"].values())
         and attacks["jointly_rehashed_reports"] == 8, "T structural admission")
    d = get("d")
    need(d["qualification"] == "PASS_PANEL_ONLY" and d["reports"] == 8 and d["full_states"] == 32832
         and d["fixture_count"] == 650 and all(x["difference"] is None for x in d["comparisons"]), "D finite panel")
    v = get("v")
    need(v["unique_raw_panels"] == 1 and v["fresh_seeds"] == 2 and v["unique_transitions"] == 4096
         and v["sealed_witness_transitions"] == 6 and v["independent_exp_evaluations"] == 275484
         and v["attacks"]["legacy_structural_false_acceptance"] is True and len(v["attacks"]["rejected"]) == 21,
         "V independent equations")
    h = get("h")
    need(h["continuous_time_numerical_gate"] == "FAIL" and h["reference_qualified"] == 8
         and h["native_qualified"] == h["finest_qualified"] == 0 and len(h["reports"]) == 8, "H fixed-step failure")
    k = get("k")
    need(k["blind_cohort_admission"] == "BLOCKED" and k["real_trust_roots"] == 0
         and k["contract_tests"]["status_assignments"] == 78125
         and len(k["contract_tests"]["attacks_rejected"]) == 17
         and all(v is True for v in k["contract_tests"]["attacks_rejected"].values()), "K no blind authority")
    j = get("j")
    need(j["qualification"] == "PASS_FINITE_ONLY" and j["qualified_episodes"] == 8
         and j["qualified_comparisons"] == j["independent_comparisons"] == 40
         and j["event_certificates"] == 736 and j["attacks_rejected"] == 80, "J finite event qualification")
    cpu_report(get("x"),False,BY_SUFFIX["x"][2],BY_SUFFIX["x"][3])
    cpu_report(get("y0"),True,R0_HEAD,45352843313)
    y = get("y")
    cpu_report(y,True,R1_HEAD,BY_SUFFIX["y"][3])
    need(y["arithmetic_lineage"] == "R1_MPFR_EMBEDDED_ERROR_DOT" and y["reference_qualified"] == 8
         and y["forensic_scope"] == "SEALED_CHUNK_REPRODUCED" and y["historical_cross_cpu_replay"] == "FAIL_PRESERVED",
         "Y R1 scope")
    for obj in (get("y0"), y):
        refs = obj["reference_reports"]
        need([x["index"] for x in refs] == list(range(8))
             and all(x["status"] == "PASS_FINITE" and len(x["comparisons"]) == 2
                     and all(c["status"] == "PASS_FINITE" and all(g is True for g in c["gates"].values())
                             for c in x["comparisons"]) for x in refs), "Y continuous references")
    for p in y["preflight"].values():
        e = p["arithmetic"]["embedded_error_reduction"]
        need(e["component_checks"] == 4364 and e["sealed_trial_records"] == 128
             and len(e["negative_controls"]) == 5 and all(v is True for v in e["negative_controls"].values())
             and p["fingerprint"]["build"]["forbidden_fma"] == 0 and p["fingerprint"]["build"]["mpfr_dot_import"] is True,
             "Y correct dot/native provenance")
    transport = get("y_transport")
    need(transport["head_sha"] == R1_HEAD and transport["run_id"] == str(BY_SUFFIX["y"][3])
         and transport["status"] == "PASS" and transport["upstream_ok"] is True
         and not any(transport[k] for k in ("missing","unexpected","malformed"))
         and len(transport["downloads"]) == 4 and all(x["exit_code"] == 0 for x in transport["downloads"])
         and y["transport_sha256"] == hashes["y_transport"]["report.json"], "Y strict transport")
    return {"archived_failed_campaigns": [56,63,67,70], "historical_replay": "FAIL_PRESERVED",
            "r1_exact_pairs": 1000, "r1_reference_episodes": 8, "r1_reference_comparisons": 16,
            "scientific_promotion": "BLOCKED", "scientific_promotion_authorized": False,
            "blind_causal_cohort": "BLOCKED"}


def api(path):
    return promotion.strict_json(subprocess.check_output(["gh", "api", path]))


def origin(suffix):
    if suffix == "y0":
        return R0_HEAD, 45352843313, "success"
    return BY_SUFFIX[suffix][2:]


def authenticate_run(value, head, run, status):
    need(value["id"] == run and value["head_sha"] == head and value["status"] == "completed"
         and value["conclusion"] == status and value["repository"]["full_name"] == REPO,
         "historical run identity/conclusion mismatch")


def authenticate_artifact(value, aid, digest, head, run):
    need(value["id"] == aid and value["digest"] == "sha256:" + digest and value["expired"] is False
         and value["workflow_run"]["id"] == run and value["workflow_run"]["head_sha"] == head,
         "historical artifact identity/digest mismatch")


def collect():
    reports, hashes, receipt = {}, {}, []
    for suffix in (*BY_SUFFIX, "y0"):
        head,run,status = origin(suffix)
        authenticate_run(api(f"repos/{REPO}/actions/runs/{run}"),head,run,status)
    with tempfile.TemporaryDirectory() as tmp:
        for label,suffix,aid,digest,members in ARCHIVES:
            head,run,_ = origin(suffix)
            authenticate_artifact(api(f"repos/{REPO}/actions/artifacts/{aid}"),aid,digest,head,run)
            path = Path(tmp)/f"{aid}.zip"
            subprocess.run(["curl","--fail","--silent","--show-error","--location",
                            "--header","Authorization: Bearer "+os.environ["GH_TOKEN"],
                            "--header","Accept: application/vnd.github+json",
                            f"https://api.github.com/repos/{REPO}/actions/artifacts/{aid}/zip",
                            "--output",str(path)],check=True)
            need(path.stat().st_size <= MAX_MEMBER, "archive size")
            reports[label],hashes[label]=read_archive(path.read_bytes(),digest,members)
            receipt.append({"label":label,"artifact":aid,"zip_sha256":digest,"head":head,
                            "run":run,"members_sha256":hashes[label]})
    return verify_semantics(reports,hashes),receipt


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo",type=Path,default=Path.cwd())
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    sources=source_audit(args.repo)
    result,archives=collect()
    output={"experiment":"CNEH-EXP-05-INTEGRATION","engineering_gate":"PASS_ARCHIVED_EVIDENCE_ONLY",
            "head_sha":git(args.repo,"rev-parse","HEAD").decode().strip(),"lineages":sources,"archives":archives,
            **result}
    promotion.check_verdict(output["experiment"],output)
    args.out.mkdir()
    raw=canonical(output)
    (args.out/"report.json").write_bytes(raw)
    (args.out/"SHA256SUMS").write_text(sha(raw)+"  report.json\n")
    print(canonical({k:v for k,v in output.items() if k not in ("lineages","archives")}).decode(),end="")


if __name__ == "__main__":
    main()
