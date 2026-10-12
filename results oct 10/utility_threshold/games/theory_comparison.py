"""Analytic comparators for recorded choices; no fitted behavioral assumptions."""
from math import isfinite

from .phase_space import SymmetricPayoffs, score_joint

TOL = 1e-9  # All decision tolerances are in normalized payoff units.


def best_response(margin):
    """Return the complete optimal action set, including indifference."""
    return 'C|D' if abs(margin) <= TOL else ('C' if margin > 0 else 'D')


def decision_benchmark(p: SymmetricPayoffs, action, q):
    scale = p.R - p.P
    a, b = (p.R-p.T)/scale, (p.S-p.P)/scale
    slope = a-b
    cutoff = -b/slope if abs(slope) > TOL else None
    dominant = 'C' if min(a,b) > TOL else ('D' if max(a,b) < -TOL else None)
    valid_action = action in ('C','D')
    valid_q = isinstance(q,(int,float)) and not isinstance(q,bool) and isfinite(q) and 0 <= q <= 1
    half = (a+b)/2
    result = {
        'strict_dominant_action': dominant,
        'dominant_action_chosen': action == dominant if dominant and valid_action else None,
        'belief_threshold_q': cutoff,
        'belief_threshold_in_unit_interval': cutoff is not None and 0 <= cutoff <= 1,
        'C_optimal_belief_condition': ('q >= threshold' if slope > TOL else 'q <= threshold')
            if cutoff is not None else ('every q' if b >= -TOL else 'no q'),
        'every_belief_indifferent': max(abs(a),abs(b)) <= TOL,
        'q_half_margin_normalized': half,
        'q_half_best_response': best_response(half),
        'q_half_action_consistent': action in best_response(half).split('|') if valid_action else None,
        'cost_for_weak_C_dominance_raw': max(p.T-p.R,p.P-p.S,0),
        'stated_q': q if valid_q else None,
        'stated_belief_margin_normalized': None,
        'stated_belief_best_response': None,
        'stated_belief_tie': None,
        'stated_belief_action_consistent': None,
        'stated_belief_regret_normalized': None,
        'cost_for_weak_C_at_stated_belief_raw': None,
        **{f'{x}_threshold_at_stated_belief': None for x in ('T','R','P','S')},
    }
    if valid_q:
        margin = q*a+(1-q)*b
        optimum = best_response(margin)
        result.update(stated_belief_margin_normalized=margin,
                      stated_belief_best_response=optimum,
                      stated_belief_tie=abs(margin)<=TOL,
                      stated_belief_action_consistent=action in optimum.split('|') if valid_action else None,
                      stated_belief_regret_normalized=max(0,-margin if action=='C' else margin) if valid_action else None,
                      cost_for_weak_C_at_stated_belief_raw=max(0,-margin*scale))
        if q > 0:
            result['T_threshold_at_stated_belief'] = p.R+(1-q)/q*(p.S-p.P)
            result['R_threshold_at_stated_belief'] = p.T-(1-q)/q*(p.S-p.P)
        if q < 1:
            result['P_threshold_at_stated_belief'] = p.S+q/(1-q)*(p.R-p.T)
            result['S_threshold_at_stated_belief'] = p.P-q/(1-q)*(p.R-p.T)
    return result


def joint_benchmark(p: SymmetricPayoffs, row, column):
    theory = p.report()
    scores = score_joint(p,row,column)
    q = theory['mixed_cooperation_probability']
    mixed_nash = None
    if q is not None:
        probabilities = {('C','C'): q*q, ('C','D'): q*(1-q),
                         ('D','C'): q*(1-q), ('D','D'): (1-q)**2}
        mixed_nash = sum(probabilities[tuple(profile)] for profile in theory['pure_nash'])
    maximum = max(2*p.R,p.S+p.T,2*p.P)
    return {
        **scores,
        'pure_nash_profiles': theory['pure_nash'],
        'symmetric_interior_mixed_C_probability': q,
        'pure_nash_outcome_probability_if_independent_mixed_NE': mixed_nash,
        'maximum_joint_payoff_raw': maximum,
        'welfare_gap_normalized': (maximum-scores['welfare'])/(p.R-p.P) if scores['valid'] else None,
        'maximum_unilateral_regret_normalized': max(scores['row_regret'],scores['column_regret']) if scores['valid'] else None,
    }
