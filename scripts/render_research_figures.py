"""Render publication-style matrices and charts from saved live experiments.

Run from any directory: python scripts/render_research_figures.py
Outputs PNG, editable SVG, an HTML gallery, exact aggregates, and a ZIP bundle.
No provider credentials or new model calls are used.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import sys
import textwrap
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch, Rectangle
import numpy as np

from utility_threshold.figure_data import GAMES, MODELS, OBJECTIVES, build_figure_data
from utility_threshold.research_metrics import build_metric_atlas
from render_metric_atlas import render_metric_atlas

COLORS = LinearSegmentedColormap.from_list("research_scores", [
    "#c51b30", "#f2784b", "#fff3ae", "#a6d96a", "#0d8754",
])
BLUE, ORANGE = "#91baff", "#ffd09a"
POSITIVE, NEGATIVE = "#a9df9e", "#ff9898"
INK = "#18232b"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 11, "text.color": INK,
    "axes.labelcolor": INK, "axes.edgecolor": "#cbd1da",
    "xtick.color": INK, "ytick.color": INK,
    "svg.fonttype": "none", "svg.hashsalt": "aisi-replication-02",
    "savefig.facecolor": "white", "figure.facecolor": "white",
})

MODEL_NOTE = (
    "Each model has 96 role appearances per game, pooled over opponents, roles, six treatments and both objectives. "
    "Joint outcomes are attributed to both participants; self-play contributes two dependent role appearances."
)
GAME_NOTE = (
    "Each cell contains 32 joint games: 16 ordered model pairs × 2 objectives. "
    "Binding commitment restricts the available actions, making its equilibrium result mechanical."
)
LIMIT_NOTE = "Descriptive rates; one observation per factorial cell. No confidence intervals or significance claims."


def caption(fig, text: str, *, width: int = 154, y: float = .04):
    fig.text(.04, y, "\n".join(textwrap.wrap(text, width)), ha="left", va="bottom",
             fontsize=10, linespacing=1.5, color="#374151")


def save(fig, output: Path, stem: str, title: str, note: str, catalog: list[dict], dpi: int):
    fig.text(.96, .988, "AISI RESEARCH  /  REPLICATION 02  /  11 SEP 2026",
             ha="right", va="top", fontsize=7.5, color="#637083")
    fig.savefig(output / f"{stem}.png", dpi=dpi)
    fig.savefig(output / f"{stem}.svg", metadata={"Date": None, "Description": note})
    catalog.append({"id": stem, "title": title, "caption": note,
                    "png": f"{stem}.png", "svg": f"{stem}.svg"})
    plt.close(fig)


def heat_table(table: dict, title: str, subtitle: str, note: str, *, low_is_best: bool = False):
    values = np.asarray(table["values"])
    nr, nc = values.shape
    has_mean = table["columns"][-1] == "Weighted mean"
    fig = plt.figure(figsize=(15.5, 3.9 + nr * .47))
    fig.text(.04, .94, title, fontsize=21, fontweight="bold", va="top")
    fig.text(.04, .881, subtitle, fontsize=11, color="#586174", va="top")
    ax = fig.add_axes([.04, .235, .92, .585])
    label_width, cw = 3.0, 1.9
    full = label_width + nc * cw
    ax.set_xlim(0, full)
    ax.set_ylim(nr + 1.5, -.05)
    ax.axis("off")
    ax.text(.10, .52, "Model" if nr == 5 else "Treatment", fontfamily="DejaVu Serif",
            fontsize=14, fontweight="bold", va="center")
    for j, label in enumerate(table["columns"]):
        if label == "Weighted mean": label = "Weighted\nmean"
        ax.text(label_width + (j + .5) * cw, .53, label, ha="center", va="center",
                fontfamily="DejaVu Serif", fontsize=12.5, fontweight="bold", linespacing=1.35)
    for i, label in enumerate(table["rows"]):
        y = i + 1.15
        ax.text(.10, y + .46, label, va="center", fontfamily="DejaVu Serif",
                fontsize=14, fontweight="bold" if i == nr - 1 else "normal")
        for j in range(nc):
            value = values[i, j]
            color = COLORS(1 - value if low_is_best else value)
            ax.add_patch(Rectangle((label_width + j * cw, y), cw, .93,
                                   facecolor=color, edgecolor=(1, 1, 1, .12), linewidth=.3))
            best = np.min(values[:-1, j]) if low_is_best else np.max(values[:-1, j])
            bold = i < nr - 1 and np.isclose(value, best, rtol=0, atol=1e-12)
            number = f"{value:.3f}" if low_is_best else f"{value:.2f}"
            ax.text(label_width + (j + .5) * cw, y + .46, number,
                    ha="center", va="center", color="#091b13", fontfamily="DejaVu Serif",
                    fontsize=18, fontweight="bold" if bold else "normal")
    for y, lw in ((.02, 1.6), (1.08, .9), (nr + .09, 1), (nr + 1.13, 1.6)):
        ax.plot([0, full], [y, y], color="#152019", lw=lw)
    if has_mean:
        ax.plot([full - cw, full - cw], [.02, nr + 1.13], color="#17211a", lw=.8)
    scale_ax = fig.add_axes([.765, .168, .185, .019])
    scale_ax.imshow(np.linspace(0, 1, 256)[None, :], aspect="auto",
                    cmap=COLORS.reversed() if low_is_best else COLORS, extent=[0, 1, 0, 1])
    scale_ax.set_yticks([])
    scale_ax.set_xticks([0, .5, 1], labels=["0", "0.5", "1"])
    scale_ax.tick_params(axis="x", labelsize=9, length=0)
    direction = "Lower is better" if low_is_best else "Higher score"
    extreme = "minimum" if low_is_best else "maximum"
    fig.text(.04, .172, f"Bold: observed column {extreme}. {direction}; colors fixed to [0, 1].",
             fontsize=10, color="#586174")
    caption(fig, note, width=161, y=.027)
    return fig


def bar_comparison(data: dict, title: str, note: str):
    fig, ax = plt.subplots(figsize=(15.5, 7.5))
    fig.subplots_adjust(left=.065, right=.97, top=.76, bottom=.25)
    fig.text(.04, .95, title, fontsize=21, fontweight="bold", va="top")
    fig.text(.04, .885, "Open-ended → explicit individual expected utility | same games, models and treatments",
             fontsize=11, color="#586174")
    ax.set_facecolor("#f0f1f8")
    positions = np.arange(len(data["labels"]))
    for offset, (metric, color) in zip((-.19, .19), (("expected_payoff_nash", BLUE), ("utilitarian_optimal", ORANGE))):
        item = data["metrics"][metric]
        for i, (before, after) in enumerate(zip(item[OBJECTIVES[0]], item[OBJECTIVES[1]])):
            x = positions[i] + offset
            ax.bar(x, min(before, after), width=.32, color=color, zorder=3)
            delta = after - before
            if abs(delta) > 1e-12:
                ax.bar(x, abs(delta), width=.32, bottom=min(before, after),
                       color=POSITIVE if delta > 0 else NEGATIVE, zorder=3)
            ax.plot([x - .16, x + .16], [after, after], color=INK, lw=1.2, zorder=4)
            top = max(before, after)
            ax.text(x, top + .023, f"{after:.2f}", ha="center", va="bottom", fontweight="bold", fontsize=13)
            sign_color = "#08753f" if delta > 1e-12 else "#b31c25" if delta < -1e-12 else "#596272"
            ax.text(x, top + .09, f"{delta * 100:+.1f} pp", ha="center", va="bottom",
                    fontweight="bold", fontsize=10, color=sign_color)
    ax.set_ylim(0, 1.16)
    ax.set_yticks(np.arange(0, 1.01, .2))
    ax.set_ylabel("Fraction of joint outcomes", fontsize=12)
    ax.set_xticks(positions, data["labels"], fontsize=11)
    ax.grid(axis="y", color="#dce0e7", zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    fig.legend(handles=[Patch(color=BLUE, label="Nash equilibrium"), Patch(color=ORANGE, label="Welfare optimum"),
                        Patch(color=POSITIVE, label="Increase"), Patch(color=NEGATIVE, label="Decrease")],
               loc="upper left", bbox_to_anchor=(.06, .84), ncol=4, frameon=False, fontsize=10)
    caption(fig, "Bold numbers are explicit-utility scores; signed labels are percentage-point changes from open-ended. "
            "A green/red segment spans the two conditions; bars are not additive metrics. " + note, width=163)
    return fig


def crossplay_figure(data: dict):
    fig, axes = plt.subplots(2, 2, figsize=(14.8, 11.8))
    fig.subplots_adjust(left=.14, right=.90, top=.855, bottom=.19, hspace=.75, wspace=.5)
    fig.text(.04, .96, "Self-play and cross-play: joint outcomes", fontsize=21, fontweight="bold", va="top")
    fig.text(.04, .91, "Row model × column model | four games and six treatments | 24 joint games per cell per objective",
             fontsize=11, color="#586174")
    labels = ["Claude\nSonnet 4.5", "GPT-5\nmini", "Gemini 3\nFlash Preview", "Llama 3.3\n70B"]
    for row, metric in enumerate(("expected_payoff_nash", "utilitarian_optimal")):
        for col, objective in enumerate(OBJECTIVES):
            ax = axes[row, col]
            values = np.asarray(data[f"{metric}:{objective}"]["values"])[:-1, :-1]
            im = ax.imshow(values, cmap=COLORS, vmin=0, vmax=1, aspect="auto")
            ax.set_xticks(range(4), labels, fontsize=9)
            ax.set_yticks(range(4), labels, fontsize=9)
            ax.set_xlabel("Column model", fontsize=10)
            ax.set_ylabel("Row model", fontsize=10)
            metric_label = "Nash-equilibrium rate" if row == 0 else "Welfare-optimal outcome rate"
            condition = "Open-ended" if col == 0 else "Explicit individual utility"
            ax.set_title(f"{condition}\n{metric_label}", fontsize=12, pad=10)
            for i in range(4):
                for j in range(4):
                    ax.text(j, i, f"{values[i, j]:.2f}", ha="center", va="center", fontsize=15,
                            fontfamily="DejaVu Serif", fontweight="bold" if i == j else "normal")
            for i in range(4):
                ax.add_patch(Rectangle((i - .49, i - .49), .98, .98, fill=False, edgecolor=INK, lw=1.1))
    cax = fig.add_axes([.93, .30, .014, .45])
    fig.colorbar(im, cax=cax, ticks=[0, .5, 1])
    note = "Outlined diagonal cells are self-play; off-diagonal cells are cross-play. Ordered roles are preserved. " + LIMIT_NOTE
    caption(fig, note, width=145)
    return fig, note


def threshold_figure(data: dict):
    fig, axes = plt.subplots(2, 2, figsize=(15.5, 10.5))
    fig.subplots_adjust(left=.075, right=.97, top=.84, bottom=.18, hspace=.62, wspace=.24)
    fig.text(.04, .96, "Analytical thresholds in the live-game payoff models", fontsize=21, fontweight="bold", va="top")
    fig.text(.04, .908, "Calculated from probability-weighted latent-state payoffs | these curves are not fitted model responses",
             fontsize=11, color="#586174")
    for key, ax in zip(GAMES, axes.flat):
        item = data[key]["expected"]
        aa, ab, ba, bb = item["payoffs"]
        ax.set_title(GAMES[key].replace("\n", " — "), fontsize=12, pad=12)
        ax.grid(color="#e6e8ed", zorder=0)
        ax.spines[["top", "right"]].set_visible(False)
        if key in ("frontier_deployment_race", "autonomous_escalation"):
            x = np.linspace(0, 5, 201)
            ax.plot(x, x - item["against_first"], color="#3377b5", lw=2.4, label="Against safe opponent")
            ax.plot(x, x - item["against_second"], color="#ce7944", lw=2.4, label="Against competitive opponent")
            ax.axhline(0, color=INK, lw=.8)
            ax.axvline(item["dominance"], color="#087b50", ls="--", lw=1.5)
            ax.text(item["dominance"] + .10, .85, f"x* = {item['dominance']:.3f}",
                    transform=ax.get_xaxis_transform(), color="#087b50", fontsize=11, fontweight="bold")
            ax.set_xlabel("Expected cost on racing / escalation, x")
            ax.set_ylabel("Safe-action utility minus alternative")
            ax.legend(loc="upper left", fontsize=9, framealpha=.9)
        elif key == "cross_lab_incident_response":
            x = np.linspace(0, 13, 201)
            q = np.clip((bb - ab - x) / (aa - ba + bb - ab), 0, 1)
            ax.plot(x, q, color="#3377b5", lw=2.5)
            ax.axhline(.5, color=INK, lw=.8, ls=":")
            for value, label in ((item["risk_dominance"], "Risk dominance"), (item["dominance"], "Strict dominance above")):
                ax.axvline(value, color="#087b50", ls="--", lw=1)
                ax.text(value, .91, f"{label}\n{value:.4f}".rstrip("0").rstrip("."),
                        ha="center", fontsize=9, color="#087b50")
            ax.set_ylim(-.04, 1.05)
            ax.set_xlabel("Assurance paid for containment, x")
            ax.set_ylabel("Required belief in counterpart containment")
        else:
            x = np.linspace(0, 20, 201)
            q = (bb + x - ab) / (aa + bb + 2 * x - 2 * ab)
            ax.plot(x, q, color="#3377b5", lw=2.5)
            ax.axhline(.5, color=INK, lw=.8, ls=":")
            ax.scatter([0], [item["belief"]], color="#3377b5", s=45, zorder=4)
            ax.text(1, item["belief"] - .003, f"q*(0) = {item['belief']:.4f}", fontsize=10)
            ax.text(.96, .18, "Both coordinated equilibria persist.\nNo finite neutral bonus selects one.",
                    ha="right", transform=ax.transAxes, fontsize=10)
            ax.set_ylim(.46, .505)
            ax.set_xlabel("Neutral bonus at either matching protocol, x")
            ax.set_ylabel("Belief needed to prefer own protocol")
    note = "Positive utility margin favors the safe action; equality is indifference. Stag Hunt needs assurance above 11.025 "
    note += "for strict dominance. Belief thresholds use risk-neutral expected utility; other risk criteria can differ."
    caption(fig, note, width=155)
    return fig, note


def threshold_table(data: dict):
    fig = plt.figure(figsize=(15.5, 7.3))
    fig.text(.04, .95, "Utility thresholds: canonical examples and live-game payoffs", fontsize=20, fontweight="bold", va="top")
    fig.text(.04, .884, "Analytical indifference boundaries | strict preferences require exceeding the listed boundary",
             fontsize=11, color="#586174")
    ax = fig.add_axes([.04, .245, .92, .565]); ax.axis("off")
    rows = []
    definitions = (
        ("frontier_deployment_race", "Audit strictly dominates racing", "dominance", "utility"),
        ("autonomous_escalation", "De-escalation strictly dominates", "dominance", "utility"),
        ("cross_lab_incident_response", "Belief in reciprocal containment (x = 0)", "belief", "belief"),
        ("cross_lab_incident_response", "Assurance for risk dominance", "risk_dominance", "utility"),
        ("cross_lab_incident_response", "Assurance for strict dominance", "dominance", "utility"),
        ("incident_response_protocol", "Belief in preferred protocol (x = 0)", "belief", "belief"),
        ("incident_response_protocol", "Payoff gap between coordinated protocols", "compensation", "utility"),
    )
    for key, concept, field, unit in definitions:
        values = [data[key][version][field] for version in ("deterministic", "expected")]
        formatter = (lambda v: f"{100*v:.2f}%") if unit == "belief" else (lambda v: f"{v:.4f}".rstrip("0").rstrip("."))
        rows.append([GAMES[key].split("\n")[0], concept, *map(formatter, values)])
    rows.append(["Battle of the Sexes", "Neutral bonus selecting a unique protocol", "No finite value", "No finite value"])
    tab = ax.table(cellText=rows, colLabels=["Game", "Threshold meaning", "Canonical example", "Live expected payoffs"],
                   colWidths=[.19, .42, .18, .21], cellLoc="left", loc="center", bbox=[0, 0, 1, 1])
    tab.auto_set_font_size(False); tab.set_fontsize(11.5)
    for (i, j), cell in tab.get_celld().items():
        cell.set_edgecolor("white"); cell.set_linewidth(1)
        cell.set_facecolor("#e7ecf2" if i == 0 else "#f4f6f8" if i % 2 else "white")
        cell.get_text().set_fontfamily("DejaVu Serif")
        if i == 0: cell.get_text().set_weight("bold")
    note = "Utility quantities and belief percentages have different units, so this table has no score color scale. "
    note += "Canonical examples and live uncertain games use different payoffs. These are mathematical boundaries, "
    note += "not estimated switching points for the four LLMs. A neutral coordination bonus leaves both protocol equilibria available."
    caption(fig, note, width=158, y=.05)
    return fig, note, rows


def write_gallery(output: Path, catalog: list[dict], provenance: dict):
    cards = []
    for entry in catalog:
        title = html.escape(entry["title"])
        cards.append(f'<article id="{entry["id"]}"><h2>{title}</h2>'
                     f'<a href="{entry["png"]}"><img loading="lazy" src="{entry["png"]}" alt="{title}"></a>'
                     f'<p>{html.escape(entry["caption"])}</p>'
                     f'<nav><a href="{entry["png"]}" download>PNG · high resolution</a>'
                     f'<a href="{entry["svg"]}" download>SVG · editable vector</a></nav></article>')
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AISI research figures — replication 02</title><style>
body{font:16px/1.6 system-ui,sans-serif;background:#f3f5f7;color:#18232b;margin:0}
main{max-width:1240px;margin:auto;padding:44px 28px}h1{font-size:38px;line-height:1.15;letter-spacing:-1px}
h2{font-size:23px}p{max-width:1050px;color:#4b5563}a{color:#176146}nav{display:flex;gap:24px;flex-wrap:wrap}
article{background:white;border:1px solid #dfe5eb;border-radius:12px;padding:24px;margin:30px 0}
img{width:100%;height:auto}code{font-size:13px}.eyebrow{font-size:13px;letter-spacing:1.5px;color:#176146}
li{margin:8px 0}</style><main><div class="eyebrow">AISI · GAME UTILITY THRESHOLD · REPLICATION 02</div>
<h1>Cooperation, equilibrium and utility thresholds</h1>
<p>Saved live experiments from 11 September 2026: 768 joint games with four models, four games, six treatments
and two objectives; plus 156 decisions in the separate sequential-oversight threshold evaluation.</p>
<p><strong>Expanded atlas:</strong> 28 figures, 34 gameplay metrics and 15 threshold-evaluation metrics,
including cooperation, competition, deviation regret, safety, utility and observed threshold behavior.</p>
<nav><a href="metric_explorer.html">Explore every metric and condition</a><a href="research-figures.zip" download>Download all figures</a><a href="metric_atlas.json">Complete metric data</a>
<a href="README.md">Methods and reproduction</a><a href="manifest.json">Provenance and checksums</a></nav>
<ul><li>Higher equilibrium scores mean more stable action pairs under expected payoffs; they are not a safety ranking.</li>
<li>Model tables attribute joint outcomes to both participating roles. Those appearances are not independent observations.</li>
<li>Changes compare open-ended and explicit individual-utility instructions; both conditions already display numeric payoffs.</li>
<li>Binding commitments constrain action choices. Threshold curves are analytical, not fitted LLM response curves.</li></ul>
'''
    page += "\n".join(cards) + "</main></html>"
    (output / "index.html").write_text(page, encoding="utf-8")
    readme = """# Research figure package — replication 02

