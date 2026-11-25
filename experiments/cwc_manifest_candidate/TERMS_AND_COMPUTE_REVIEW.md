# Q2b-CANDIDATE-01 — source terms and compute observations

Status: SUPPORTING_EVIDENCE_ONLY / SOURCE_NOT_ADMITTED / MODEL_NOT_SELECTED / REAL_TRANSFER_01_NOT_TESTED.

This review supports the protocol frozen at `b0f24b1da0723bbfa6ff1af66af1d55a14ceeddb`, on canonical main `3f894bb77ff91b37438fa143a3022c318a73769d` after PR #93. It records inspected source notices and current executor observations. It supplies no owner declaration, legal clearance, source admission, model selection, model output, or Q2b completion credit. All source observations below use the existing frozen inputs.

## 1. Pinned source notices actually inspected

| Source and immutable ref | Inspected notice | Observed identity and consequence |
|---|---|---|
| AVeriTeC `7c62d1ec8df3fb560d6efe2b85fa191135636f81` | [README.md](https://github.com/MichSchli/AVeriTeC/blob/7c62d1ec8df3fb560d6efe2b85fa191135636f81/README.md), License section | Git blob `90f013e1c0580ae2b9a0883358132054f73a7c5d`, 4,771 bytes. Explicit CC BY-NC 4.0 link, consistent with the [official FEVER dataset page](https://fever.ai/dataset/averitec.html). Credit Schlichtkrull, Guo and Vlachos (2023). The inspected root roster has no separate LICENSE file. |
| HybridQA `db22fda8c5951438fade3c69d75b350335ba93b3` | [LICENSE](https://github.com/wenhuchen/HybridQA/blob/db22fda8c5951438fade3c69d75b350335ba93b3/LICENSE) | Git blob `6cce7fb48f73fe3e9cf469ebefa2d29293c6f056`, 1,067 bytes. MIT, copyright 2020 Wenhu Chen. This repository notice does not establish unrestricted rights to incorporated third-party material. |
| Same HybridQA ref | [README.md](https://github.com/wenhuchen/HybridQA/blob/db22fda8c5951438fade3c69d75b350335ba93b3/README.md) and [authors' dataset page](https://hybridqa.github.io/about.html) | README Git blob `d8b372aa7643698c988aec3f23e70ca5af8a5fa1`, 9,080 bytes; no license/Creative Commons lines. The authors' page separately declares CC BY 4.0 for the dataset. Credit Chen et al. (2020). The current web declaration is not a fabricated license file in the pinned snapshot. |
| WikiTables-WithLinks `f4ed68e54e25c495f63d309de0b89c0f97b3c508` | [README.md](https://github.com/wenhuchen/WikiTables-WithLinks/blob/f4ed68e54e25c495f63d309de0b89c0f97b3c508/README.md), read from the actual pinned ZIP | Git blob `a8a4b62e4416d28a1e4f5046a137eb864f728a17`, 1,132 bytes; SHA256 `a29dbbea518ddc9e6840464e6fa6e12a93237d65ebc39f956a517db31bf1c9bf`. Identifies crawled Wikipedia tables/passages and upstream links; contains no license/copyright wording. |

The actual WikiTables ZIP was revalidated at 193,533,209 bytes and SHA256 `8f8f708f485e38a6114cf7d246e6ac00eb6f7705a9e5b740ab2ef499b864da43`. Its 30,641-member roster contains exactly four root regular files: README.md, intro.png, orig_id_to_uid.json and utils.py. There is no root LICENSE, NOTICE, COPYING or copyright file. Missing notices do not imply absence of copyright or unrestricted permission.

The 563 selected table members were independently read and matched to the qualified #93 custody member hashes. Each has the same eight top-level fields: url, title, header, data, section_title, section_text, uid and intro. None has a dedicated license/notice/revision/timestamp field. This describes the available metadata; it does not claim that the textual payload contains no possible notice. The archive alone cannot authenticate each article's historical revision or imported-content notices.

## 2. Use-sensitive terms review

[Creative Commons' FAQ](https://creativecommons.org/faq/) distinguishes nonpublic use from public sharing. For CC 4.0 data, an applicable NC restriction can constrain private copying or extraction. BY/ND/SA conditions generally concern regulated uses involving public sharing. Personal use without sharing the material or adaptations does not itself require attribution. The NC assessment turns on the actual primary purpose, not the user's occupation, nonprofit status, repository name or a research label. Private use is not automatically noncommercial. These distinctions support preparing an attribution record without inventing universal per-article clearance or signature requirements. They do not establish that every possible use is permitted.

The [CC BY-NC 4.0 legal code](https://creativecommons.org/licenses/by-nc/4.0/legalcode.en), sections 1(i), 2(a) and 3(a), controls AVeriTeC use within its licensed scope. No commercial permission or copyright-exception conclusion is asserted here.

The [historical Wikimedia terms, oldid 98524](https://foundation.wikimedia.org/w/index.php?oldid=98524&title=Policy:Terms_of_Use), section 7, were actually retrieved and reviewed for the prior #92 handoff, which preserves that historical-source review. A fresh open during this candidate stage failed; no new successful HTTP retrieval is claimed. The reviewed text identifies CC BY-SA 3.0/GFDL defaults and exceptions. Article URLs can provide contributor attribution through history. Known applicable imported-source notices must be retained; a source-specific exception cannot be erased by a dataset's general declaration. The [CC BY-SA 3.0 legal code](https://creativecommons.org/licenses/by-sa/3.0/legalcode.en) separately describes reproduction and distribution conditions. No universal oldid requirement or blanket per-article permission gate follows from this review. The existing attribution roster remains governance metadata, prohibited from model input.

## 3. Exact unresolved factual question

The owner's authorization to implement and merge this stage is established. The narrow context lookup did not recover an explicit owner statement establishing the primary economic purpose of this particular AVeriTeC run. README's LOCAL_RESEARCH_ONLY describes deployment scope, not that missing fact. No declaration is inferred from generic hypothesis-testing language.

**Is this specific AVeriTeC evaluation primarily intended for noncommercial research, or for commercial advantage or monetary compensation?**

No signature or additional permission ritual is requested by this document. The answer permits a use-specific assessment; it does not automatically clear unrelated rights. Until that assessment and the original source-admission work are completed, `use_context=UNRESOLVED`, `data_terms=NOT_ADMITTED`, and all admission/authority flags remain false. The prospective candidate's null license slots are intentional admission interlocks; the publisher declarations above are known evidence, not unknown licenses.

## 4. Current executor observations

Read-only observations during this candidate stage on 2026-11-25 describe the remote execution environment, **not the owner's ASUS computer**. An additional local observation at `2026-11-25T16:55:18.986879+00:00` corroborated Python, CPU count and absent NVIDIA indicators. No model, tokenizer or GPU runtime was invoked.

| Observation | Result and limit |
|---|---|
| Interpreter / architecture | Python 3.12.14; Linux x86_64. |
| CPU reporting | `os.cpu_count()` = 9; `len(os.sched_getaffinity(0))` = 9. These are visible logical CPUs, not measured inference throughput. |
| Reported memory | MemTotal = 10,451,427,328 bytes. One reviewer snapshot reported MemAvailable = 9,737,662,464 bytes; availability fluctuates. SwapTotal and SwapFree = 0. |
| Disk reporting | Repository filesystem total = 20,957,446,144 bytes; one reviewer snapshot free = 18,465,284,096 bytes. Free space fluctuates. |
| Enforced resource quotas | `/proc/self/cgroup` = `0::/`; `/sys/fs/cgroup` absent. Effective cgroup CPU/RAM limits are UNKNOWN, not unlimited. |
| GPU evidence | `nvidia-smi` absent; no `/dev/nvidia*` entries in the additional observation. No GPU runtime query was executed. GPU hardware/access remains UNVERIFIED. |
| Existing runtime packages | `numpy` 2.3.5. Package metadata for torch, transformers, tokenizers, safetensors and llama-cpp-python was absent; llama-cli and ollama were not found. This is a setup observation, not a model-feasibility result. |

Reproduction uses `platform.python_version()`, `platform.machine()`, `os.cpu_count()`, `os.sched_getaffinity(0)`, `/proc/meminfo`, `/proc/self/cgroup`, the cgroup paths above, `shutil.disk_usage(repository_root)`, `shutil.which(...)` and `importlib.metadata.version(...)`. Missing files/packages are reported as missing rather than interpreted as unrestricted resources. Memory values from `/proc/meminfo` were converted from kB by multiplying by 1024.

## 5. CALIBRATION-only serialized input sizes

An independent implementation-side reviewer measured the following from the actual pinned inputs. Units are **UTF-8 bytes, not tokens**. No PRIMARY or REPLICATION input-size profiling, template rendering, tokenization, model selection or model execution was performed.

| Input projection | Cases | Minimum bytes | Upper median bytes | Maximum bytes | Total bytes |
|---|---:|---:|---:|---:|---:|
| AVeriTeC `case.model_input` | 99 | 236 | 792 | 14,684 | 109,296 |
| HybridQA `stage0_input()` | 64 | 1,256 | 9,079 | 72,506 | 1,122,023 |
| Same HybridQA cases, `post_query_input()` | 64 | 8,385 | 28,631 | 79,603 | 2,084,846 |

Reproduction method:

1. Run unchanged `source_intake.analyze` against actual pinned source bytes. Use `contract.split_averitec(records).calibration` and the reconstructed 64 HybridQA CALIBRATION hashes only.
2. Rejoin each HybridQA record by SHA256 of `question_id + '\n' + question + '\n' + table_id + '\n' + answer-text`; resolve its exact tables_tok/request_tok archive members and construct the case with unchanged `contract.make_hybridqa_case`.
3. For each projection above, measure `len(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))`. Output lengths and aggregates only; no source text, labels or gold answers.
4. Median is `sorted(lengths)[len(lengths)//2]`, the upper middle value for the 64-case groups.

The post-query projection is an offline serialization of permitted calibration material, not evidence that a live model queried or saw it. The measurements exclude real prompt/template overhead and cannot establish context-window fit, memory fit, latency, cost or expected task performance. All such conclusions remain UNKNOWN until an actual tokenizer, template, checkpoint, backend and execution budget are selected and bound under the original prerequisites.

## 6. Next dependency

Use the verified inert candidate and its current-tree evidence to prepare the later explicit admission transformation. Establish the actual use purpose, complete the context-applicable terms review, then commit and revalidate the canonical source manifest against its actual new tree. Genuine model/runtime material remains a separate subsequent dependency. This supporting review changes no frozen protocol, endpoint, cohort, comparator, negative result or authority boundary.
