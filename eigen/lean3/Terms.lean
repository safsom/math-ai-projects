import Gestures
/-!
# Proof terms: intrinsic compression and the logical rank of cuts

For each proof term:

* `nf`: the complete development of its written cuts. Every `have`, proof `let` and proof β-redex
  present in the term is eliminated by substitution (and data β-redexes are substituted silently, as
  in `Cuts`). Redexes *created* by the substitution (a substituted λ-proof applied to an argument)
  are not reduced: they are counted as residual cuts. Lean's `instantiate` shares substituted
  subterms, so the result is built in time and space linear in the term's DAG.
* On the DAG of `nf` (proof-position nodes only, the same nodes `Cuts` counts):
  `S` tree size, `D` distinct nodes, the largest tree multiplicity of a node (`occMax`), and the
  size `G` of an explicit cut layout found greedily: a node is named (a new cut) when its references
  times its body size exceed body + references + 1. `G` is exact for the layout it describes, so
  log₂(S/G) is a lower bound on the best possible compression by cuts, and log₂(S/D) an upper bound
  (sharing everything, naming free).
  Two occurrences of an open subterm are the same node only when their free variables are bound by
  the same binders, so every shared node could be named by a `have` at that scope.
* On the written term: each cut's formula rank (implications nested to the left; `¬A` is `A → ⊥`)
  and the multiplicity class of its variable (0, 1, ω), as a 4 × 3 histogram.
-/
open Lean

namespace Gestures.Terms
open Cuts (cutForm)

def nfBudget : Nat := 400000

def dagBudget : Nat := 200000

/-!
The cut-free normal form is never built. Cuts are eliminated through an environment: a cut-bound
variable stands for the node of its (normalized) proof. Every subterm gets a canonical hash in which
a cut variable hashes as its proof and an ordinary bound variable as its binder, so the same subproof
reached at different binder depths, or substituted at several uses, is one node.
-/
structure DS where
  chm : Std.HashMap (Expr × UInt64) UInt64 := {}
  idx : Std.HashMap UInt64 Nat := {}
  kids : Array (Array (Nat × Nat)) := #[]
  isLam : Array Bool := #[]
  label : Array String := #[]
  dbg : Bool := false
  used : Std.HashSet Nat := {}
  nextTok : Nat := 0
  log : Array String := #[]
  resid : Nat := 0
  residP : Nat := 0
  steps : Nat := 0
  over : Bool := false

