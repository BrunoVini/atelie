# Capability: Refine — named moves on an artifact that already exists

Refine is the opposite of a from-scratch build. The surface is already on screen and
already on the contract; the job is a *named, bounded* move on it — louder, calmer,
leaner, harder, one earned moment of craft — without breaking what already works. Reach
here when the user says "make it pop", "tone it down", "simplify this", "handle the empty
state", "polish it" — they are pointing at an existing element and asking for a verb, not
a redesign.

Every move below is **contract-bound**. It pushes within the palette, the spacing/radius
scales, the motion budget, and the a11y floor the project already declares — never around
them. That is what lets atelier offer these as live, instant variants (see *The live
loop* at the bottom): the moves can only land on values the contract already permits, so
a refine can't drift the design off-brand the way an open-ended "improve this" would.

**The first move is to identify the register**, because each verb means a different thing
in each. A surface is either **brand** (the design IS the product — landing, marketing,
portfolio) or **product** (the design SERVES a task — app UI, dashboard, settings). Read
`references/registers/brand.md` and `references/registers/product.md`; the gate in SKILL.md
resolves which is active. Brand leans toward distinctiveness; product leans toward clarity.
The same verb pulls in opposite directions across the two, and applying the brand reading
to a product surface (or vice-versa) is the most common way a refine misfires.

Across every move, three things are **never** on the table: the contract (palette, scales,
fonts, depth strategy), the design laws in `references/design-laws.md`, and the
accessibility floor (AA contrast, visible focus, reduced-motion, keyboard reach). A move
that would break any of those is not the move — find the version that respects them.

---

## bolder / quieter — push or pull the visual weight (intensity ±)

These are a matched pair on one axis: how much the surface *asserts itself*. They share
machinery (the live `range` and `steps` modes drive both), so think of them together.

**bolder — what it changes.** More commitment: stronger hierarchy, a more decisive type
contrast, one sharper accent, more committed density. It amplifies what's already there;
it does not bolt on effects.

