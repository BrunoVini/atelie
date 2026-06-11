# Capability: Forms, settings & app-surface craft (restraint + ergonomics)

This is the craft layer for **utility surfaces** — settings/account pages, forms, sign-up
& onboarding flows, wizards, admin panels, tables-with-controls, modals that collect input.
These are *jobs the user came to finish*, not posters they came to admire. Read it whenever
the deliverable is something a user operates rather than reads. Pair it with the universal QA
gates (focus-visible, honest working controls, anti-slop) — those apply here too.

This is a **product**-register surface (the design SERVES the product); see `references/registers/product.md` for the clarity bar and how QA escalates decorative-cost tells here.

The one-line thesis: **a utility surface is judged by how little it makes the user think,
not by how much design it shows.** The senior move is editing *out*, not adding flourish.

## 1. Genre discipline — do NOT design a settings page like a landing page

This is the most common failure, and it's the *inverse* of the landing-page failure. On a
hero you must push ambition; on a utility surface you must **withhold** it. Marketing instincts
applied to a form read as junior, not polished.

- **No poster type.** Heading sizes are functional (a clear `h1`, quiet section headers), not
  a 64px display face. A settings page titled in a dramatic serif looks like it's trying too hard.
  See `../design-laws.md` for the quantified thresholds (and which are auto-checked).
- **Accent is for the ONE primary action, not everywhere.** The save/submit button gets the
  brand color. Avatars, section icons, toggle tracks, kickers, and card borders do **not** each
  get an accent fill — a page where the accent appears 15 times has no primary action at all.
  Tint icons neutral; reserve saturated brand color for the thing you want clicked.
- **Surfaces are calm.** Plain cards or hairline-separated sections on a near-white/near-black
  ground. No gradient panels, no glow, no decorative blobs behind a password field.
- **Restraint is editing, not thinness.** Calm ≠ empty. The craft shows in spacing rhythm,
  alignment, label/control pairing, and consistent control sizing — not in ornament. A page can
  be visually quiet and still obviously expert.

Litmus test: if you screenshot the page and it looks like it wants to *sell* you the product,
you over-designed it. A settings page should look like it respects that you're busy.

## 2. Information architecture — show one concern at a time

The single biggest UX lever on a multi-section settings/admin surface, and where a polished
per-component build can still lose to a plainer one.

- **Don't firehose.** When there are many sections (profile, notifications, security, billing,
  danger zone…), do NOT stack all of them on one infinite scroll. A user who came to toggle one
  setting should not scroll past six unrelated panels. Prefer **tabbed / routed panels that show
  one section at a time** — the Stripe/Linear settings pattern. Short, focused, breathable wins.
- **The nav affordance must match its behavior — don't let it lie.** A sidebar that *highlights
  the active item* reads as tabs and promises "click → that panel replaces this one." If clicking
  actually just anchor-scrolls a giant page, the highlight is dishonest. Pick one and be coherent:
  either real tab panels (one visible at a time, the rest `hidden`, `role="tab"`/`tabpanel`,
  arrow-key support), **or** an in-page scroll-nav styled plainly as a jump list (no tab-like
  active pill implying replacement). Mismatched affordance is a quiet credibility hit.
- **Group within a section by meaning,** with quiet subheads — don't dump 12 fields in one column.
- **Put destructive/rare things last and behind friction** (a "Danger zone" section, a confirm
  step), never adjacent to routine fields where a misclick is costly.
- **An embedded pricing/plan card is not a settings control.** Linking to billing is fine; a full
  marketing pricing card dropped into account settings is genre bleed — it belongs on its own
  Plan & billing panel, summarized, not sold.

## 3. Form ergonomics — the actual work of the page

- **Label every control, visibly and programmatically.** A persistent visible `<label>` tied via
  `for`/`id` (placeholder-as-label fails the moment the field has content). Toggles/switches need
  a real label too — never an unlabeled switch whose meaning lives only in nearby prose.
- **Group related fields and order them the way a human fills them.** Name → email → role, not
  scattered. Use `autocomplete` tokens (`name`, `email`, `current-password`, `new-password`,
  `one-time-code`) so password managers and autofill work — this is craft users feel.
- **Use the right control for the data.** Toggle = instant on/off; checkbox = a choice you submit;
  radio/segmented = one-of-few; select = one-of-many. A toggle that needs a separate Save is a
  contradiction — either it saves on flip (with feedback) or it should be a checkbox in the form.
- **Sensible defaults & required marking.** Mark required fields consistently (an asterisk *with*
  a "* required" legend, not a lone glyph). Pre-fill what you safely know. Don't ask for what you
  can derive.
- **Helper text sits with its field, before the error,** explaining format/why (e.g. "Used for
  sign-in and receipts") — not as a tooltip the user must hunt for.

## 4. State, validation & feedback — the page must respond honestly

- **Validate inline, on blur or submit — not on every keystroke,** and never block typing.
  Show the error *at the field*, in text + an accessible association (`aria-describedby`,
  `aria-invalid`), not color alone. Re-validate and clear the error as the user fixes it.
- **No validation theatre — enforce exactly what the copy promises.** If the helper says "minimum
  10 characters", the submit must actually reject 9. If it's a security surface (password change,
  2FA), do the real checks the UI implies (require + verify the current password before allowing a
  new one). Stating a rule you don't enforce is worse than stating none — it teaches the user the
  form lies. Match the regex/length/required logic to the literal promise on screen.
- **Every control does something or is honestly disabled — no dead affordances.** Secondary
  buttons (Upload, Remove, Manage billing, View invoices, Set up SMS…) and links must either work,
  show a visible stub response (a toast/inline state, like the toggles do), or be `disabled` with a
  reason. Never ship `href="#"` placeholders — they jump-scroll the page and read as broken. A page
  that *looks* fully wired but where most buttons are inert fails the "finish interactions honestly"
  bar (see `landing-craft.md`).