/-- Per de Bruijn level: its hash (a binder identity, or the canonical hash of a cut's proof) and,
for a cut, the node of its proof. -/
structure Env where
  h : Array UInt64 := #[]
  cut : Array (Option (Nat × Nat)) := #[]

def Env.push (env : Env) (h : UInt64) (c : Option (Nat × Nat) := none) : Env := ⟨env.h.push h, env.cut.push c⟩
def Env.top (env : Env) : UInt64 := env.h.back?.getD 3

def scopeHash (env : Env) (e : Expr) : UInt64 := Id.run do
  let r := min e.looseBVarRange env.h.size
  let mut h : UInt64 := 11
  for i in [env.h.size - r:env.h.size] do
    h := mixHash h env.h[i]!
  return h

def binderId (env : Env) (dom : UInt64) : UInt64 := mixHash 7 (mixHash dom env.top)

/-- Canonical hash of `e` with the cuts in it eliminated. -/
partial def ch (cx : Ctx) (ctx : Array Expr) (env : Env) (e : Expr) : StateM DS UInt64 := do
  let e := e.consumeMData
  let key := (e, scopeHash env e)
  if let some r := (← get).chm[key]? then return r
  modify fun s => { s with steps := s.steps + 1, over := s.over || s.steps > 4 * dagBudget }
  if (← get).over then return 0
  let r ← match cutForm cx ctx e with
    | some (_, t, v, b) => do
      let hv ← ch cx ctx env v
      ch cx (ctx.push t) (env.push hv) b
    | none =>
      match e with
      | .bvar i => pure (if i < env.h.size then env.h[env.h.size - 1 - i]! else hash e)
      | .app f a =>
        if let .lam _ _ b _ := e.getAppFn.consumeMData then
          let args := e.getAppArgs
          ch cx ctx env (mkAppN (b.instantiate1 args[0]!) (args.extract 1 args.size))
        else do pure (mixHash 1 (mixHash (← ch cx ctx env f) (← ch cx ctx env a)))
      | .lam _ d b _ => do
        let hd ← ch cx ctx env d
        pure (mixHash 2 (mixHash hd (← ch cx (ctx.push d) (env.push (binderId env hd)) b)))
      | .forallE _ d b _ => do
        let hd ← ch cx ctx env d
        pure (mixHash 4 (mixHash hd (← ch cx (ctx.push d) (env.push (binderId env hd)) b)))
      | .letE _ t v b _ => do
        let ht ← ch cx ctx env t
        let hv ← ch cx ctx env v
        pure (mixHash 5 (mixHash ht (mixHash hv (← ch cx (ctx.push t) (env.push (binderId env ht)) b))))
      | .proj s i x => do pure (mixHash 6 (mixHash (hash s) (mixHash (hash i) (← ch cx ctx env x))))
      | _ => pure (hash e)
  modify fun s => { s with chm := s.chm.insert key r }
  return r

def addNode (key : UInt64) (ks : Array (Nat × Nat)) (lam : Bool) (lab : String := "") : StateM DS Nat := do
  let i := (← get).kids.size
  modify fun s => { s with idx := s.idx.insert key i, kids := s.kids.push ks, isLam := s.isLam.push lam, label := s.label.push lab }
  return i

def cutVar? (env : Env) (e : Expr) : Option (Nat × Nat) :=
  match e with
  | .bvar i => if i < env.cut.size then env.cut[env.cut.size - 1 - i]! else none
  | _ => none

/-- DAG of the proof-position nodes of the cut-free form, in post-order (children first). -/
partial def dag (cx : Ctx) (ctx : Array Expr) (env : Env) (e : Expr) : StateM DS (Option Nat) := do
  let e := e.consumeMData
  if (← get).over then return none
  -- a use of a cut variable is its proof
  if let some (c, tok) := cutVar? env e then
    modify fun s => { s with used := s.used.insert tok }
    return some c
  if let some (kind, t, v, b) := cutForm cx ctx e then
    let c ← dag cx ctx env v
    if (← get).dbg then modify fun s => { s with log := s.log.push s!"cut {kind} depth={ctx.size} v->{c}" }
    let hv ← ch cx ctx env v
    let some c := c | return ← dag cx (ctx.push t) (env.push hv) b
    let tok := (← get).nextTok
    modify fun s => { s with nextTok := tok + 1 }
    let rb ← dag cx (ctx.push t) (env.push hv (some (c, tok))) b
    -- used only inside types or data: the proof is kept, once (as in `Cuts`)
    if !(← get).used.contains tok && Id.run ((Cuts.countAll b 0).run' {}) > 0 then
      let key := mixHash 99 (mixHash hv (← ch cx (ctx.push t) (env.push hv) b))
      if let some i := (← get).idx[key]? then return some i
      let ks := match rb with
        | some r => if r == c then #[(c, 2)] else #[(r, 1), (c, 1)]
        | none => #[(c, 1)]
      return some (← addNode key ks false "keep")
    return rb
  let f := e.getAppFn.consumeMData
  let args := e.getAppArgs
  if let .lam _ _ b _ := f then
    if args.size > 0 then
      return ← dag cx ctx env (mkAppN (b.instantiate1 args[0]!) (args.extract 1 args.size))
  let key ← ch cx ctx env e
  if let some i := (← get).idx[key]? then return some i
  if (← get).kids.size ≥ dagBudget then
    modify fun s => { s with over := true }
    return none
  -- a cut variable applied to arguments: its proof is substituted at the head
  if let some (c, tok) := cutVar? env f then
    modify fun s => { s with used := s.used.insert tok }
    if (← get).isLam[c]! then
      modify fun s => { s with resid := s.resid + 1 }
      if args.any (isProofTerm cx ctx ·) then modify fun s => { s with residP := s.residP + 1 }
    let mut ks : Std.HashMap Nat Nat := ({} : Std.HashMap Nat Nat).insert c 1
    for a in args do
      if isProofTerm cx ctx a then
        if let some k ← dag cx ctx env a then ks := ks.insert k (ks.getD k 0 + 1)
    return some (← addNode key ks.toArray false)
  let some (lab, kids, _) := node cx ctx e | return none
  if (← get).dbg then modify fun s => { s with log := s.log.push s!"node {lab} depth={ctx.size} kids={kids.size}" }
  let mut ks : Std.HashMap Nat Nat := {}
  for (kctx, k) in kids do
    let env' ← if kctx.size > ctx.size then do
        let hd ← ch cx ctx env kctx.back!
        pure (env.push (binderId env hd))
      else pure env
    if let some c ← dag cx kctx env' k then
      ks := ks.insert c (ks.getD c 0 + 1)
  return some (← addNode key ks.toArray e.isLambda s!"{lab} key={key} nkids={kids.size}")

/-- Exact size of the cut layout that names the nodes in `named`: rules plus references. -/
def layout (kids : Array (Array (Nat × Nat))) (root : Nat) (named : Array Bool) : Nat × Array Nat × Array Nat := Id.run do
  let n := kids.size
  let mut cs : Array Nat := Array.replicate n 0
  for i in [0:n] do
    let mut c := 1
    for (k, m) in kids[i]! do
      c := c + m * (if named[k]! then 1 else cs[k]!)
    cs := cs.set! i c
  let mut g : Array Nat := Array.replicate n 0
  g := g.set! root 1
  for i' in [0:root + 1] do
    let i := root - i'
    let copies := if named[i]! || i == root then (if g[i]! > 0 then 1 else 0) else g[i]!
    if copies > 0 then
      for (k, m) in kids[i]! do
        g := g.set! k (g[k]! + m * copies)
  let mut G := cs[root]!
  for i in [0:n] do
    if named[i]! && i != root && g[i]! > 0 then G := G + cs[i]! + 1
  return (G, cs, g)

/-- Rank of a proposition: the depth of implications nested to the left. -/
partial def rank (env : Environment) (ctx : Array Expr) (T : Expr) : Nat :=
  match T.consumeTypeAnnotations.headBeta with
  | .forallE _ d b _ =>
    let rb := rank env (ctx.push d) b
    if isProp env ctx d then max (rank env ctx d + 1) rb else rb
  | e =>
    let args := e.getAppArgs
    match e.getAppFn.consumeMData with
    | .const c _ =>
      if c == `Not && args.size == 1 then rank env ctx args[0]! + 1
      else if c == `Iff && args.size == 2 then max (rank env ctx args[0]!) (rank env ctx args[1]!) + 1
      else if (c == `And || c == `Or) && args.size == 2 then max (rank env ctx args[0]!) (rank env ctx args[1]!)
      else if c == `Exists && args.size == 2 then
        match args[1]!.consumeMData with
        | .lam _ d b _ => rank env (ctx.push d) b
        | _ => 0
      else 0
    | _ => 0

/-- Weak head normal form by δ-unfolding of definitions and projection of constructor
applications, with a bound on the number of unfoldings. -/
partial def whnfLite (env : Environment) (fuel : Nat) (e : Expr) : Expr :=
  let e := e.consumeMData.headBeta
  if fuel == 0 then e else
  let args := e.getAppArgs
  match e.getAppFn.consumeMData with
  | .const c us =>
    match env.find? c with
    | some (.defnInfo d) =>
      whnfLite env (fuel - 1) ((d.value.instantiateLevelParams d.levelParams us).beta args)
    | _ => e
  | .proj _ i x =>
    let x' := whnfLite env (fuel - 1) x
    match x'.getAppFn.consumeMData with
    | .const k _ =>
      match env.find? k with
      | some (.ctorInfo ci) =>
        let xs := x'.getAppArgs
        if h : ci.numParams + i < xs.size then whnfLite env (fuel - 1) (mkAppN xs[ci.numParams + i] args) else e
      | _ => e
    | _ => e
  | _ => e

/-- `rank` with definitions unfolded (`s ⊆ t`, `Monotone f`, `Injective f` are implications). -/
partial def rankU (env : Environment) (ctx : Array Expr) (T : Expr) : Nat :=
  match whnfLite env 24 T.consumeTypeAnnotations with
  | .forallE _ d b _ =>
    let rb := rankU env (ctx.push d) b
    if isProp env ctx d then max (rankU env ctx d + 1) rb else rb
  | e =>
    let args := e.getAppArgs
    match e.getAppFn.consumeMData with
    | .const c _ =>
      if c == `Iff && args.size == 2 then max (rankU env ctx args[0]!) (rankU env ctx args[1]!) + 1
      else if (c == `And || c == `Or) && args.size == 2 then max (rankU env ctx args[0]!) (rankU env ctx args[1]!)
      else if c == `Exists && args.size == 2 then
        match args[1]!.consumeMData with
        | .lam _ d b _ => rankU env (ctx.push d) b
        | _ => 0
      else 0
    | _ => 0

structure RS where
  seen : Std.HashSet (Expr × Nat) := {}
  hist : Array Nat := Array.replicate 12 0
  histU : Array Nat := Array.replicate 12 0
  steps : Nat := 0

/-- Cut histogram of the written term: rank (0, 1, 2, ≥3) × multiplicity of the cut variable. -/
partial def ranks (cx : Ctx) (ctx : Array Expr) (e : Expr) : StateM RS Unit := do
  let e := e.consumeMData
  let key := (e, ctx.size)
  if (← get).seen.contains key || (← get).steps ≥ nfBudget then return
  modify fun s => { s with seen := s.seen.insert key, steps := s.steps + 1 }
  if let some (_, t, v, b) := cutForm cx ctx e then
    let r := min 3 (rank cx.env ctx t)
    let m := match mult b with | "0" => 0 | "1" => 1 | _ => 2
    let ru := min 3 (rankU cx.env ctx t)
    modify fun s => { s with hist := s.hist.modify (3 * r + m) (· + 1), histU := s.histU.modify (3 * ru + m) (· + 1) }
    ranks cx ctx v
    ranks cx (ctx.push t) b
    return
  -- a data β-redex is substituted, as in `dag`, so the cuts behind it are seen
  if let .lam _ _ b _ := e.getAppFn.consumeMData then
    let args := e.getAppArgs
    if args.size > 0 then
      return ← ranks cx ctx (mkAppN (b.instantiate1 args[0]!) (args.extract 1 args.size))
  let some (_, kids, _) := node cx ctx e | return
  for (kctx, k) in kids do
    ranks cx kctx k

def debugDump (ds : DS) (root : Option Nat) : String := Id.run do
  let mut out := s!"root={root}\n" ++ "\n".intercalate ds.log.toList ++ "\n"
  for i in [0:ds.kids.size] do
    out := out ++ s!"{i}: {ds.label[i]!} -> {ds.kids[i]!}\n"
  return out

def stats (cx : Ctx) (value : Expr) (debug : Bool := false) : List (String × Json) := Id.run do
  let ((), rst) := Id.run ((ranks cx #[] value).run {})
  let (root, ds) := Id.run ((dag cx #[] {} value).run { dbg := debug })
  let dbg := [("tDebug", toJson (debugDump ds root))]
  if ds.over || root.isNone then
    return [("tt", toJson true), ("rk", toJson rst.hist)]
  let kids := ds.kids
  let n := kids.size
  let ri := root.get!
  -- tree size and tree multiplicities; nodes not reachable from the root (proofs of dead cuts) are ignored
  let mut sz : Array Nat := Array.replicate n 0
  for i in [0:n] do
    sz := sz.set! i (1 + kids[i]!.foldl (fun a (k, m) => a + m * sz[k]!) 0)
  let mut named : Array Bool := Array.replicate n false
  let (_, _, occ) := layout kids ri named
  let occMax := occ.foldl max 0
  let reach := occ.foldl (fun a o => if o ≥ 1 then a + 1 else a) 0
  let shared := occ.foldl (fun a o => if o ≥ 2 then a + 1 else a) 0
  -- greedy layout, refined a few times; the best layout found is kept
  let mut best := sz[ri]!
  let mut bestNamed := 0
  for _ in [0:6] do
    let (G, cs, g) := layout kids ri named
    if G < best then
      best := G
      bestNamed := named.foldl (fun a b => if b then a + 1 else a) 0
    let named' := (Array.range n).map fun i =>
      i != ri && g[i]! ≥ 2 && (g[i]! - 1) * cs[i]! > g[i]! + 1
    if named' == named then break
    named := named'
  return [("tt", toJson false), ("tS", toJson sz[ri]!), ("tD", toJson reach), ("tG", toJson best),
    ("tNamed", toJson bestNamed), ("tShared", toJson shared), ("tOccMax", toJson occMax),
    ("tResid", toJson ds.resid), ("tResidP", toJson ds.residP), ("rk", toJson rst.hist), ("rku", toJson rst.histU)] ++ (if debug then dbg else [])

/-- Saves the given theorems' constants (types and proof terms) in Lean's module-data format. -/
def saveTerms (dir : System.FilePath) (mod : Name) (cis : Array ConstantInfo) : IO Unit := do
  if cis.isEmpty then return
  IO.FS.createDirAll dir
  let names := cis.map (·.name)
  let data : ModuleData := ⟨false, #[], names, cis, #[], #[]⟩
  saveModuleData (dir / (mod.toString ++ ".terms")) mod data

end Gestures.Terms
