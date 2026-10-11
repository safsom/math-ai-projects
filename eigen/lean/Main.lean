import Gestures
/-!
Driver: import Mathlib once; (1) extract gestures for mathlib's source theorems; (2) elaborate each
OpenAI project module by module on top of the Mathlib environment (one process, one import) and
extract gestures for every theorem it adds.
-/
open Lean Elab

structure ModJob where
  mod : String
  path : String
deriving FromJson

structure ProjJob where
  name : String
  modules : Array ModJob
deriving FromJson

structure Job where
  out : String
  imports : Array String
  mathlibNames : String := ""
  projects : Array ProjJob := #[]
deriving FromJson

def projKey (m : Name) : String :=
  ".".intercalate ((m.components.take 3).map (·.toString))

/-- The longest prefix of `n` (including `n`) that is a source declaration name. -/
partial def sourceParent (names : NameSet) (n : Name) : Option Name :=
  if names.contains n then some n
  else match n with
    | .str p _ => sourceParent names p
    | .num p _ => sourceParent names p
    | .anonymous => none

def opts : Options := ({} : Options)
  |>.setBool `autoImplicit false
  |>.setBool `relaxedAutoImplicit false
  |>.setBool `Elab.async false
  |>.setBool `linter.all false

def mathlibPass (env : Environment) (namesPath out : String) : IO Unit := do
  let lines ← IO.FS.lines namesPath
  let names := lines.foldl (fun s l => if l.isEmpty then s else s.insert l.toName) ({} : NameSet)
  let h ← IO.FS.Handle.mk (out ++ "/mathlib.jsonl") .write
  let modNames := env.header.moduleNames
  let modOf (c : Name) : Option Name := (env.getModuleIdxFor? c).map fun i => modNames[i.toNat]!
  let mut k := 0
  for (n, ci) in env.constants.map₁ do
    let .thmInfo tv := ci | continue
    let some m := modOf n | continue
    unless m.getRoot == `Mathlib do continue
    let user := (privateToUserName? n).getD n
    let some parent := sourceParent names user | continue
    let proj := projKey m
    let cx : Gestures.Ctx := {
      env, modOf,
      isLocal := fun c => match modOf c with
        | some mc => projKey mc == proj
        | none => false }
    let r := Gestures.analyse cx n tv.value
      [("m", toJson m.toString), ("p", toJson proj), ("parent", toJson parent.toString)]
    h.putStrLn r.compress
    k := k + 1
    if k % 25000 == 0 then IO.println s!"mathlib theorems: {k}"
  h.flush
  IO.println s!"mathlib done: {k}"

def processModule (env : Environment) (path : String) (mod : Name) :
    IO (Environment × Nat × String) := do
  let src ← IO.FS.readFile path
  let inputCtx := Parser.mkInputContext src path
  let (_, parserState, msgs) ← Parser.parseHeader inputCtx
  let env := env.setMainModule mod
  let cmdState : Command.State :=
    { Command.mkState env msgs opts with infoState := { enabled := false } }
  let (_, st) ← (Frontend.processCommands.run { inputCtx }).run
    { commandState := cmdState, parserState, cmdPos := parserState.pos }
  let errs := st.commandState.messages.toList.filter (·.severity == .error)
  let first ← match errs.head? with
    | some m => m.toString
    | none => pure ""
  return (st.commandState.env, errs.length, first)

def projectPass (env0 : Environment) (out : String) (p : ProjJob) : IO Unit := do
  let mut env := env0
  let mut owner : Std.HashMap Name String := {}
  let logH ← IO.FS.Handle.mk (out ++ "/" ++ p.name ++ ".log.jsonl") .write
  for mj in p.modules do
    let t0 ← IO.monoMsNow
    try
      let (env', nerr, first) ← processModule env mj.path mj.mod.toName
      for (n, _) in env'.constants.map₂.toList do
        unless owner.contains n do owner := owner.insert n mj.mod
      env := env'
      let dt := (← IO.monoMsNow) - t0
      logH.putStrLn (Json.mkObj [("module", toJson mj.mod), ("errors", toJson nerr),
        ("ms", toJson dt), ("first", toJson (first.take 400))]).compress
      IO.println s!"  {mj.mod}: {nerr} errors, {dt} ms"
      (← IO.getStdout).flush
    catch e =>
      logH.putStrLn (Json.mkObj [("module", toJson mj.mod), ("errors", toJson (-1 : Int)),
        ("first", toJson (toString e |>.take 400))]).compress
      IO.println s!"  {mj.mod}: EXCEPTION {e}"
    logH.flush
  let h ← IO.FS.Handle.mk (out ++ "/" ++ p.name ++ ".jsonl") .write
  let modNames := env.header.moduleNames
  let modOf (c : Name) : Option Name := (env.getModuleIdxFor? c).map fun i => modNames[i.toNat]!
  let cx : Gestures.Ctx := { env, modOf, isLocal := fun c => !env.isImportedConst c }
  let mut k := 0
  for (n, m) in owner.toList do
    if let some (.thmInfo tv) := env.find? n then
      h.putStrLn (Gestures.analyse cx n tv.value
        [("m", toJson m), ("p", toJson (projKey m.toName))]).compress
      k := k + 1
  h.flush
  IO.println s!"{p.name}: {k} theorems extracted"

def main (args : List String) : IO UInt32 := do
  let job ← IO.ofExcept <| (Json.parse (← IO.FS.readFile args[0]!)) >>= fromJson? (α := Job)
  let leanBin := (← IO.getEnv "LEAN_BIN").getD "lean"
  initSearchPath (← findSysroot leanBin)
  unsafe enableInitializersExecution
  let t0 ← IO.monoMsNow
  let env0 ← importModules (job.imports.map fun s => { module := s.toName }) opts
    (trustLevel := 1024) (loadExts := true) (leakEnv := true)
  IO.println s!"imported {job.imports} in {(← IO.monoMsNow) - t0} ms"
  (← IO.getStdout).flush
  if job.mathlibNames != "" then
    mathlibPass env0 job.mathlibNames job.out
  for p in job.projects do
    IO.println s!"project {p.name} ({p.modules.size} modules)"
    (← IO.getStdout).flush
    projectPass env0 job.out p
  return 0
