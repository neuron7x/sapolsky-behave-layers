# Capability Assessment and Trigger Levels

## Current profile
- **Capabilities:** small-scale synthetic mechanism experiments; no language/agent capability.
- **Deployment:** none (local research only).
- **Data:** synthetic, non-sensitive.
- **Infrastructure access:** none autonomous.
- **Status:** `TRIGGER_NOT_REACHED` for all frontier-safety documents. Producing a full
  safety case, red-team report, or incident-response plan now would be **fabrication of
  governance that no capability warrants** — deliberately deferred, not omitted.

## Trigger ladder (documents unlock only when the trigger is reached)
| Trigger | Condition | Then required |
|---|---|---|
| **TR-1** external tool use | network / filesystem-beyond-sandbox / cloud creds / external API | THREAT_MODEL, RISK_REGISTER, SECURITY, INCIDENT_RESPONSE |
| **TR-2** public / multi-user | served to others | PRIVACY/PII, VULNERABILITY_DISCLOSURE, DEPLOYMENT_MONITORING, RED_TEAM_PLAN |
| **TR-3** autonomous long-running agent | acts without per-step human approval | sandbox-escape / credential-misuse / persistence / shutdown-override evaluations |
| **TR-4** material automated AI R&D | meaningfully automates ML research | SAFETY_CASE, independent capability + risk review, enhanced security, deployment hold |

Capability-triggered escalation mirrors Anthropic RSP / DeepMind FSF / OpenAI Frontier
Governance in *structure only*; CWC asserts no frontier capability.
