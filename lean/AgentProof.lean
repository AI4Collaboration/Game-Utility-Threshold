import Std

/- Exact integers represent payoffs after multiplying all fractions by one
positive common denominator. No floating point, model reasoning, or beliefs. -/
namespace AgentProof

inductive Action where
  | first | second
  deriving DecidableEq, Repr

inductive Comparison where
  | better | tied | worse
  deriving DecidableEq, Repr

structure Payoffs where
  aa : Int
  ab : Int
  ba : Int
  bb : Int
  deriving Repr

def other : Action → Action
  | .first => .second
  | .second => .first

def payoff (g : Payoffs) : Action → Action → Int
  | .first, .first => g.aa
  | .first, .second => g.ab
  | .second, .first => g.ba
  | .second, .second => g.bb

def compare (g : Payoffs) (choice opponent : Action) : Comparison :=
  if payoff g choice opponent > payoff g (other choice) opponent then .better
  else if payoff g choice opponent = payoff g (other choice) opponent then .tied
  else .worse

def BestResponse (g : Payoffs) (choice opponent : Action) : Prop :=
  payoff g (other choice) opponent ≤ payoff g choice opponent

instance (g : Payoffs) (a b : Action) : Decidable (BestResponse g a b) :=
  inferInstanceAs (Decidable (_ ≤ _))

def Dominant (g : Payoffs) (choice : Action) : Prop :=
  BestResponse g choice .first ∧ BestResponse g choice .second

instance (g : Payoffs) (a : Action) : Decidable (Dominant g a) :=
  inferInstanceAs (Decidable (_ ∧ _))

theorem bestResponse_sound (g : Payoffs) (a b : Action) (h : BestResponse g a b) :
    ∀ alternative, payoff g alternative b ≤ payoff g a b := by
  cases a <;> intro alternative <;> cases alternative <;>
    simp_all [BestResponse, payoff, other]

theorem dominance_sound (g : Payoffs) (a : Action) (h : Dominant g a) :
    ∀ opponent alternative, payoff g alternative opponent ≤ payoff g a opponent := by
  intro opponent
  cases opponent with
  | first => exact bestResponse_sound g a .first h.1
  | second => exact bestResponse_sound g a .second h.2

def penalize (g : Payoffs) (k : Int) : Payoffs :=
  { g with ba := g.ba-k, bb := g.bb-k }

theorem first_threshold (g : Payoffs) (k : Int) :
    BestResponse (penalize g k) .first .first ↔ g.ba-g.aa ≤ k := by
  simp only [BestResponse, payoff, other, penalize]
  omega

theorem second_threshold (g : Payoffs) (k : Int) :
    BestResponse (penalize g k) .first .second ↔ g.bb-g.ab ≤ k := by
  simp only [BestResponse, payoff, other, penalize]
  omega

theorem dominant_thresholds (g : Payoffs) (k : Int) :
    Dominant (penalize g k) .first ↔ g.ba-g.aa ≤ k ∧ g.bb-g.ab ≤ k := by
  simp only [Dominant, first_threshold, second_threshold]

theorem first_tie (g : Payoffs) :
    payoff (penalize g (g.ba-g.aa)) .first .first =
      payoff (penalize g (g.ba-g.aa)) .second .first := by
  simp only [payoff, penalize]
  omega

theorem second_tie (g : Payoffs) :
    payoff (penalize g (g.bb-g.ab)) .first .second =
      payoff (penalize g (g.bb-g.ab)) .second .second := by
  simp only [payoff, penalize]
  omega

/-- A certificate records both comparisons, including unfavorable findings. -/
structure Certificate (g : Payoffs) (choice : Action) where
  againstFirst : Comparison
  againstSecond : Comparison
  first_correct : compare g choice .first = againstFirst
  second_correct : compare g choice .second = againstSecond

#print axioms bestResponse_sound
#print axioms dominance_sound
#print axioms dominant_thresholds
#print axioms first_tie
#print axioms second_tie

end AgentProof