The figures use the latest complete saved replication, dated 11 September 2026.
Earlier runs are not merged into these rates. No new model calls are made.

## Reproduce

Install `matplotlib>=3.8` and `numpy>=1.26`, then from the repository root run:

```bash
python3 scripts/render_research_figures.py
python3 -m pytest -q tests/test_figure_data.py tests/test_research_metrics.py tests/test_metric_explorer.py
```

All paths in the default command are resolved relative to the repository.
PNG exports are 220 dpi; SVG exports keep editable text. Use `--dpi 300` for
larger PNGs. `figure_data.json` includes the original figure matrices;
`metric_atlas.json` adds the full metric atlas, numeric observations, exact
denominators, and threshold derivations. `metric_explorer.html` is self-contained
and works offline with no network requests. It filters every score by objective,
treatment and game, and supports model, treatment and ordered cross-play tables.
The manifest hashes the input data, analysis/plotting code, and every artifact.

## Denominators and interpretation

- Gameplay: 4 row models × 4 column models × 4 games × 6 treatments × 2
  objective conditions × 1 replicate = 768 joint outcomes / 1,536 role slots.
- Model/game table: 96 role appearances per cell, 384 per model. For a joint
  metric the outcome is attributed to both roles, including twice in self-play.
  For the first-action table only that participant's action is counted.
  These are opponent- and role-pooled descriptions, not independent model effects.
