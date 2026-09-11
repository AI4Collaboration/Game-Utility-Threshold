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
  L : Int

structure GameState where
  v : Int
  d : Int

/-- Probabilities and utilities are multiplied by 20 for exact arithmetic. -/
def detectionRateScaled (d : Int) : Int := min 20 (max 0 (3 * d))
def attackCost (d : Int) : Int := 10 * d
def detectionPenalty (d : Int) (p : Int) : Int := detectionRateScaled d * p
def defenseCost (d : Int) : Int := 6 * d * d

def attackUtility (state : GameState) (params : GameParams) : Int :=
  20 * state.v * params.R - attackCost state.d - detectionPenalty state.d params.p

def safetyMargin (state : GameState) (params : GameParams) : Int :=
  20 * params.g - attackUtility state params

def humanUtility (action : Action) (state : GameState) (params : GameParams) : Int :=
  match action with
  | .cooperate => -defenseCost state.d
  | .attack => -defenseCost state.d - (20 - detectionRateScaled state.d) * params.L

def thresholdAction (state : GameState) (params : GameParams) : Action :=
  if 0 ≤ safetyMargin state params then .cooperate else .attack

theorem detection_rate_nonnegative (d : Int) : 0 ≤ detectionRateScaled d := by
  by_cases hnegative : 3 * d ≤ 0
  · rw [detectionRateScaled, Int.max_eq_left hnegative]
    omega
  · have hnonnegative : 0 ≤ 3 * d := by omega
    rw [detectionRateScaled, Int.max_eq_right hnonnegative]
    by_cases hlinear : 3 * d ≤ 20
    · rw [Int.min_eq_right hlinear]
      exact hnonnegative
    · rw [Int.min_eq_left (by omega)]
      omega

theorem detection_rate_at_most_twenty (d : Int) : detectionRateScaled d ≤ 20 := by
  by_cases h : max 0 (3 * d) ≤ 20
  · rw [detectionRateScaled, Int.min_eq_right h]
    exact h
  · rw [detectionRateScaled, Int.min_eq_left (by omega)]
    omega

theorem detection_rate_linear (d : Int) (h0 : 0 ≤ d) (hlinear : 3 * d ≤ 20) :
    detectionRateScaled d = 3 * d := by
  rw [detectionRateScaled, Int.max_eq_right (by omega), Int.min_eq_right hlinear]

theorem detection_rate_saturated (d : Int) (hsaturated : 20 ≤ 3 * d) :
    detectionRateScaled d = 20 := by
  have h0 : 0 ≤ 3 * d := by omega
  rw [detectionRateScaled, Int.max_eq_right h0, Int.min_eq_left hsaturated]

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

def cooperateBot (_state : GameState) (_params : GameParams) : Action := .cooperate

def defectBot (_state : GameState) (_params : GameParams) : Action := .attack

def thresholdBot (state : GameState) (params : GameParams) : Action :=
  thresholdAction state params

/-- An agent whose every output is paired with a proof of threshold optimality. -/
structure VerifiedAgent where
  name : String
  decide : (state : GameState) → (params : GameParams) → DecisionWitness state params

def dupocAgent : VerifiedAgent where
  name := "DUPOC"
  decide := certifyThresholdDecision

def cupodAgent : VerifiedAgent where
  name := "CUPOD"
  decide := certifyThresholdDecision

/-- Exact finite Bernoulli witness used to audit a probabilistic policy draw. -/
structure ProbabilisticDecisionWitness where
  attackWeight : Nat
  totalWeight : Nat
  draw : Nat
  positiveTotal : 0 < totalWeight
  weightBound : attackWeight ≤ totalWeight
  drawBound : draw < totalWeight
  action : Action
  correct : action = if draw < attackWeight then .attack else .cooperate

def certifyProbabilisticDecision
    (attackWeight totalWeight draw : Nat)
    (positiveTotal : 0 < totalWeight)
    (weightBound : attackWeight ≤ totalWeight)
    (drawBound : draw < totalWeight) : ProbabilisticDecisionWitness :=
  {
    attackWeight
    totalWeight
    draw
    positiveTotal
    weightBound
    drawBound
    action := if draw < attackWeight then .attack else .cooperate
    correct := rfl
  }

end UtilityThreshold
