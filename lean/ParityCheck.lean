import UtilityThreshold

open UtilityThreshold

def actionToken : Action → String
  | .cooperate => "COOPERATE"
  | .attack => "ATTACK"

def values : List Int := [1, 2, 4, 6, 8]
def defenses : List Int := [0, 2, 4, 6, 8]

def main : IO Unit := do
  let params : GameParams := { R := 1, g := 0, p := 5, L := 20 }
  for v in values do
    for d in defenses do
      let state : GameState := { v, d }
      IO.println <| String.intercalate "," [
        toString v,
        toString d,
        toString (detectionRateScaled d),
        toString (attackUtility state params),
        toString (safetyMargin state params),
        toString (humanUtility (thresholdAction state params) state params),
        actionToken (thresholdAction state params)
      ]