- Treatment/game table: 32 joint games per cell, 128 per treatment.
- Objective change plots: matched conditions, 192 role appearances per model
  or 96 joint games per game per condition. Both conditions display payoffs;
  the contrast changes the objective instruction, not numerical versus prose format.
- Cross-play: 24 joint games per ordered pair per objective, pooled over games
  and treatments. Diagonals are self-play.
- Phase-one evaluation: 39 cases per model (25 broad grid, 4 just-safe,
  5 exact-boundary, 5 just-unsafe). Weighted means use those counts rather
  than equal stratum weights. Invalid model actions and worksheets are retained.
- One observation per gameplay factorial cell does not estimate within-cell
  variance. No inferential error bars, p-values, or claims of significance are shown.

## Metric definitions

- Welfare optimum: observed joint action maximizes the sum of treatment-adjusted
  expected payoffs over permitted profiles (`utilitarian_optimal`). It is not
  the action-level utilitarian-accuracy measure in the supplied style reference.
  External subsidies are included in those payoffs; this is not net social surplus.
- Nash equilibrium: neither player can improve expected utility by a unilateral
  permitted deviation (`expected_payoff_nash`). It tests the observed pure
  profile, not convergence to a mixed equilibrium or a correlated equilibrium.
- First action: audit / de-escalate / joint containment / public disclosure,
  respectively. Protocol selection has two legitimate coordinated outcomes.
  A larger first-action value there is not necessarily better; the color scale
  visualizes frequency only.
