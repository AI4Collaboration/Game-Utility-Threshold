/-- A minimal proof-carrying threshold-game foundation for Lean 4. -/
namespace UtilityThreshold

inductive Action where
  | cooperate
  | attack
  deriving DecidableEq, Repr

structure GameParams where
  R : Rat
  g : Rat
  p : Rat

structure GameState where
  v : Rat
  d : Rat

def attackCost (d : Rat) : Rat := d / 2
def detection (d : Rat) : Rat := 3 * d / 20

def attackUtility (state : GameState) (params : GameParams) : Rat :=
  state.v * params.R - attackCost state.d - detection state.d * params.p

def safetyMargin (state : GameState) (params : GameParams) : Rat :=
  params.g - attackUtility state params

def thresholdAction (state : GameState) (params : GameParams) : Action :=
  if 0 ≤ safetyMargin state params then .cooperate else .attack

theorem cooperate_of_nonnegative_margin (state : GameState) (params : GameParams)
    (h : 0 ≤ safetyMargin state params) : thresholdAction state params = .cooperate := by
  simp [thresholdAction, h]

theorem attack_of_negative_margin (state : GameState) (params : GameParams)
    (h : safetyMargin state params < 0) : thresholdAction state params = .attack := by
  simp [thresholdAction, not_le_of_gt h]

/-- A policy output paired with the condition required to verify it. -/
structure DecisionWitness (state : GameState) (params : GameParams) where
  action : Action
  correct : action = thresholdAction state params

def certifyThresholdDecision (state : GameState) (params : GameParams) : DecisionWitness state params :=
  { action := thresholdAction state params, correct := rfl }

end UtilityThreshold
