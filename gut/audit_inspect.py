"""Matched-information audit studies with native Inspect traces.

threshold: sweep only q at fixed rewards/penalty.
information: match actual rewards, reveal/hide them before the defender chooses
q; fixed penalty, q is an outcome, not another swept parameter.
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

from gut.audit_game import ACTIONS, SCHEMA
from gut.commitment import rational
from gut.presentation import blocks, presentation

PROTOCOL = "gut-audit-inspect-v2"
RULES = """This is a one-round point-reward audit game. Exactly one of target_1
and target_2 is checked after the attacker chooses. The defender commits to q,
the probability of checking target_1; target_2 is checked with probability 1-q.
The attacker sees q, not the realized check. Abstaining earns the attacker zero.
A violation earns the unchecked reward if not checked, or the checked reward
minus the stated punishment if checked. The defender pays punishment_cost times
punishment even after abstention. The reward profiles and prior are public.
The attacker always knows its actual profile. In revealed conditions the
defender also learns it BEFORE choosing q; in hidden conditions it does not.
Both players know these rules. Maximize your own expected points.
Return only the requested JSON object. Do not include private reasoning in it."""


def encode(value):
    return json.dumps(value, default=str, sort_keys=True)


def parse_choice(text, key, block=None):
    def unique_object(pairs):
        result = {}
        for name, entry in pairs:
            if name in result:
                raise ValueError("Duplicate JSON fields are not permitted.")
            result[name] = entry
        return result
    try:
        value = json.loads(text, object_pairs_hook=unique_object)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Response is not a JSON action.") from exc
    if not isinstance(value, dict) or set(value) != {key}:
        raise ValueError(f"Return exactly the field {key}.")
    if key == "q":
        q = rational(value[key])
        if not 0 <= q <= 1:
            raise ValueError("Checking probability must be in [0,1].")
        return q
    labels = presentation(ACTIONS, block)['labels'] if block is not None else dict(zip(ACTIONS, ACTIONS))
    for action, label in labels.items():
        if value[key] == label:
            return action
    raise ValueError("Action is not legal.")


def player_view(game, information, kind, block, role, q=None):
    """Allowlisted fields only: no scoring, future draws or hidden actual type."""
    game.information_game(information, kind)
    if role not in ('defender', 'attacker'):
        raise ValueError('Unknown role.')
    display = presentation(ACTIONS, block)
    def rows(values):
        return [{'action': display['labels'][ACTIONS[i]], **values[i]} for i in display['indices']]
    view = {'information': information, 'role': role,
            'punishment': str(game.punishment), 'punishment_cost': str(game.punishment_cost),
            'action_order': display['action_order'],
            'actions': rows([{'meaning': 'abstain'}, {'meaning': 'violate target_1'}, {'meaning': 'violate target_2'}]),
            'defender_payoffs': rows([{'unchecked': '0', 'checked': '0'}] +
                [{'unchecked': str(game.defender_unchecked[i]), 'checked': str(game.defender_checked[i])} for i in range(2)]),
            'possible_types': [
                {'name': t.name, 'prior': str(t.prior),
                 'payoffs': rows([{'unchecked': '0', 'checked_before_punishment': '0'}] +
                    [{'unchecked': str(t.unchecked[i]), 'checked_before_punishment': str(t.checked[i])} for i in range(2)])}
                for t in game.types]}
    if role == 'attacker' or information == 'revealed':
        view['actual_type'] = kind
    if q is not None:
        view['checking_probabilities'] = {'target_1': str(q), 'target_2': str(1-q)}
    return view


def player_prompt(game, metadata, role, q=None):
    instruction = ('Choose {"q":"a number or fraction"} for checking target_1.' if role == 'defender'
                   else 'Choose {"action":"one label from action_order"}.')
    return RULES + '\nYou are the ' + role + '. ' + instruction + '\n' + encode(
        player_view(game, metadata['information'], metadata['private_type'],
                    metadata['presentation_block'], role, q))


def audit_samples(game, coverages=None, repetitions=1, defender_mode='fixed', seed=100,
                  information=None, presentation_blocks=None):
    if defender_mode not in ('fixed', 'model') or type(repetitions) is not int or repetitions < 1 or type(seed) is not int:
        raise ValueError('Use fixed/model defender, positive repetitions and an integer seed.')
    infos = tuple(information if information is not None else
                  (('hidden',) if defender_mode == 'fixed' else ('revealed', 'hidden')))
    if not infos or len(set(infos)) != len(infos) or any(i not in ('revealed', 'hidden') for i in infos):
        raise ValueError('Use distinct revealed/hidden conditions.')
    if defender_mode == 'model':
        if coverages is not None:
            raise ValueError('An information study measures chosen q; do not supply a coverage sweep.')
        qs = (None,)
    else:
        qs = tuple(map(rational, game.coverage_grid() if coverages is None else coverages))
        if not qs or len(set(qs)) != len(qs):
            raise ValueError('Use distinct nonempty checking conditions.')
        for q in qs:
            game.evaluate(q)
    display_blocks = tuple(blocks(ACTIONS) if presentation_blocks is None else presentation_blocks)
    if not display_blocks or len(set(display_blocks)) != len(display_blocks):
        raise ValueError('Use distinct presentation blocks.')
    for block in display_blocks:
        presentation(ACTIONS, block)
    samples = []
    for q in qs:
        for kind in game.types:
            for block in display_blocks:
                for repetition in range(repetitions):
                    pair = f'audit:q{q}:type{kind.name}:block{block}:r{repetition}'
                    pair_seed = int(hashlib.sha256(f'{seed}:{pair}'.encode()).hexdigest()[:12], 16)
                    for info in infos:
                        samples.append(Sample(id=f'{pair}:{info}', input='Audit game decision',
                            metadata={'pair_id': pair, 'private_type': kind.name, 'planned_q': str(q) if q is not None else None,
                                      'information': info, 'presentation_block': block, 'repetition': repetition,
                                      'seed': pair_seed, 'type_prior': str(kind.prior), 'protocol': PROTOCOL}))
    Random(seed).shuffle(samples)
    return samples


@solver
def audit_interaction(game, defender_mode, synthetic):
    async def solve(state, generate):
        required = {'attacker'} | ({'defender'} if defender_mode == 'model' else set())
        if not required <= set(model_roles()):
            raise ValueError('Every player model role must be explicitly bound.')
        record = dict(state.metadata)
        record.update(status='started', synthetic=synthetic, defender_mode=defender_mode)
        state.metadata['record'] = record
        q = rational(record['planned_q']) if defender_mode == 'fixed' else None
        if defender_mode == 'model':
            messages = [ChatMessageUser(content=player_prompt(game, record, 'defender'))]
            output = await get_model(role='defender').generate(messages)
            state.messages, state.output = messages + [output.message], output
            record['defender_raw'] = output.completion
            try:
                if output.choices[0].stop_reason != 'stop':
                    raise ValueError('Incomplete or refused output.')
                q = parse_choice(output.completion, 'q')
            except ValueError as exc:
                record.update(status='invalid_defender', error=str(exc))
                state.completed = True
                return state
        record['q'] = str(q)
        messages = [ChatMessageUser(content=player_prompt(game, record, 'attacker', q))]
        output = await get_model(role='attacker').generate(messages)
        state.messages, state.output = messages + [output.message], output
        record['attacker_raw'] = output.completion
        try:
            if output.choices[0].stop_reason != 'stop':
                raise ValueError('Incomplete or refused output.')
            action = parse_choice(output.completion, 'action', record['presentation_block'])
        except ValueError as exc:
            record.update(status='invalid_attacker', error=str(exc))
        else:
            row = next(t for t in game.evaluate(q)['types'] if t['name'] == record['private_type'])
            regret = max(row['follower'])-row['follower'][ACTIONS.index(action)]
            record.update(status='valid', action=action, best_responses=row['best_responses'],
                          is_best_response=action in row['best_responses'], regret=str(regret),
                          margin=str(row['margin']), prior=str(row['prior']),
                          expected_attacker=str(row['follower'][ACTIONS.index(action)]),
                          expected_defender=str(row['leader'][ACTIONS.index(action)]),
                          outcome=json.loads(encode(game.sample(q, record['private_type'], action, Random(record['seed'])))))
        conditional = game.information_game(record['information'], record['private_type'])
        record['theory'] = json.loads(encode({'thresholds': game.thresholds(),
            'commitment': conditional.commitment().solve(),
            'realized_rewards': game.attacker_view(q, record['private_type']),
            'note': 'All attacker ties retained; leader bounds assume payoff-maximizing followers.'}))
        state.completed = True
        return state
    return solve


@scorer(metrics=[])
def audit_outcomes():
    async def score(state, target):
        row = state.metadata['record']
        scores = {'valid': int(row['status'] == 'valid')}
        if row['status'] == 'valid':
            scores.update(best_response=int(row['is_best_response']), regret=float(rational(row['regret'])),
                          violation=int(row['outcome']['violation']),
                          undetected_violation=int(row['outcome']['undetected_violation']))
        return Score(value=scores, answer=row.get('action', row['status']), metadata=row)
    return score


def audit_task(game, models, coverages=None, repetitions=1, defender_mode='fixed',
               seed=100, cost_limit=None, information=None, presentation_blocks=None):
    required = {'attacker'} | ({'defender'} if defender_mode == 'model' else set())
    if set(models) != required:
        raise ValueError('Bind exactly the player roles used by the task.')
    synthetic = all(str(m).startswith('mockllm/') for m in models.values())
    if not synthetic and (cost_limit is None or not isfinite(cost_limit) or cost_limit <= 0):
        raise ValueError('Live tasks need a finite sample limit and the study-wide budget runner.')
    samples = audit_samples(game, coverages, repetitions, defender_mode, seed, information, presentation_blocks)
    fingerprints = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                    for name in ('audit_inspect.py', 'audit_game.py', 'commitment.py', 'presentation.py')}
    return Task(name='audit_'+('information' if defender_mode == 'model' else 'threshold'), version=PROTOCOL,
                dataset=samples, solver=audit_interaction(game, defender_mode, synthetic), scorer=audit_outcomes(),
                model_roles=models, cost_limit=cost_limit, fail_on_error=False,
                metadata={'schema': SCHEMA, 'synthetic': synthetic, 'game': game.defender_view(),
                          'sweep': 'checking_probability_only' if defender_mode == 'fixed' else 'information_only',
                          'sampling': 'stratified actual profiles; shuffled; independent cyclic label and order blocks',
                          'code_hashes': fingerprints, 'prompt_hash': hashlib.sha256(RULES.encode()).hexdigest(),
                          'sources': ['https://arxiv.org/abs/1303.0356',
                                      'https://www.ifaamas.org/Proceedings/aamas08/proceedings/pdf/paper/AAMAS08_0057.pdf']})