- Structural success: mutual audit, asymmetric escalation/de-escalation,
  mutual containment, or either matching protocol. Mutual de-escalation is safe
  but not the Chicken structural target, so this score is not universal safety.
- Catastrophe probability: the latent-state probability of a catastrophic
  outcome conditional on the observed action pair; not the frequency of
  realized sampled catastrophes. Lower is better and the color scale is reversed.
- Binding commitment removes inconsistent actions. Its perfect equilibrium
  score is partly mechanical and cannot establish model reasoning competence.
- Threshold correctness: matches the phase-one utility-maximizing action and
  its specified cooperation tie-break. Utility-maximizing ATTACK can be correct.
- Worksheet quality scores concern observable outputs, not private model thoughts.
- Analytical thresholds are computed from the checked-in payoff definitions.
  Figures 11, 13, 24 and 26 use risk-neutral expected utility. Figure 25 uses
  six explicitly specified decision criteria and three opponent beliefs.
  Equality means indifference; strict dominance requires >.

Rate heatmaps use fixed [0, 1] scales. Raw utility and regret panels have
separate, labeled utility scales; cross-game averages are not normalized
rankings. Original single-metric tables bold all column maxima (minima for
catastrophe), excluding the summary row. Expanded multi-panel tables show
all values without highlighting winners. Cross-play panels bold the self-play
diagonal. Rows and models retain a fixed order.
Marginal means are count-weighted. Values are rounded to two decimals
(three for catastrophe probabilities to retain small nonzero risks);
the exact unrounded values and counts remain in JSON.

