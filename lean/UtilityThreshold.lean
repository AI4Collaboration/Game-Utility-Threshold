import Lean.Elab.Tactic.Omega

/- A minimal proof-carrying threshold-game foundation for Lean 4. -/
namespace UtilityThreshold

inductive Action where
  | cooperate
  | attack
  deriving DecidableEq, Repr

structure GameParams where
  R : Int
  g : Int
  p : Int

structure GameState where
  v : Int
  d : Int

/-- Utilities are multiplied by 20 to retain exact integer arithmetic. -/
def attackCost (d : Int) : Int := 10 * d
def detectionPenalty (d : Int) (p : Int) : Int := 3 * d * p

def attackUtility (state : GameState) (params : GameParams) : Int :=
  20 * state.v * params.R - attackCost state.d - detectionPenalty state.d params.p

def safetyMargin (state : GameState) (params : GameParams) : Int :=
  20 * params.g - attackUtility state params

def thresholdAction (state : GameState) (params : GameParams) : Action :=
  if 0 ≤ safetyMargin state params then .cooperate else .attack

theorem cooperate_of_nonnegative_margin (state : GameState) (params : GameParams)
    (h : 0 ≤ safetyMargin state params) : thresholdAction state params = .cooperate := by
  simp [thresholdAction, h]

theorem attack_of_negative_margin (state : GameState) (params : GameParams)
    (h : safetyMargin state params < 0) : thresholdAction state params = .attack := by
  have hnot : ¬ 0 ≤ safetyMargin state params := by
    intro hnonnegative
    omega
  simp [thresholdAction, hnot]

/-- A policy output paired with the condition required to verify it. -/
structure DecisionWitness (state : GameState) (params : GameParams) where
  action : Action
  correct : action = thresholdAction state params

def certifyThresholdDecision (state : GameState) (params : GameParams) : DecisionWitness state params :=
  { action := thresholdAction state params, correct := rfl }

end UtilityThreshold
