# Controlled validation — fresh credential

**Blocked: the replacement key also received HTTP 402. No model choices.**

This collection follows the [frozen protocol](../../../docs/controlled-validation-protocol.md).
It uses the same 16,572 main requests and 120 separate compatibility requests.
No primary outcomes were observed before this restart. The [earlier billing
rejections](../2026-11-19/README.md) are retained separately.

`restart.json` records the reason, unchanged requests and combined spending
ceiling. This run has a $41.86 cap, leaving the earlier unknown costs reserved
within the original $45 allocation. No API key is included in these artifacts.

Plans and endpoint snapshots were frozen before the new compatibility pilot.
The replacement key authenticated, but its first pilot request was rejected for
insufficient account credits. No further requests or main trials were sent.
`ledger.jsonl.gz` and `audits.jsonl.gz` retain the rejection and investigation;
`status.json` records the state. The $0.200640 hold is an unknown-cost reservation,
not a reported charge. OpenRouter denied the account balance lookup because
this key lacks organization-admin privileges. There are no results to analyze.