## Expanded metric coverage

All 24 saved gameplay score fields are exposed, plus 10 derived diagnostics:
own-role deviation regret, best-response rate, zero-risk Nash outcomes,
own expected and realized utility, minimum-player expected welfare,
shifted Nash welfare product, declared confidence, first-action opponent belief,
and opponent-prediction Brier loss. The first-action and cooperation fields
are aliases, not two independent measures. All 13 saved phase-one scores
are exposed, with attack and invalid-action frequencies added separately.

Mediator compliance and message–action consistency are applicable to 128
joint games each, not all 768. The atlas uses the original nullable outcome
fields to avoid the saved scorer's zero filling outside the relevant treatment.
Each matrix exports available and eligible counts, with N/A rather than zero
for absent data. Joint consistency/compliance scores are attributed jointly,
not treated as individual causal effects. For individual action, regret, utility,
confidence and belief metrics the model table instead uses the participant's
own role. Missing declared confidence is excluded from its descriptive mean;
the original confidence-calibration score retains its scorer's missing-value penalty.

The gameplay-wide CSV contains model and treatment tables for all 34 metrics.
The explorer can export any filtered matrix, including phase-one metrics.
Raw prompts, credentials, and private reasoning are not embedded in the explorer.

## Threshold evidence versus derivation

