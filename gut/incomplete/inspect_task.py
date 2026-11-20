"""Native Inspect collection for separate Design 1 games; no model grading.

Simultaneous information: separate fresh histories, neither player's choice or
reasoning is forwarded. Hidden row input is identical across actual profiles.
Paired conditions share the environment, not a conversation or an LLM response.
"""

import hashlib
import json
from math import isfinite
from pathlib import Path
from random import Random

from inspect_ai import Task
from inspect_ai.dataset import Sample
from inspect_ai.model import ChatMessageUser, get_model, model_roles
from inspect_ai.scorer import Score, scorer
from inspect_ai.solver import solver

from .games import ACTIONS, INFORMATION, SCHEMA, TYPES, encode
from gut.presentation import blocks

PROTOCOL = 'gut-private-inspect-v2'

RULES = """Play a one-round simultaneous point-reward game. Maximize your own
expected points. Neither player observes the other's choice before choosing.
Each knows its own payoff table. The row player's table is public. The column
player has a low or high reward profile, each with the stated probability.
In the revealed condition, row also learns the actual column profile. In the
hidden condition, row receives only the possibilities and probabilities.
These information rules are known to both players. All supplied payoff tables
ALREADY include the public action cost: do not subtract it a second time.
Return exactly {"action":"A"} or {"action":"B"}. No other fields."""


def parse_action(text, swapped):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON fields.")
            result[key] = value
        return result
    try:
        obj = json.loads(text, object_pairs_hook=unique)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Expected one JSON action object.") from exc
    if not isinstance(obj, dict) or set(obj) != {'action'} or obj['action'] not in ('A', 'B'):
        raise ValueError("Expected exactly action A or B.")
    return ACTIONS[(("B", "A") if swapped else ("A", "B")).index(obj['action'])]


def prompt(game, row, role):
    return RULES + '\n' + encode(game.view(role, row['information'], row['private_type'],
                                          row['cost'], row['labels_swapped'], row.get('order_reversed', False)))


def paired_samples(game, costs=None, repetitions=1, seed=2026):
    if type(repetitions) is not int or repetitions < 1 or type(seed) is not int:
        raise ValueError("Use a positive integer repetition count and integer seed.")
    costs = tuple(game.cost(z) for z in (game.costs if costs is None else costs))
    if not costs or len(set(costs)) != len(costs):
        raise ValueError("Use distinct, nonempty cost conditions.")
    samples = []
    for z in costs:
        for kind in TYPES:
            for block in blocks(ACTIONS):
                swapped, reversed_order = bool(block//2), bool(block%2)
                for repetition in range(repetitions):
                    pair = f'{game.id}:z{z}:{kind}:block{block}:r{repetition}'
                    pair_seed = int(hashlib.sha256(f'{seed}:{pair}'.encode()).hexdigest()[:12], 16)
                    for info in INFORMATION:
                        samples.append(Sample(id=f'{pair}:{info}', input='One-round game', metadata={
                            'pair_id': pair, 'game_id': game.id, 'cost': str(z), 'private_type': kind,
                            'information': info, 'labels_swapped': swapped, 'repetition': repetition,
                            'order_reversed': reversed_order, 'presentation_block': block,
                            'protocol': PROTOCOL, 'seed': pair_seed, 'type_prior': '1/2'}))
    Random(seed).shuffle(samples)
    return samples


@solver
def private_interaction(game, synthetic):
    async def run(state, generate):
        if not {'row', 'column'} <= set(model_roles()):
            raise ValueError("Both player model roles must be explicitly bound.")
        record = dict(state.metadata)
        record.update(status='started', synthetic=synthetic, choices={})
        state.metadata['record'] = record
        for role in ('row', 'column'):
            messages = [ChatMessageUser(content=prompt(game, record, role))]
            output = await get_model(role=role).generate(messages)
            state.messages = messages + [output.message]
            state.output = output
            choice = {'raw': output.completion, 'status': 'invalid'}
            record['choices'][role] = choice
            try:
                if output.choices[0].stop_reason != 'stop':
                    raise ValueError('Incomplete or refused output.')
                action = parse_action(output.completion, record['labels_swapped'])
            except ValueError as exc:
                choice['error'] = str(exc)
            else:
                choice.update(status='valid', **json.loads(encode(game.score_choice(
                    role, record['private_type'], record['cost'], action))))
        valid = all(c['status'] == 'valid' for c in record['choices'].values())
        record['status'] = 'valid' if valid else 'invalid'
        if valid:
            record['outcome'] = json.loads(encode(game.outcome(record['private_type'], record['cost'],
                record['choices']['row']['action'], record['choices']['column']['action'])))
        # Observer-only predictions; never append these to a player's prompt.
        record['theory'] = json.loads(encode(game.state(record['cost'], record['information'], record['private_type'])))
        state.completed = True
        return state
    return run


@scorer(metrics=[])
def private_outcomes():
    async def score(state, target):
        record = state.metadata['record']
        values = {'valid_pair': int(record['status'] == 'valid')}
        for role, choice in record['choices'].items():
            values[role+'_valid'] = int(choice['status'] == 'valid')
            if choice['status'] == 'valid':
                values[role+'_c'] = int(choice['action'] == 'C')
                values[role+'_dominance_violation'] = int(choice['strict_dominance_violation'])
        return Score(value=values, answer=record['status'], metadata=record)
    return score


def private_task(game, models, costs=None, repetitions=1, seed=2026, cost_limit=None):
    if set(models) != {'row', 'column'}:
        raise ValueError("Bind exactly row and column models; no role fallback.")
    synthetic = all(str(model).startswith('mockllm/') for model in models.values())
    if not synthetic and (cost_limit is None or not isfinite(cost_limit) or cost_limit <= 0):
        raise ValueError("Live tasks require a finite per-sample limit and a separately enforced study budget.")
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in Path(__file__).parent.glob('*.py')}
    return Task(name=game.id, version=PROTOCOL,
                dataset=paired_samples(game, costs, repetitions, seed),
                solver=private_interaction(game, synthetic), scorer=private_outcomes(),
                model_roles=models, cost_limit=cost_limit, fail_on_error=False,
                metadata={'schema': SCHEMA, 'synthetic': synthetic, 'config': json.loads(encode(game.config())),
                          'config_hash': game.fingerprint(), 'code_hashes': hashes, 'seed': seed,
                          'prompt_hash': hashlib.sha256(RULES.encode()).hexdigest(),
                          'sampling': 'matched revealed/hidden; shuffled; two label mappings crossed with two table orders',
                          'scoring': 'Strict dominance violations only; no unique-equilibrium or hindsight correctness label.'})
