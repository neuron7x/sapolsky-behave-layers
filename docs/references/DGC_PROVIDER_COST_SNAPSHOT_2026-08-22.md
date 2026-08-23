# DGC Provider Cost Snapshot — 2026-08-22

Purpose: current external cost context only. **Not a DGC savings benchmark and not a recommendation to select a particular model.**

Source-of-record pages retrieved 2026-08-22:

- `https://developers.openai.com/api/docs/models/gpt-5.6-sol`
- `https://developers.openai.com/api/docs/models/gpt-5.6-terra`
- `https://developers.openai.com/api/docs/models/gpt-5.6-luna`

Text-token prices shown by those model-specific pages at retrieval time, USD per 1M tokens:

| Model | Input | Cached input | Output |
|---|---:|---:|---:|
| GPT-5.6 Sol | 5.00 | 0.50 | 30.00 |
| GPT-5.6 Terra | 2.00 | 0.20 | 12.00 |
| GPT-5.6 Luna | 0.20 | 0.02 | 1.20 |

The model pages also document long-context uplifts and other pricing conditions. DGC accounting therefore MUST bind the exact provider/model/tier/context regime used by each operation instead of using a single global token price.

Economic implication permitted by this snapshot: inference operations can have materially different marginal prices, so compute admission/routing can affect spend. It does **not** establish that DGC saves any particular percentage.
