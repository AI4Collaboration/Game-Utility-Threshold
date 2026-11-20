"""Per-profile 2D reports; native Inspect logs remain the source of truth."""

import csv
from collections import defaultdict
from math import sqrt
from pathlib import Path
import json


def interval(successes, n):
    """95% Wilson interval for a binomial proportion; descriptive within cell."""
    if not n:
        return None, None
    p, z = successes/n, 1.959963984540054
    d = 1+z*z/n
    center = (p+z*z/(2*n))/d
    half = z*sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return center-half, center+half


def report(records, output, figures=False):
    output = Path(output)
    groups = defaultdict(list)
    for item in records:
        row = item['record']
        if not row:
            continue
        for role in ('row', 'column'):
            # Retain label blocks separately rather than pooling presentation effects.
            key = (row['game_id'], row['information'], row['private_type'],
                   row['cost'], role, row['labels_swapped'])
            groups[key].append(item)
    cells = []
    for key, items in sorted(groups.items()):
        choices = [i['record']['choices'][key[4]] for i in items
                   if i['status'] == 'valid']
        n = len(choices)
        coop = sum(c['action'] == 'C' for c in choices)
        lo, hi = interval(coop, n)
        cells.append(dict(zip(('game','information','profile','cost','role','labels_swapped'), key),
                          planned=len(items), valid_pairs=n,
                          invalid_pairs=sum(i['status']=='invalid' for i in items),
                          errors=sum(i['status'] not in ('valid','invalid') for i in items),
                          c_count=coop, c_rate=coop/n if n else None, ci_low=lo, ci_high=hi,
                          dominance_violations=sum(c['strict_dominance_violation'] for c in choices)))
    if cells:
        with (output/'cells.csv').open('x', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(cells[0]))
            writer.writeheader(); writer.writerows(cells)
    paired = defaultdict(dict)
    for item in records:
        if item['record']:
            row = item['record']
            if row['information'] in paired[row['pair_id']]:
                raise ValueError('Duplicate paired observation: do not pool repeated native epochs silently.')
            paired[row['pair_id']][row['information']] = item
    comparisons = []
    for pair_id, conditions in sorted(paired.items()):
        valid = set(conditions) == {'revealed', 'hidden'} and all(i['status']=='valid' for i in conditions.values())
        row = {'pair_id': pair_id, 'both_valid': valid}
        for role in ('row', 'column'):
            row[role+'_hidden_minus_revealed_c'] = (
                int(conditions['hidden']['record']['choices'][role]['action']=='C') -
                int(conditions['revealed']['record']['choices'][role]['action']=='C')) if valid else None
        comparisons.append(row)
    if comparisons:
        with (output/'pairs.csv').open('x', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(comparisons[0]))
            writer.writeheader(); writer.writerows(comparisons)
    summary = {'synthetic': all(r['record'] and r['record']['synthetic'] for r in records),
               'samples': len(records), 'valid_pairs': sum(r['status']=='valid' for r in records),
               'invalid_pairs': sum(r['status']=='invalid' for r in records),
               'errors': sum(r['status'] not in ('valid','invalid') for r in records),
               'matched_environments': len(comparisons),
               'both_conditions_valid': sum(c['both_valid'] for c in comparisons),
               'note': 'Each cell is one role/profile/label block. Intervals describe sampling variation, not safety guarantees. No fitted behavioral threshold or causal significance claim.'}
    (output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    if figures:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from fractions import Fraction
        from .games import get_game
        panels = sorted({(c['game'], c['profile'], c['role'], c['labels_swapped']) for c in cells})
        for game, profile, role, swapped in panels:
            fig, ax = plt.subplots(figsize=(6.2, 4.2), layout='constrained')
            for info, marker in (('revealed','o'), ('hidden','s')):
                rows = sorted([c for c in cells if (c['game'],c['profile'],c['role'],c['labels_swapped']) ==
                               (game,profile,role,swapped) and c['information']==info and c['valid_pairs']],
                              key=lambda c: Fraction(c['cost']))
                if rows:
                    ax.errorbar([float(Fraction(c['cost'])) for c in rows], [c['c_rate'] for c in rows],
                        yerr=[[c['c_rate']-c['ci_low'] for c in rows], [c['ci_high']-c['c_rate'] for c in rows]],
                        label=info, marker=marker, markerfacecolor='none',
                        markersize=7 if info=='revealed' else 4, zorder=3 if info=='revealed' else 2,
                        linestyle='--' if info=='revealed' else '-', capsize=2, linewidth=1)
            roots = get_game(game).thresholds(role, profile)
            for z in sorted({roots['against_c'], roots['against_d']}):
                if z >= 0:
                    ax.axvline(float(z), color='0.4', linestyle=':', linewidth=1)
            counts = [c['valid_pairs'] for c in cells if (c['game'],c['profile'],c['role'],c['labels_swapped']) ==
                      (game,profile,role,swapped)]
            ax.set(xlabel='Public cost of D (points)', ylabel='Fraction choosing C', ylim=(-.03,1.03),
                   title=f"{'SYNTHETIC · ' if summary['synthetic'] else ''}{game}\n{role} · {profile} · label {int(swapped)} · n={min(counts)}–{max(counts)} per cell")
            ax.legend(); fig.savefig(output/f'{game}-{profile}-{role}-labels{int(swapped)}.png', dpi=170)
            plt.close(fig)
    return summary
