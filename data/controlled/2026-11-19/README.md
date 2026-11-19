# Controlled validation — 19 November 2026

**Collection blocked: OpenRouter account credits. No new model choices.**
Plans frozen before collection. See the [protocol](../../../docs/controlled-validation-protocol.md).
The committed suite manifest fixes 16,572 main and 120 separate pilot requests
across three model configurations. The shared spending ceiling is US$45.

Canonical native plans are stored in game/model directories; the two oversight
plans contain all models. Plans are losslessly gzip-compressed. Eight dispatched
pilot requests all returned HTTP 402, “Insufficient credits.” Collection stopped;
the remaining 112 pilot and all 16,572 main requests were unattempted. This is
an archived failed compatibility attempt, **not an experimental result**.

`ledger.jsonl.gz` preserves each exact request and raw rejection; `audits.jsonl.gz`
records the investigation. `status.json` records counts and budget holds. The
$2.8222592 reservation is a conservative hold for unknown costs, **not a reported
charge**; the provider supplied no usage. No retry or replacement was sent.
After account funding is resolved, any fresh compatibility pilot must be frozen
and retained separately before collecting the untouched main study.

`historical-checksums.json` inventories the original T/S grid and historical
oversight files. Those data are preserved, never pooled into this study.
