"""Independent, balanced action naming and display order; no payoff changes.

Cross cyclic label rotations with cyclic order rotations: four blocks for
two actions, nine for three. Every action has every label and position equally.
"""


def presentation(actions, block=0):
    actions = tuple(actions)
    n = len(actions)
    if n not in (2, 3) or type(block) is not int or not 0 <= block < n*n:
        raise ValueError("Use one of the declared two- or three-action blocks.")
    mapping, order = divmod(block, n)
    names = tuple(chr(ord('A') + (i+mapping) % n) for i in range(n))
    indices = tuple((i+order) % n for i in range(n))
    return {'block': block, 'label_rotation': mapping, 'order_rotation': order,
            'labels': dict(zip(actions, names)), 'indices': indices,
            'action_order': tuple(names[i] for i in indices)}


def blocks(actions):
    return tuple(range(len(actions)**2))
