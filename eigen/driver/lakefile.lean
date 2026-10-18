import Lake
open Lake DSL

package gestures

lean_lib Gestures where
  roots := #[`Gestures, `Terms]

@[default_target]
lean_exe gestures where
  root := `Main
  supportInterpreter := true