- Figure 22 tests the observed adjacent safe / boundary / unsafe decisions:
  11 of 20 model–defense tests pass (55%). This is behavior, not a payoff formula.
- Figure 23 describes feasible deterministic step thresholds from every sampled
  value at each defense. COOPERATE implies theta >= v; ATTACK implies theta < v.
  Contradictory actions are explicitly nonmonotonic; censored intervals and
  invalid outputs are flagged. These are not fitted traits or confidence intervals.
- Figure 24 catalogs canonical, three latent-state and expected-payoff boundaries
  for all four games. Full payoffs and pure/mixed equilibria are saved in JSON.
- Figure 25 numerically derives 54 risk-dependent thresholds using expected value,
  mean–variance, CARA, lower-tail CVaR, maximin and prospect value at opponent
  first-action probabilities 0.25, 0.50 and 0.75. Parameter values, search bounds
  and tolerance are saved in JSON. The intervention is extra cost on the second
  action, which differs from assurance bonuses under nonlinear risk criteria.
- Figure 26 distinguishes the tested contract's target-profile Nash boundary
  from the stronger target-action dominance boundary, accounting for detection,
  false positives and enforcement. Penalty 6 crosses the target Nash boundary
  in all four games, but the dominance boundary only in Prisoner's Dilemma.

