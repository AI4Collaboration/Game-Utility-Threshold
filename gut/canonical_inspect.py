"""Native Inspect adapter for the existing canonical v2 tables and prompts.

The older collector and its saved data remain independently reproducible.
Each sample is a pair of fresh, simultaneous decisions, not a conversation.
"""
from fractions import Fraction as F
import json
from random import Random

from inspect_ai import Task
from inspect_ai.dataset import Sample
from inspect_ai.model import ChatMessageUser, ModelOutput, get_model
from inspect_ai.scorer import Score, scorer
from inspect_ai.solver import solver

from .canonical import EXAMPLES, controlled_conditions, controlled_matrix
from .experiment import labels, prompt
from .study import _json

PROTOCOL = 'gut-canonical-inspect-v1'


def canonical_samples(game, repetitions=5, control_repetitions=2, seed=20261120, pilot=False):
    conditions = controlled_conditions(game)
    primary = [c for c in conditions if c['purpose'] == 'primary']
    samples = []
    for block in range(4):
        selected = [primary[0 if block % 2 == 0 else -1]] if pilot else conditions
        for condition in selected:
            count = 1 if pilot else (repetitions if condition['purpose'] == 'primary' else control_repetitions)
            for repetition in range(count):
                pair = f'{game}:{condition["id"]}:b{block}:r{repetition}'
                samples.append(Sample(id=pair, input='One-round simultaneous game', metadata={
                    'game_id': game, 'pair_id': pair, 'condition': condition, 'cost': condition['z'],
                    'presentation_block': block, 'repetition': repetition, 'seed': seed,
                    'information': 'complete', 'private_type': 'fixed', 'protocol': PROTOCOL}))
    Random(seed).shuffle(samples)
    return samples


def parse_action(text, block):
    obj = _json(text)
    if not isinstance(obj, dict) or set(obj) != {'final_action'} or obj['final_action'] not in ('A', 'B'):
        raise ValueError('Expected exactly final_action A or B.')
    return labels(block // 2).index(obj['final_action'])


@solver
def interaction(game, synthetic):
    async def run(state, generate):
        record = dict(state.metadata, status='started', synthetic=synthetic, choices={})
        state.metadata['record'] = record
        condition, block = record['condition'], record['presentation_block']
        for role in ('row', 'column'):
            messages = [ChatMessageUser(content=prompt(condition['z'], role, block, game, condition))]
            output = await get_model(role=role).generate(messages)
            state.messages, state.output = messages + [output.message], output
            choice = {'raw': output.completion, 'status': 'invalid'}
            record['choices'][role] = choice
            try:
                if output.choices[0].stop_reason != 'stop':
                    raise ValueError('Incomplete or refused output.')
                action = parse_action(output.completion, block)
            except (ValueError, TypeError, KeyError, IndexError) as exc:
                choice['error'] = str(exc)
            else:
                table = controlled_matrix(game, condition, role)
                margins = [table[0][j][0] - table[1][j][0] for j in (0, 1)]
                dominant = 0 if min(margins) > 0 else (1 if max(margins) < 0 else None)
                choice.update(status='valid', action=EXAMPLES[game].actions[action], action_index=action,
                              margins=list(map(str, margins)), strict_dominant_action=dominant,
                              strict_dominance_violation=dominant is not None and action != dominant)
        valid = all(c['status'] == 'valid' for c in record['choices'].values())
        record['status'] = 'valid' if valid else 'invalid'
        if valid:
            i, j = (record['choices'][r]['action_index'] for r in ('row', 'column'))
            table = controlled_matrix(game, condition)
            payoffs = table[i][j]
            record['outcome'] = {'row_payoff': str(payoffs[0]), 'column_payoff': str(payoffs[1]),
                                 'same_action': i == j, 'joint_action': [i, j]}
            for role, chosen, other in (('row', i, j), ('column', j, i)):
                own = controlled_matrix(game, condition, role)
                record['choices'][role]['hindsight_regret'] = str(max(own[a][other][0] for a in (0, 1)) - own[chosen][other][0])
        state.completed = True
        return state
    return run


@scorer(metrics=[])
def outcomes():
    async def score(state, target):
        row = state.metadata['record']
        return Score(value={'valid_pair': int(row['status'] == 'valid')}, answer=row['status'], metadata=row)
    return score


def canonical_task(game, models, sample, cost_limit=None):
    if set(models) != {'row', 'column'}:
        raise ValueError('Bind exactly row and column.')
    synthetic = all(str(m).startswith('mockllm/') for m in models.values())
    if not synthetic and (cost_limit is None or cost_limit <= 0):
        raise ValueError('Live tasks require the shared budget.')
    return Task(name=game, version=PROTOCOL, dataset=[sample], solver=interaction(game, synthetic),
                scorer=outcomes(), model_roles=models, cost_limit=cost_limit, fail_on_error=False,
                metadata={'synthetic': synthetic, 'prompt_source': 'gut.experiment.prompt (canonical v2)',
                          'note': 'Strict dominance and retrospective payoff loss; no unique equilibrium assumed.'})


def mock_models(game, metadata):
    """Choose a best reply to a 50/50 opponent; ties select the first action."""
    models = {}
    for role in ('row', 'column'):
        table = controlled_matrix(game, metadata['condition'], role)
        action = max((0, 1), key=lambda a: sum(table[a][j][0] for j in (0, 1)))
        text = json.dumps({'final_action': labels(metadata['presentation_block'] // 2)[action]})
        models[role] = get_model('mockllm/'+role, custom_outputs=[ModelOutput.from_content('mockllm/'+role, text)])
    return models