- **Every mutating control has a visible result.** A toggle flips and *shows* it took (state +
  text). A Save shows pending → success/failure. A control that changes nothing visible reads
  as broken — the #1 "is this thing on?" anxiety.
- **A sticky save bar is a real pattern — implement it honestly.** If you use a fixed "you have
  unsaved changes / Save / Discard" bar, it must (a) appear only when the form is actually dirty,
  (b) not occlude the field currently being edited — reserve bottom padding equal to the bar's
  height so the last field clears it, (c) be keyboard-reachable and announced
  (`role="region"` + `aria-live` on appearance), (d) actually wire Discard to reset. A save bar
  that covers the control you just changed is worse than no bar.
- **ONE save affordance per context — never two primary Saves on screen at once.** If a sticky
  bar owns the dirty-state save, the in-card footer must NOT also be a second primary "Save"
  button at the same time (two identical primary buttons = no primary). Pick one pattern per
  panel: either the footer button, or the floating bar — not both lit simultaneously.
- **Verify the save bar at MOBILE width, not just desktop.** A bar that clears the last field at
  1440px often *wraps* on a 390px screen — its buttons stack, its height doubles, and the
  reserved padding (sized for the desktop bar) is now too small, so it occludes the field. Either
  measure the rendered bar height and set the spacer to match at every breakpoint, or dock the
  bar in normal flow (not floating) on narrow screens. Render at 390px and confirm no occlusion.
- **One consistent save model, and signpost it.** Mixing instant-save toggles with
  explicit-save forms is fine, but the user must never have to guess which is which. Give every
  auto-saving section the same visible cue ("Saved automatically") and every explicit-save
  section the same Save affordance — don't let the mental model silently flip tab to tab.
- **Pick ONE explicit-save mechanism for the whole surface — don't mix idioms.** A floating
  dirty "Save changes / Discard" bar and per-panel in-card footer Save buttons are two *different*
  save idioms; using both in one settings area (a bar for Profile, an in-card submit for Security)
  forces the user to learn two patterns and puts two primary-styled Saves in the same document.
  Choose one and apply it to every explicit-save panel: either each panel carries its own in-card
  footer Save (the GitHub-settings idiom — simplest, scales cleanly), OR a single global dirty-bar
  serves all panels. Consistency here is the senior tell.
- **Dangerous actions confirm with proof, not a generic "Are you sure?"** Type-to-confirm
  (the workspace name) for account/data deletion; state exactly what will be lost.
- **Design the empty, loading, disabled, and error states,** not just the happy filled form.
  A disabled Save needs a reason; a loading region needs a placeholder, not a layout jump.

## 4b. Checkout, address & multi-step wizards

- **An address form needs a country field, and validation must follow it.** Don't hard-code a
  US ZIP regex (`^\d{5}$`) — that silently locks out every Canadian (`A1A 1A1`), UK (`SW1A 1AA`),
  and other international buyer, and is the kind of exclusion a senior reviewer catches instantly.
  Include a country selector and make postal-code / state validation country-aware (or at minimum
  accept the common formats and don't fail-hard on non-US input). Use the right `autocomplete`
  tokens (`country-name`, `postal-code`, `address-level1/2`).
- **Seeded data must be internally plausible — match tax to the jurisdiction.** A "Tax (13%)"
  line on an Oregon (0% sales tax) US address reads as Ontario HST pasted onto the wrong country;
  it undermines trust even though the arithmetic is correct. Pick a shipping locale and a tax rate
  that actually go together, and label the tax with its basis.
- **A multi-step stepper must keep its orientation on mobile.** Collapsing the stepper to bare
  numbered dots (hiding every step label) at narrow widths leaves the only "you are here" cue as
  a 30px colored circle — borderline for low-vision users and worse than just keeping at least the
  *current* step's label visible. Show the active step's name on mobile; abbreviate the others if
  space is tight, but don't go label-less.
- **Order math reconciles across every surface** — subtotal = Σ items; total = subtotal + shipping
  + tax; and the sidebar, the review step, the CTA, and the success screen must all show the SAME
  total (surfacing it on the primary button — "Place order · $338.57" — makes the reconciliation
  provable at a glance). See `data-viz-craft.md` for the integrity mindset.

## 5. Accessibility & input is the baseline, not an extra (utility surfaces live or die here)

- **Visible focus on every control** (`:focus-visible`), keyboard-operable everything: tab order
  follows visual order, toggles flip on Space/Enter, tabbed nav supports arrow keys, modals trap
  focus and restore it on close, Esc closes.
- **Touch targets ≥ 44px**, hit areas include the label (clicking the label toggles the control).
- **Don't reorder the DOM for visual columns** in a way that breaks tab order; use grid/layout,
  keep source order logical.
- **Honest ARIA only.** A `role="switch"` needs `aria-checked` kept in sync; a tablist needs
  `aria-selected`; don't sprinkle roles that the JS doesn't maintain.

## 6. Self-QA — operate it, don't just look at it

- **Screenshot it** (`scripts/screenshot.mjs`) and ask the editing question: what can I *remove*?
  Where is accent doing decoration instead of signalling the primary action? Does it look like a
  page that respects the user's time, or one that's showing off?
- **Tab through it** with the keyboard end-to-end; flip a toggle and confirm the state shows and
  the save affordance behaves; trigger a validation error and confirm it's announced and clears.
- **Render at the section boundaries** and confirm the save bar / sticky header never occludes a
  field; with many sections, confirm you're not making the user scroll past unrelated panels.
- Run `slop_check.py` (generic-font / accent-as-default / no-focus-visible) and fix every
  `[important]` finding before shipping.
