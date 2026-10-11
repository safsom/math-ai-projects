import Lean
/-!
# Gestures: typed inference steps read off elaborated proof terms

Every node of a proof term that is itself a proof gets a *gesture*: the shape of the inference rule it
uses, written in a small simple type system obtained by erasing dependency.

* Types τ are proposition heads: `=`, `≠`, `↔`, `∧`, `∨`, `¬`, `∃`, `⊤`, `⊥`, `≤`, `<`, `∈`, `⊆`, `∣`,
  `→` (non-dependent implication), `∀`, and atomic predicates `P:<area>` (by the mathlib area that
  defines them), `P:local` (defined in the declaration's own project) or `P:var` (a predicate variable).
* An application node `c a₁ … aₙ` in proof position has gesture `mech(τ₁,…,τₖ)⇒τ`, where τᵢ are the
  types of its proof premises, τ its conclusion and `mech` the kind of rule: a core logical constant by
  name (`core:Eq.mpr`, `core:And.intro`, …), a tactic family (`tac:Linarith`, `tac:Ring`, …), `rec`,
  `match`, `decide`, `lemma` (library theorem), `local` (theorem of the same project), `ctor`, `def`,
  or `hyp` (a local hypothesis applied to premises).
* Binders carry a linear-logic annotation: `λh:τ:m` introduces a hypothesis of type τ used m ∈ {0,1,ω}
  times in its scope (weakening, linear use, contraction); `cut:τ:m` is a `have`/`let` of a proof.

Per declaration we record gesture counts and parent→child gesture pairs (the composition graph),
treating the proof term as a DAG: a shared subterm is counted once.
-/
open Lean

namespace Gestures

structure Ctx where
  env : Environment
  isLocal : Name → Bool
  modOf : Name → Option Name

structure St where
  uni : Std.HashMap String Nat := {}
  bi : Std.HashMap String Nat := {}
  memo : Std.HashMap (Expr × Nat) String := {}
  nodes : Nat := 0
  truncated : Bool := false
  hasSorry : Bool := false
  atoms : Std.HashMap String Nat := {}

abbrev M := ReaderT Ctx (StateM St)

def budget : Nat := 40000

def coreRules : NameSet := List.foldl (·.insert ·) {} [
  `Eq.mpr, `Eq.mp, `Eq.trans, `Eq.symm, `Eq.subst, `Eq.substr, `Eq.ndrec, `Eq.rec, `Eq.recOn,
  `Eq.refl, `rfl, `HEq.refl, `HEq.trans, `HEq.symm, `eq_of_heq, `heq_of_eq, `congrArg, `congrFun,
  `congr, `id, `cast, `absurd, `False.elim, `False.rec, `trivial, `True.intro, `And.intro, `And.left,
  `And.right, `And.elim, `And.symm, `Or.inl, `Or.inr, `Or.elim, `Or.resolve_left, `Or.resolve_right,
  `Or.symm, `Exists.intro, `Exists.elim, `Exists.choose, `Exists.choose_spec, `Classical.byContradiction,
  `Classical.byCases, `Classical.em, `Classical.not_not, `Decidable.byContradiction, `Decidable.byCases,
  `Iff.intro, `Iff.mp, `Iff.mpr, `Iff.symm, `Iff.trans, `Iff.refl, `propext, `funext, `of_eq_true,
  `of_eq_false, `eq_self, `eq_true, `eq_false, `implies_congr, `forall_congr, `Eq.mpr_prop,
  `Eq.mpr_not, `iff_of_eq, `Not.intro, `Not.elim, `mt, `Function.mt, `letFun, `dite, `ite,
  `Subtype.property, `Subtype.mk, `ne_eq, `not_false_eq_true, `Nat.le.refl, `le_refl, `le_rfl]

def areaOf (m : Name) : String :=
  match m.components.map (·.toString) with
  | "Mathlib" :: a :: _ => a
  | r :: _ => if r == "Init" || r == "Std" || r == "Lean" || r == "Batteries" then "Core" else r
  | [] => "?"

def tacticFamily (m : Name) : Option String :=
  match m.components.map (·.toString) with
  | "Mathlib" :: "Tactic" :: f :: _ => some f
  | "Init" :: "Omega" :: _ => some "Omega"
  | "Init" :: "Grind" :: _ => some "Grind"
  | "Init" :: "Data" :: _ :: "Linear" :: _ => some "Linear"
  | "Lean" :: "Elab" :: "Tactic" :: f :: _ => some f
  | "Std" :: "Tactic" :: f :: _ => some f
  | "Aesop" :: _ => some "Aesop"
  | _ => none

partial def codomainIsProp : Expr → Bool
  | .forallE _ _ b _ => codomainIsProp b
  | .mdata _ e => codomainIsProp e
  | .sort .zero => true
  | _ => false

/-- Is `T` (a type in context `ctx`) a proposition? Decided from the sort of its head. -/
partial def isProp (env : Environment) (ctx : Array Expr) (T : Expr) : Bool :=
  match T.consumeTypeAnnotations.headBeta with
  | .forallE _ d b _ => isProp env (ctx.push d) b
  | .sort _ => false
  | e =>
    match e.getAppFn.consumeMData with
    | .const c _ => match env.find? c with
      | some ci => codomainIsProp ci.type
      | none => false
    | .bvar i => if i < ctx.size then codomainIsProp ctx[ctx.size - 1 - i]! else false
    | _ => false

/-- Erased simple type of a proposition. -/
partial def tau (cx : Ctx) (ctx : Array Expr) (P : Expr) : String :=
  match P.consumeTypeAnnotations.headBeta with
  | .forallE _ d b _ => if isProp cx.env ctx d && !b.hasLooseBVar 0 then "→" else "∀"
  | .sort _ => "Sort"
  | e =>
    match e.getAppFn.consumeMData with
    | .const c _ =>
      if c == `Eq || c == `HEq then "="
      else if c == `Ne then "≠" else if c == `Iff then "↔" else if c == `And then "∧"
      else if c == `Or then "∨" else if c == `Not then "¬"
      else if c == `Exists || c == `ExistsUnique || c == `Nonempty then "∃"
      else if c == `True then "⊤" else if c == `False then "⊥"
      else if c == `LE.le || c == `GE.ge then "≤" else if c == `LT.lt || c == `GT.gt then "<"
      else if c == `Membership.mem then "∈"
      else if c == `HasSubset.Subset || c == `HasSSubset.SSubset then "⊆"
      else if c == `Dvd.dvd then "∣"
      else if cx.isLocal c then "P:local"
      else match cx.modOf c with
        | some m => "P:" ++ areaOf m
        | none => "P:local"
    | .bvar _ | .fvar _ => "P:var"
    | _ => "?"

/-- Head constant of an atomic (non-connective) proposition, for the concept record. -/
def atomHead (cx : Ctx) (P : Expr) : Option Name :=
  match P.consumeTypeAnnotations.headBeta.getAppFn.consumeMData with
  | .const c _ =>
    if [`Eq, `HEq, `Ne, `Iff, `And, `Or, `Not, `Exists, `ExistsUnique, `Nonempty, `True, `False,
        `LE.le, `GE.ge, `LT.lt, `GT.gt, `Membership.mem, `HasSubset.Subset, `HasSSubset.SSubset,
        `Dvd.dvd].contains c then none
    else if cx.isLocal c then some `local else some c
  | _ => none

def isMatcherName (env : Environment) (c : Name) : Bool :=
  Lean.Meta.isMatcherCore env c ||
    (match c with
     | .str _ s => s.startsWith "match_"
     | _ => false)

def mech (cx : Ctx) (c : Name) : String :=
  if coreRules.contains c then "core:" ++ c.toString
  else if c == `sorryAx then "sorry"
  else if c == `Lean.ofReduceBool || c == `Lean.ofReduceNat then "decide:native"
  else if c == `of_decide_eq_true || c == `of_decide_eq_false || c == `Decidable.decide then "decide"
  else if isMatcherName cx.env c then "match"
  else
    match cx.env.find? c with
    | some (.recInfo _) => "rec"
    | some ci =>
      if isAuxRecursor cx.env c || isNoConfusion cx.env c then "rec"
      else match (cx.modOf c).bind tacticFamily with
        | some f => "tac:" ++ f
        | none =>
          match ci with
          | .ctorInfo _ => if cx.isLocal c then "ctor:local" else "ctor"
          | .thmInfo _ => if cx.isLocal c then "local" else "lemma"
          | _ => if cx.isLocal c then "def:local" else "def"
    | none => "?"

/-- Binder domains of `ty` instantiated along `args`, the instantiated result type, and the number of
arguments consumed by explicit binders (further arguments are applied through unfolding). -/
partial def telescope (ty : Expr) (args : Array Expr) : Array Expr × Expr × Nat := Id.run do
  let mut ty := ty
  let mut doms : Array Expr := #[]
  let mut base := 0
  let mut i := 0
  while i < args.size do
    match ty with
    | .forallE _ d b _ =>
      doms := doms.push (d.instantiateRevRange base i args)
      ty := b
      i := i + 1
    | .mdata _ e => ty := e
    | _ =>
      let t := (ty.instantiateRevRange base i args).headBeta
      match t with
      | .forallE .. =>
        ty := t
        base := i
      | _ => return (doms, t, i)
  return (doms, ty.instantiateRevRange base i args, i)

partial def countBVar (e : Expr) (i : Nat) : StateM (Std.HashMap (Expr × Nat) Nat) Nat := do
  if e.looseBVarRange ≤ i then return 0
  if let some r := (← get)[(e, i)]? then return r
  let r ← match e with
    | .bvar j => pure (if j == i then 1 else 0)
    | .app f a => do
      let x ← countBVar f i
      if x ≥ 2 then pure 2 else pure (min 2 (x + (← countBVar a i)))
    | .lam _ d b _ => do pure (min 2 ((← countBVar d i) + (← countBVar b (i + 1))))
    | .forallE _ d b _ => do pure (min 2 ((← countBVar d i) + (← countBVar b (i + 1))))
    | .letE _ t v b _ => do
      pure (min 2 ((← countBVar t i) + (← countBVar v i) + (← countBVar b (i + 1))))
    | .mdata _ x => countBVar x i
    | .proj _ _ x => countBVar x i
    | _ => pure 0
  modify (·.insert (e, i) r)
  return r

/-- Usage multiplicity of the innermost bound variable in `b`: 0, 1 or ω. -/
def mult (b : Expr) : String :=
  match Id.run ((countBVar b 0).run' {}) with
  | 0 => "0"
  | 1 => "1"
  | _ => "ω"

def bvarType (ctx : Array Expr) (i : Nat) : Option Expr :=
  if i < ctx.size then some ((ctx[ctx.size - 1 - i]!).liftLooseBVars 0 (i + 1)) else none

partial def isProofTerm (cx : Ctx) (ctx : Array Expr) (a : Expr) : Bool :=
  match a.consumeMData with
  | .bvar i => match bvarType ctx i with
    | some T => isProp cx.env ctx T
    | none => false
  | .lam _ d b _ => isProofTerm cx (ctx.push d) b
  | .letE _ t _ b _ => isProofTerm cx (ctx.push t) b
  | e =>
    match e.getAppFn.consumeMData with
    | .const c _ => match cx.env.find? c with
      | some ci => let (_, res, _) := telescope ci.type e.getAppArgs; isProp cx.env ctx res
      | none => false
    | .bvar i => match bvarType ctx i with
      | some T => let (_, res, _) := telescope T e.getAppArgs; isProp cx.env ctx res
      | none => false
    | _ => false

def capPrem (ts : Array String) : String :=
  if ts.size ≤ 6 then ",".intercalate ts.toList
  else ",".intercalate (ts.extract 0 6).toList ++ s!",+{ts.size - 6}"

abbrev Kids := Array (Array Expr × Expr)

def rule (cx : Ctx) (ctx : Array Expr) (m : String) (ty : Expr) (args : Array Expr) :
    String × Kids × Option Name := Id.run do
  let (doms, res, used) := telescope ty args
  let mut prem : Array String := #[]
  let mut kids : Kids := #[]
  for i in [0:used] do
    let d := doms[i]!
    if isProp cx.env ctx d then
      prem := prem.push (tau cx ctx d)
      kids := kids.push (ctx, args[i]!)
  for i in [used:args.size] do
    if isProofTerm cx ctx args[i]! then
      prem := prem.push "u"
      kids := kids.push (ctx, args[i]!)
  let unfold := if used < args.size then "+u" else ""
  return (s!"{m}({capPrem prem})⇒{tau cx ctx res}{unfold}", kids, atomHead cx res)

def structName (s : Name) : String :=
  if s == `And || s == `Iff || s == `Subtype || s == `PProd || s == `Prod || s == `PSigma ||
     s == `Sigma then s.toString else "struct"

def app (cx : Ctx) (ctx : Array Expr) (e : Expr) : Option (String × Kids × Option Name) :=
  let f := e.getAppFn.consumeMData
  let args := e.getAppArgs
  match f with
  | .lam .. => some ("cut:β", #[(ctx, e.headBeta)], none)
  | .const c _ =>
    if c == `letFun && args.size == 4 then
      match args[3]!.consumeMData with
      | .lam _ d b _ =>
        some (s!"cut:{tau cx ctx d}:{mult b}", #[(ctx, args[2]!), (ctx.push d, b)], none)
      | _ => some ("cut:?", #[(ctx, args[2]!)], none)
    else
      match cx.env.find? c with
      | some ci => some (rule cx ctx (mech cx c) ci.type args)
      | none => some ("?", #[], none)
  | .bvar i => match bvarType ctx i with
    | some T => some (rule cx ctx "hyp" T args)
    | none => none
  | .proj s _ x =>
    some (s!"proj:{structName s}+app",
      #[(ctx, x)] ++ (args.filter (isProofTerm cx ctx)).map (fun a => (ctx, a)), none)
  | _ => some ("app?", #[], none)

def node (cx : Ctx) (ctx : Array Expr) (e : Expr) : Option (String × Kids × Option Name) :=
  match e with
  | .lam _ d b _ =>
    let g := if isProp cx.env ctx d then s!"λh:{tau cx ctx d}:{mult b}" else s!"λx:{mult b}"
    some (g, #[(ctx.push d, b)], none)
  | .letE _ t v b _ =>
    if isProp cx.env ctx t then
      some (s!"cut:{tau cx ctx t}:{mult b}", #[(ctx, v), (ctx.push t, b)], atomHead cx t)
    else some ("let", #[(ctx.push t, b)], none)
  | .bvar i => match bvarType ctx i with
    | some T => some (s!"hyp()⇒{tau cx ctx T}", #[], atomHead cx T)
    | none => none
  | .proj s _ x => some (s!"proj:{structName s}", #[(ctx, x)], none)
  | .const .. | .app .. => app cx ctx e
  | _ => none

def edge (p g : String) : M Unit :=
  modify fun s =>
    let k := p ++ "\t" ++ g
    { s with bi := s.bi.insert k (s.bi.getD k 0 + 1) }

partial def visit (ctx : Array Expr) (e : Expr) (parent : String) : M Unit := do
  let e := e.consumeMData
  let key := (e, ctx.size)
  if let some g := (← get).memo[key]? then
    edge parent g
    return
  if (← get).nodes ≥ budget then
    modify fun s => { s with truncated := true }
    return
  let cx ← read
  let some (g, kids, atom) := node cx ctx e | return
  modify fun s => { s with
    memo := s.memo.insert key g, nodes := s.nodes + 1,
    uni := s.uni.insert g (s.uni.getD g 0 + 1),
    hasSorry := s.hasSorry || g.startsWith "sorry",
    atoms := match atom with
      | some a => let k := a.toString; s.atoms.insert k (s.atoms.getD k 0 + 1)
      | none => s.atoms }
  edge parent g
  for (c, k) in kids do
    visit c k g

def countsJson (m : Std.HashMap String Nat) : Json :=
  Json.mkObj (m.toList.map fun (k, v) => (k, toJson v))

/-- Analyse one theorem; returns a JSON record. -/
def analyse (cx : Ctx) (n : Name) (value : Expr) (extra : List (String × Json)) : Json :=
  let ((), s) := ((visit #[] value "ROOT").run cx).run {}
  Json.mkObj ([("n", toJson n.toString), ("nodes", toJson s.nodes), ("tr", toJson s.truncated),
    ("sorry", toJson s.hasSorry), ("u", countsJson s.uni), ("b", countsJson s.bi),
    ("a", countsJson s.atoms)] ++ extra)

end Gestures
