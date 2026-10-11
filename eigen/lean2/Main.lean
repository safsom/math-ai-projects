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
  trace : Array String := #[]
  /-- Elaborate each module against exactly its own imports, writing .olean files to `oleanDir`. -/
  isolated : Bool := false
  oleanDir : String := ""
  /-- Isolated mode: exit after this many modules (imports are never freed, so memory grows). -/
  maxModules : Nat := 1000000
  /-- Already compiled projects: modules are imported from `oleanDir` and their theorems read off. -/
  oleanProjects : Array ProjJob := #[]
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

/-- Gesture record of one theorem, with cut statistics when `GESTURE_CUTS=1`. -/
def record (cx : Gestures.Ctx) (n : Name) (v : Expr) (extra : List (String × Json)) : IO Json := do
  let cuts := (← IO.getEnv "GESTURE_CUTS") == some "1"
  return Gestures.analyse cx n v (extra ++ if cuts then Gestures.Cuts.stats cx v else [])

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
    let r ← record cx n tv.value
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
  -- collects messages from the snapshot tree (plain processCommands resets them per command)
  let st ← IO.processCommands inputCtx parserState cmdState
  let errs := st.commandState.messages.toList.filter (·.severity == .error)
  let first ← match errs.head? with
    | some m => m.toString
    | none => pure ""
  return (st.commandState.env, errs.length, first)

