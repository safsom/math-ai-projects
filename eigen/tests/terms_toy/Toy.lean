def Imp (p q : Prop) : Prop := p → q
theorem t_share (p q : Prop) (hp : p) (hq : q) : (p ∧ q) ∧ (p ∧ q) :=
  have h : p ∧ q := And.intro hp hq; And.intro h h
theorem t_cse (p q : Prop) (hp : p) (hq : q) : (p ∧ q) ∧ (p ∧ q) :=
  And.intro (And.intro hp hq) (And.intro hp hq)
theorem t_cse3 (p q : Prop) (hp : p) (hq : q) : ((p ∧ q) ∧ (p ∧ q)) ∧ (p ∧ q) :=
  And.intro (And.intro (And.intro hp hq) (And.intro hp hq)) (And.intro hp hq)
theorem t_res (p : Prop) (hp : p) : (p ∧ p) ∧ (p ∧ p) :=
  have f : p → p ∧ p := fun h => And.intro h h; And.intro (f hp) (f hp)
theorem t_inst (p : Prop) (hp : p) : p ∧ p :=
  have g : ∀ _n : Nat, p := fun _ => hp; And.intro (g 3) (g 4)
theorem t_unf (p : Prop) (hp : p) : p :=
  have k : Imp p p := fun h => h; k hp
theorem t_prefix (p : Prop) (hp : p) : p :=
  (fun (_n : Nat) (h : p → p) => h hp) 0 (fun x => x)
theorem t_nest (p : Prop) (hp : p) : ((p ∧ p) ∧ (p ∧ p)) ∧ ((p ∧ p) ∧ (p ∧ p)) :=
  have a : p ∧ p := And.intro hp hp
  have b : (p ∧ p) ∧ (p ∧ p) := And.intro a a
  And.intro b b
def MySet (α : Type) : Type := α → Prop
theorem t_setprop (S : MySet Nat) (h0 : S 0) : S 0 :=
  have x : ∀ (_a : S 0), S 0 := fun a => a; x h0
