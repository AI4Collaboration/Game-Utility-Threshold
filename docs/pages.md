# Public game explorer and research results

The site is an offline static build of the existing game UI and the two
retained experimental datasets. GitHub Pages serves HTML, JavaScript, figures,
and downloads. No API key, model call, account, or Python server is needed to
use the published explorer.

The browser uses exact rational arithmetic for decisions, ties, thresholds,
and equilibria; decimals are only display coordinates. Tests compare the
browser calculations with the Python reference. The original oversight game
still uses eleven human defense choices, observed defense, deterministic
payoffs, and pure strategies. The science demo uses exact integer comparisons
for decisions and a seeded generator for replayable synthetic rounds.

## Build without paid calls

Install the repository's figure dependencies, then run:

```sh
python3 build_site.py
python3 -m http.server 8766 --bind 127.0.0.1 --directory _site
```

Open `http://127.0.0.1:8766/results.html`. All local links are relative; tests
also resolve them under the GitHub Pages project subpath.
Use `--output PATH` to select a new output directory. The builder refuses to
replace an existing nonempty directory unless it has this builder's
`site-manifest.json` marker. `_site/` is generated output, not research source.

## What is published

* `index.html`, `games.html`, `oversight.html`: interactive mathematical
  explorers and deterministic toy simulations.
* `science.html`: a simulated science audit with synthetic instrument logs,
  sampled evidence, human verdicts, and a conditional payoff threshold.
  Its practice records are not an additional LLM experiment.
* `results.html`: catalogue and concise explanation of the two retained
  experimental studies, with their separate assumptions and limitations.
* `report/`: offline reproduction of the original 169-setting, four-model
  simultaneous-game experiment, together with its separate theory figures.
* `validation/`: the completed 9 November 2026 oversight study, with all
  saved figures, tables, and a detailed report.
* `data/post/`, `data/oversight/2026-11-09/`: complete copies of both retained
  datasets, including raw compressed records, frozen plans, and provenance.
* `downloads/`: ZIP bundles of each dataset. The underlying source files
  keep their original bytes and hashes.
* `docs/`: guides, protocol, results, and this publication note.
* `site-manifest.json`: source commit and hashes of published files.

The historical repository snapshot is linked from the catalogue. It remains
separate: it contains older experiments and implementations not revalidated
or pooled into this site. The new canonical-game cost experiments have a
working framework but no new live results; synthetic demonstrations are not
presented as model observations.

## Publication boundary

`build_site.py` copies only named files. It never recursively copies the
workspace, `.env`, `runs/`, credential files, or Git metadata. It verifies the
source dataset checksums, checks HTML links for the GitHub project subpath,
and scans output for credential patterns, including decompressed raw records
and ZIP contents. A failed check stops the build before replacing the previous
site. These controls reduce accidental disclosure; only reviewed datasets
should be added to the explicit publication list.

Report generation and site deployment do not collect new model responses.