**bolder — what it must NOT break.** Bold is not "more effects." Reject the reflex tells
the moment they surface — a purple-blue gradient, glassmorphism, a neon accent, gradient
text on a metric. Those read as *generated*, the opposite of bold (`slop_check.py` /
`slop_ported.py` will flag the worst of them; don't wait for the flag). Body text stays
readable, contrast stays at AA, and not everything goes bold at once — bold needs
something quiet to push against, or nothing reads as loud.

**quieter — what it changes.** Less intensity: a more restrained use of the palette,
fewer competing weights, more breathing room, less decorative motion. Subtlety needs
precision — quiet without intent collapses into generic, which is its own failure.

**quieter — what it must NOT break.** Quiet is not grayscale and not "everything the same
size." Hierarchy survives the cut; the point of view survives the cut. Don't strip the
surface of all character chasing calm — `quieter` that lands on a faceless page has
overshot.

**By register.**
- **brand:** bolder means *distinctive* — extreme scale, an unexpected committed color,
  a typographic risk that's still legible. quieter means a more restrained palette and
  more typographic air, drama reduced but the POV intact — never erased.
- **product:** bolder rarely means theatrics (they undermine trust); it means clearer
  hierarchy, sharper weight contrast, more committed density — the amplification is in
  clarity. quieter means reducing visual noise so the tool disappears further into the
  task: fewer background accents, flatter cards, less color, less motion.

---

## distill — remove until only the load-bearing elements remain

**What it changes.** A ruthless edit. Cut redundant elements, repeated information,
decorative noise, cosmetic complexity, and structural nesting that earns nothing. The
target is the 20% of the surface that carries 80% of its job, expressed cleanly: one
primary action, a flatter structure, one spacing rhythm, fewer type sizes, no card nested
inside a card. Saint-Exupéry's test — *perfection is when there is nothing left to take
away* — is the bar.

**What it must NOT break.** Distill removes obstacles, not features. Necessary
functionality stays reachable; labels and ARIA stay intact (a11y is not noise to cut);
hierarchy is reduced, never flattened to nothing; and a complex domain keeps the
complexity the task genuinely needs — mystery is not minimalism. If you remove an option
or a path, note where it went.

**By register.** **brand:** distill toward a single confident gesture — one focal moment,
maximal air, everything else subordinate; the cut is what makes the remaining move land.
**product:** distill toward task speed — fewer choices, smarter defaults, progressive
disclosure for the rest, ONE obvious next step instead of five competing ones.

---

## harden — make it survive real, imperfect data

A design that only works with perfect data is a demo, not a shippable surface. Harden it
against the inputs reality throws at it.

**What it changes.** The states that placeholder content hides: **empty** (no data yet —
a real empty state, not a blank box), **loading** (skeletons/feedback, never a frozen UI),
**error** (a clear, on-brand failure path with recovery), **long-content** (a 4-line
headline or a 40-character name that must not break the layout), **zero / large numbers**,
and **overflow** (text that wraps or truncates deliberately, flex/grid items that shrink
instead of blowing the container). atelier already generates this matrix — run
`scripts/seed_content.py` for the stress-state manifest (default · empty · loading ·
long_text · error) and render *each* one, not just the happy path (see
`references/capabilities/content.md`).

**What it must NOT break.** Hardening adds resilience without re-theming — the empty and
error states obey the same contract as the happy path (an off-brand error screen is a
regression). Don't trade fixed widths for English-length assumptions; design for text
expansion and RTL. And hardening must not quietly drop the a11y floor: live regions
announce dynamic changes, focus is managed across state transitions, and errors are
conveyed by more than color.

**By register.** **brand:** the hard states are still part of the impression — an empty
or error state on a marketing surface is a chance for voice and craft, not an apology
dialog. **product:** the hard states ARE the product most days; treat empty/loading/error
as first-class screens with the same rigor as the default, because a real user hits them
constantly.

---

## delight — one earned moment of craft

**What it changes.** A single moment where the surface does something a little more than
it had to, at a point that earns it: a success confirmation, a first-time empty state, a
satisfying control, a softened error. One. Delight distributed everywhere reads as noise;
the move is to find the *one* place it pays off and commit there.

**What it must NOT break.** Delight amplifies, it never blocks — it stays under the motion
budget in `references/design-laws.md`: ease-out (quart/quint/expo), **no bounce or
elastic**, animate transform/opacity and never layout properties, and ship a
`@media (prefers-reduced-motion: reduce)` alternative for anything that moves. It never
delays the core task, and it's skippable. And it reads the room — a celebratory flourish
during a critical error, or a wacky tone on a surface that should be calm, is delight
misfired.

**By register.** **brand:** delight can be distributed a little wider — voice in the copy,
a section transition, a discovery reward — personality across the surface. **product:**
delight at specific moments, not pages — completion, a first action, a milestone, error
recovery — while reliability and consistency carry everything in between.

---

## The live loop — these verbs drive the variant engine

Refine is most useful *live*. In the preview (see `references/capabilities/preview.md`),
pick an element and the verbs above become contract-bound variants generated by
`scripts/edit_apply.py` — the stable interface the preview server shells out to. Three
modes back the picker, and **every variant they emit is checked by
`variants_are_on_contract` before it's shown** (an off-contract value is a bug, not a
choice the user gets offered):

- **range** — slide ONE property across its contract scale (e.g. `border-radius` over the
  radius scale, `padding` over the spacing scale). The slider only ever lands on a value
  the scale already declares; this is the continuous form of bolder/quieter on a single
  axis.
  `python3 scripts/edit_apply.py variants --mode range --prop border-radius --n 5 --contract <repo|tokens.json> --current '{"border-radius":"4px"}'`
- **steps** — the discrete named set (Quieter / Bolder / Flatter), the verbs as
  pre-composed takes. `propose_variants` is the legacy single source of truth behind it.
  `python3 scripts/edit_apply.py variants --mode steps --contract <repo|tokens.json> --current '{...}'`
- **toggle** — on/off of a single property (shadow `none` ↔ contract elevation, border
  `none` ↔ `1px solid <contract border>`), returning the two states.
  `python3 scripts/edit_apply.py variants --mode toggle --prop border --contract <repo|tokens.json> --current '{"border":"none"}'`

A run of decisions is a **session**. `session-start` opens one; `accept` writes the chosen
variant into source (the guarded, journaled, reversible `apply_edit` — refuses generated
files, requires a unique anchor, backs up before writing); `reject` records a turned-down
variant with no file change; `manual` records that the user hand-edited a file mid-session
so the log reflects reality. `session-log` prints the run as JSON for the UI or a summary.
`session-commit` will *optionally* `git commit` only the files the session touched, with a
message summarizing the accepted refinements — strictly: a git work tree only, the named
files only (never `git add -A`), and **never a push**. Outside a git repo it returns a
clean `{"ok": false, ...}` rather than crashing, and it is opt-in — accept never commits
on its own.

Nothing in this loop ever leaves the contract, the design laws, or the a11y floor — which
is exactly why a refine is safe to run live and instant.