The four-game factorial varies mechanisms and objectives, not a dense utility
parameter sweep. It does not identify LLM switching curves for those four games.
Producing those curves requires additional live parameter-sweep experiments.

## Files

"""
    readme += "\n".join(f'- `{e["id"]}.png` / `.svg`: {e["title"]}' for e in catalog)
    readme += "\n\n## Source files\n\n" + "\n".join(f'- `{s["path"]}` (SHA-256 `{s["sha256"]}`)' for s in provenance["sources"])
    (output / "README.md").write_text(readme + "\n", encoding="utf-8")


def fingerprint(path: Path) -> dict:
    return {"path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gameplay", type=Path, default=ROOT / "results/model_gameplay_replication_02.json")
    parser.add_argument("--phase-one", type=Path, default=ROOT / "results/phase_one_model_eval_replication_02.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/figures/replication_02")
    parser.add_argument("--dpi", type=int, default=220)
    args = parser.parse_args()
    if args.dpi < 72: parser.error("--dpi must be at least 72")
    gameplay = json.loads(args.gameplay.read_text())
    phase_one = json.loads(args.phase_one.read_text())
    if any(not payload["generated_at"].startswith("2026-09-11") for payload in (gameplay, phase_one)):
        parser.error("This labeled replication-02 figure set requires the 11 September 2026 source datasets")
    data = build_figure_data(gameplay, phase_one)
    atlas = build_metric_atlas(gameplay, phase_one)
    out = args.output; out.mkdir(parents=True, exist_ok=True)
    provenance = {
        "dataset": "replication_02", "run_date": "2026-09-11", "gameplay_joint_games": 768,
        "phase_one_decisions": 156, "dpi": args.dpi, "matplotlib": matplotlib.__version__,
        "numpy": np.__version__,
        "sources": [fingerprint(p.resolve()) for p in (args.gameplay, args.phase_one, Path(__file__),
                    ROOT / "utility_threshold/figure_data.py", ROOT / "utility_threshold/games/scenarios.py",
                    ROOT / "utility_threshold/games/uncertain_scenarios.py",
                    ROOT / "utility_threshold/research_metrics.py", ROOT / "scripts/render_metric_atlas.py",
                    ROOT / "scripts/metric_explorer.html", ROOT / "utility_threshold/games/decision.py",
                    ROOT / "utility_threshold/games/treatments.py", ROOT / "utility_threshold/games/base.py",
                    ROOT / "model_gameplay_inspect.py", ROOT / "analyze_phase_one_results.py")],
    }
    catalog = []
    tables = [
        ("01_model_welfare", "Welfare-optimal joint outcomes by model and game", "Joint expected welfare maximized among permitted outcomes", MODEL_NOTE + " Transfers and subsidies enter the scored utilities."),
        ("02_model_equilibrium", "Nash-equilibrium outcomes by model and game", "Observed pure profiles with no profitable unilateral deviation", MODEL_NOTE + " Equilibrium frequency is not a safety or welfare ranking."),
        ("03_model_actions", "First-action choices by model and game", "Audit · de-escalate · joint containment · public disclosure", "96 individual role decisions per model/game; 384 per model. Each role's own action is counted, including both roles in self-play. Protocol selection has two valid coordinated options; first-action frequency is not a universal cooperation score."),
        ("04_mechanism_success", "Structural outcomes by mechanism and game", "Mutual audit · asymmetric escalation/de-escalation · mutual containment · either matching protocol", GAME_NOTE + " Mutual de-escalation is safe but is not the Chicken structural target."),
        ("05_mechanism_equilibrium", "Nash-equilibrium outcomes by mechanism and game", "Equilibrium tested after treatment transformations and action restrictions", GAME_NOTE),
        ("06_mechanism_catastrophe", "Expected catastrophe probability by mechanism and game", "Latent-state risk conditional on observed choices | lower is better", GAME_NOTE + " These are expected probabilities, not realized sampled catastrophe frequencies."),
        ("10_threshold_accuracy", "Threshold decision accuracy by model and test stratum", "Sequential oversight evaluation | 156 decisions | cooperation tie-break at exact equality", "39 cases per model. Weighted means reflect 25 / 4 / 5 / 5 cases across the four strata. Invalid actions stay in the denominator. Correctness follows utility maximization, which can prescribe ATTACK."),
        ("12_observable_worksheets", "Observable threshold reasoning: worksheet quality", "Sequential oversight evaluation | the scores assess emitted worksheets and decisions", "39 cases per model. A correct action does not establish a correct calculation. An inequality being present does not establish its correctness. Invalid worksheets remain in denominators; private model reasoning is not observed."),
    ]
    for stem, title, subtitle, note in tables:
        fig = heat_table(data["matrices"][stem], title, subtitle, note, low_is_best="catastrophe" in stem)
        save(fig, out, stem, title, note, catalog, args.dpi)
    for stem, title, note in (
        ("07_objective_by_model", "How objective instructions change equilibrium and welfare", "192 role appearances per model per condition; joint metrics pooled over opponents, roles, games and treatments. " + LIMIT_NOTE),
        ("08_objective_by_game", "Objective effects differ across the four games", "96 joint games per game per condition, pooled over all model pairs and treatments. " + LIMIT_NOTE),
    ):
        save(bar_comparison(data[stem], title, note), out, stem, title, note, catalog, args.dpi)
    fig, note = crossplay_figure(data["09_crossplay"])
    save(fig, out, "09_crossplay", "Self-play and cross-play: joint outcomes", note, catalog, args.dpi)
    fig, note = threshold_figure(data["11_analytic_thresholds"])
    save(fig, out, "11_analytic_thresholds", "Analytical thresholds in the live-game payoff models", note, catalog, args.dpi)
    fig, note, rows = threshold_table(data["11_analytic_thresholds"])
    data["13_threshold_matrix"] = rows
    save(fig, out, "13_threshold_matrix", "Utility thresholds: canonical examples and live-game payoffs", note, catalog, args.dpi)
    render_metric_atlas(atlas, out, catalog, args.dpi, save)
    catalog.sort(key=lambda e: e["id"])
    (out / "figure_data.json").write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_gallery(out, catalog, provenance)
    provenance["figures"] = catalog
    files = [out / e[fmt] for e in catalog for fmt in ("png", "svg")]
    files += [out / n for n in ("index.html", "README.md", "figure_data.json", "metric_atlas.json",
                               "metric_explorer.html", "all_metric_matrices.csv")]
    provenance["artifacts"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (out / "manifest.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    with zipfile.ZipFile(out / "research-figures.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files + [out / "manifest.json"]): archive.write(path, path.name)
    print(f"Rendered {len(catalog)} figures in PNG + SVG: {out}")
    print("Source audit: 768 complete joint games; 156 threshold decisions; exact counts saved in figure_data.json")


if __name__ == "__main__":
    main()
