# Technical writing for CWC

State the result. Give the evidence. Name the limit that matters.

## Keep the meaning fixed

Before editing, record the actor, action, population, comparator, budget, unit,
status and evidence reference. Compare them after the edit. Check the direction
of each count and inequality against its receipt. When the source contradicts
the prose, correct the claim and cite the source in the same change. Keep
protocol text, run outputs and artifact digests verbatim.

Use the same term for the same operation. A fresh `REPLICATION` cohort names
a cohort in a protocol. Independent scientific replication requires a separate
investigator and its own evidence. A replay reruns a named computation. An
admission rule determines which decision a receipt can support.

## Edit grammar and cadence

Put the runner, checker or experiment before its verb. Give the action and
result their own clause. Place a condition next to the result it qualifies.
Split a sentence when it changes actors, denominators or evidence classes.
Read the paragraph aloud once. If the result arrives after a chain of
qualifications, move it earlier and put the limiting condition next to it.

- Count direction: “The router failed `0/6` cells” says it failed none.
  The receipt reports `0/6` passed. Write “The shared router passed `0/6`
  PRIMARY cells.” [R1 programme decision](../vnv/CWC_PROGRAM_DECISION_2026-08-11.md)
- Scope: “The oracle beat the best of three tested fixed baselines on synthetic S-R-O.”
  Report the metric, 99.8% mean relative reduction in canonical cross-entropy
  across five seeds, with the oracle, comparators and workload in view. [WP2 results](../../artifacts/wp2-routing-v2/RESULTS.md#L24-L32)

## Choose the check for the failure

| Failure to catch | Check |
| --- | --- |
| Missing actor, buried verb, ambiguous `it` | Identify the actor and action in each clause. Name the referent if two readings survive. [Google Technical Writing](https://developers.google.com/tech-writing/one/active-voice) |
| Awkward stress, crowded qualifiers, unclear phrase boundary | Read aloud and listen for where the result lands and where the sentence needs a pause. [Purdue Global Writing Center](https://purdueglobalwriting.center/editing-and-revising/) |
| One term for two operations, or two terms for one operation | Compare the wording with the protocol and code. Borrow controlled vocabulary from [ASD-STE100 Issue 9](https://www.asd-ste100.org/assets/files/ASD-STE100_ISSUE9.pdf). [Vale](https://vale.sh/docs) can flag configured term substitutions in Markdown. |
| Agreement, duplicate words, spelling and punctuation | [LanguageTool](https://dev.languagetool.org/developing-rules.html) can flag candidates in prose. Review flags in context around identifiers, equations and quoted records. |
| A stronger claim, inverted metric or lost boundary after editing | Compare the revised sentence with the exact source. Check status, subject, polarity, denominator and scope before approving the change. |

Vale and LanguageTool are optional editorial checks. Scientific status follows the
protocol and evidence. When a claim needs no more than a sentence and a source,
stop there.