def projectPass (env0 : Environment) (out : String) (p : ProjJob) (traceNames : Array String := #[]) : IO Unit := do
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
      h.putStrLn (← record cx n tv.value
        [("m", toJson m), ("p", toJson (projKey m.toName))]).compress
      k := k + 1
  h.flush
  let th ← IO.FS.Handle.mk (out ++ "/" ++ p.name ++ ".trace.jsonl") .write
  for s in traceNames do
    if let some (.thmInfo tv) := env.find? s.toName then
      th.putStrLn (Json.mkObj [("n", toJson s), ("tree", Gestures.trace cx tv.value)]).compress
  th.flush
  IO.println s!"{p.name}: {k} theorems extracted"

/-- Like `processModule`, but the environment is built from the module's own header, as `lake` would. -/
def processModuleIsolated (path : String) (mod : Name) (oleanDir : System.FilePath) :
    IO (Environment × Nat × String) := do
  let src ← IO.FS.readFile path
  let inputCtx := Parser.mkInputContext src path
  let (header, parserState, msgs) ← Parser.parseHeader inputCtx
  unsafe enableInitializersExecution  -- elaboration clears the flag
  let (env, msgs) ← Elab.processHeader header opts msgs inputCtx (trustLevel := 1024) (mainModule := mod)
  for msg in msgs.toList do
    if msg.severity == .error then IO.eprintln s!"header {mod}: {← msg.toString}"
  let cmdState : Command.State :=
    { Command.mkState env msgs opts with infoState := { enabled := false } }
  IO.eprintln "[phase] header done"
  let st ← IO.processCommands inputCtx parserState cmdState
  IO.eprintln "[phase] elab done"
  let env := st.commandState.env
  let errs := st.commandState.messages.toList.filter (·.severity == .error)
  let first ← match errs.head? with
    | some m => m.toString
    | none => pure ""
  let fname := mod.components.foldl (fun p c => p / c.toString) oleanDir |>.addExtension "olean"
  if let some dir := fname.parent then IO.FS.createDirAll dir
  writeModule env fname
  IO.eprintln "[phase] olean written"
  return (env, errs.length, first)

def projectPassIsolated (out : String) (oleanDir : System.FilePath) (p : ProjJob)
    (traceNames : Array String := #[]) (budget : IO.Ref Nat) : IO Unit := do
  -- resumable: modules already in the log are done (the wrapper drops output of unfinished ones)
  let logPath := out ++ "/" ++ p.name ++ ".log.jsonl"
  let mut done : Std.HashSet String := {}
  if ← System.FilePath.pathExists logPath then
    for l in ← IO.FS.lines logPath do
      if let .ok j := Json.parse l then
        if let .ok s := j.getObjValAs? String "module" then done := done.insert s
  let logH ← IO.FS.Handle.mk logPath .append
  let h ← IO.FS.Handle.mk (out ++ "/" ++ p.name ++ ".jsonl") .append
  let th ← IO.FS.Handle.mk (out ++ "/" ++ p.name ++ ".trace.jsonl") .append
  let mut k := 0
  for mj in p.modules do
    if done.contains mj.mod then continue
    if (← budget.get) == 0 then
      IO.println "module budget spent; exiting for a fresh process"
      IO.Process.exit 3
    budget.modify (· - 1)
    let t0 ← IO.monoMsNow
    try
      let mod := mj.mod.toName
      let (env, nerr, first) ← processModuleIsolated mj.path mod oleanDir
      let modNames := env.header.moduleNames
      let modOf (c : Name) : Option Name := (env.getModuleIdxFor? c).map fun i => modNames[i.toNat]!
      let root := mod.getRoot
      let isLoc : Name → Bool := fun c =>
        match modOf c with
        | some mc => mc.getRoot == root
        | none => true
      let cx : Gestures.Ctx := { env, modOf, isLocal := isLoc }
      for (n, ci) in env.constants.map₂.toList do
        if let .thmInfo tv := ci then
          h.putStrLn (← record cx n tv.value
            [("m", toJson mj.mod), ("p", toJson (projKey mod))]).compress
          k := k + 1
          if traceNames.contains n.toString then
            th.putStrLn (Json.mkObj [("n", toJson n.toString), ("tree", Gestures.trace cx tv.value)]).compress
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
    h.flush
  th.flush
  IO.println s!"{p.name}: {k} theorems extracted"

def oleanPass (env : Environment) (out : String) (p : ProjJob) : IO Unit := do
  let mods : NameSet := p.modules.foldl (fun s m => s.insert m.mod.toName) {}
  let modNames := env.header.moduleNames
  let modOf (c : Name) : Option Name := (env.getModuleIdxFor? c).map fun i => modNames[i.toNat]!
  let h ← IO.FS.Handle.mk (out ++ "/" ++ p.name ++ ".jsonl") .write
  let mut k := 0
  for (n, ci) in env.constants.map₁ do
    let .thmInfo tv := ci | continue
    let some m := modOf n | continue
    unless mods.contains m do continue
    let root := m.getRoot
    let cx : Gestures.Ctx := { env, modOf, isLocal := fun c => match modOf c with
      | some mc => mc.getRoot == root
      | none => true }
    h.putStrLn (← record cx n tv.value [("m", toJson m.toString), ("p", toJson p.name)]).compress
    k := k + 1
  h.flush
  IO.println s!"{p.name}: {k} theorems read from oleans"

def main (args : List String) : IO UInt32 := do
  let job ← IO.ofExcept <| (Json.parse (← IO.FS.readFile args[0]!)) >>= fromJson? (α := Job)
  let leanBin := (← IO.getEnv "LEAN_BIN").getD "lean"
  initSearchPath (← findSysroot leanBin)
  unsafe enableInitializersExecution
  if job.isolated then
    let od : System.FilePath := job.oleanDir
    IO.FS.createDirAll od
    -- project modules are imported from their freshly written .olean files
    searchPathRef.modify (od :: ·)
    let budget ← IO.mkRef job.maxModules
    for p in job.projects do
      IO.println s!"project {p.name} ({p.modules.size} modules, isolated)"
      (← IO.getStdout).flush
      projectPassIsolated job.out od p job.trace budget
    return 0
  if job.oleanDir != "" && !job.oleanProjects.isEmpty then
    searchPathRef.modify ((job.oleanDir : System.FilePath) :: ·)
  let t0 ← IO.monoMsNow
  let env0 ← importModules (job.imports.map fun s => { module := s.toName }) opts
    (trustLevel := 1024) (loadExts := true) (leakEnv := true)
  IO.println s!"imported {job.imports} in {(← IO.monoMsNow) - t0} ms"
  (← IO.getStdout).flush
  if job.mathlibNames != "" then
    mathlibPass env0 job.mathlibNames job.out
  for p in job.oleanProjects do
    oleanPass env0 job.out p
  -- traces of chosen mathlib theorems
  let th ← IO.FS.Handle.mk (job.out ++ "/trace_mathlib.jsonl") .write
  let modNames := env0.header.moduleNames
  let modOf (c : Name) : Option Name := (env0.getModuleIdxFor? c).map fun i => modNames[i.toNat]!
  for s in job.trace do
    let n := s.toName
    if let some (.thmInfo tv) := env0.find? n then
      let proj := match modOf n with | some m => projKey m | none => ""
      let isLoc : Name → Bool := fun c =>
        match modOf c with
        | some mc => projKey mc == proj
        | none => false
      let cx : Gestures.Ctx := { env := env0, modOf := modOf, isLocal := isLoc }
      th.putStrLn (Json.mkObj [("n", toJson s), ("tree", Gestures.trace cx tv.value)]).compress
  th.flush
  for p in job.projects do
    IO.println s!"project {p.name} ({p.modules.size} modules)"
    (← IO.getStdout).flush
    projectPass env0 job.out p job.trace
  return 0
