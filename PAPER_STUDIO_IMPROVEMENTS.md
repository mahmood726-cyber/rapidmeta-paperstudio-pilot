<!-- sentinel:skip-file - planning/spec doc -->
# Paper Studio — UX improvement plan (user feedback 2026-06-09)

## STATUS — 2026-06-10 (verified, 94/94 Selenium checks GREEN)

**7 of 8 fixes done** (#1, #2, #3, #4, #6, #7, #8). Only **#5 (wizard/stepper)** remains —
deferred to its own session per the plan (largest, structural). The four hard bugs were
each reproduced in a real headless browser first, which **overturned three of the plan's
hypotheses below**; the build features (#3/#6/#7) were screenshot-verified.

Added this session on top of #1/#2/#4/#8:
- **#3 protocol link — DONE.** Added a `studentText.protocolLink` field in Disclosures that
  best-effort-prefills from `RapidMeta.state.protocolUrl` / `<meta name=protocol-url>` (blank in
  the pilot, populated copies can inject it) and shows a live clickable "↗ Open protocol page"
  link only when the value is a real http(s) URL. Optional field — never blocks the gate.
- **#6 more guidance — DONE.** Added "✓ Good / ✗ Too vague" example boxes to the required
  sections that lacked one (abstract background, why-review-needed, eligibility, principal
  finding, least-confident); 13 examples now render.
- **#7 worked example — DONE.** "Show worked example" (in More ▾) opens a **read-only** modal
  with a complete finerenone exemplar across all sections, ESC/focus-return, never touches
  `studentText`. Deliberately read-only (not copy-to-draft): #8's per-box starters cover
  scaffolding, and copying topic-specific prose into a different study is an integrity risk.
  NOTE: the modal mounts on `<body>` outside `#tab-paper`, so the `--paper-*` CSS vars don't
  resolve there — it uses explicit colours (a washed-out-text bug the screenshot caught).

Done earlier this session (**#1, #2, #4, #8**), each reproduced in a real headless browser
first — which **overturned three of the plan's hypotheses below**:

- **#1 full-width — DONE.** Confirmed: the *only* clamp was `.paper-canvas{max-width:920px}`
  (no ancestor competed). Raised `--paper-max-width` to 1280px (canvas now fills ~1011px of a
  1400px screen, vs 920); clean/print export re-caps to 920px (A4). `paper-studio.css:20,~182,~447`.
- **#2 dropdowns "cut off" — DONE.** Root cause was **NOT** native `<select>`s or an
  `overflow:hidden` ancestor (plan guess wrong). The `position:fixed` toolbar `More`/`Advanced
  formats` menus hardcoded `top:54px`, assuming the toolbar sat at the viewport top — but the
  RapidMeta global header pushes the sticky toolbar to y≈230, so the menus floated to the
  screen's top-left corner, detached from their button. Fix: anchor each menu to its summary
  rect via JS on open + reposition on scroll/resize (`paper-studio.js` `wireToolbar`).
- **#4 title not editable — DONE.** The plan's "save-on-input re-renders and wipes focus" is
  **false** (the input handler never re-renders). Real latent cause: an **empty inline
  `contenteditable` collapses to ~12px**, so clicks land on the non-editable `<h1>`/`<figcaption>`.
  Fix (CSS only): `.student-editable:empty{display:inline-block;min-width:14ch}` and the empty
  title becomes a full-width `display:block` so a click anywhere on the title row lands the caret.
- **#8 no way to ACCEPT a suggestion — DONE.** Confirmed: "suggestions" were only CSS
  `:empty::before` placeholders. Added a delegated **"Use this example to start"** button per
  writing box (25 of them) that fills the box with a **clean, gate-safe starter** (NB: raw
  placeholders contain `[condition]`/`___`, which are *blocking* readiness patterns — injecting
  them verbatim would self-block the Clean PDF, so starters are token-free), hides once filled,
  is `.no-clean-pdf` (never exported), and is skipped by the word counter.

Remaining (not started): **#5** wizard/stepper only (largest; deferred to its own session,
on top of the now-stable inputs). See ordered list at the bottom.

---


Captured from live user testing. Codebase is modular:
`index.html` (44k lines, host + tab), `assets/css/paper-studio.css` (styling),
`assets/js/paper-studio.js` (1122 lines — section rendering via `box()` /
`inlineBox()` contenteditable + `renderAll`/`render`), `paper-learning-links.js`
(per-section guidance), `paper-export.js`, `paper-figures.js`, `paper-formats.js`,
`paper-readiness-checks.js`, `paper-supplementary.js`.

> **Verify in a browser after EVERY change** (html-apps rule): the 8 fixes touch
> input handling and layout, which unit tests don't cover. Use the project's
> Selenium/Playwright smoke (35 tests exist per memory) + manual click-through.

## Requirements (with diagnosis + file map)

### 1. Full-screen / full-width
**Problem:** Paper Studio doesn't use the full screen.
**Fix:** in `paper-studio.css`, let the studio container use full viewport width/height
(remove the constraining `max-width`; `width:100%`, `min-height:100vh`, responsive
padding). Check the host tab panel in `index.html` isn't clamping it.

### 2. Dropdowns cut off (don't show all the way down)
**Diagnosis:** a `<select>` (e.g. effect-measure/estimand, `selectBox` ~line 295) or a
custom menu is clipped by an ancestor `overflow:hidden`/fixed height or low `z-index`.
**Fix:** native `<select>` rarely clips (browser-drawn) — so this is likely a custom
dropdown or a container `overflow:hidden` + `max-height`. In `paper-studio.css` set the
scroll container `overflow:visible` where the menu opens, or raise the menu `z-index` and
allow `overflow:auto` with adequate height. Reproduce first to confirm which dropdown.

### 3. Link to the GitHub timestamped protocol
**Context:** each RapidMeta publishes its protocol to GitHub (timestamped) — the paper
should link to it. **Fix:** add a "Registered protocol" field (a URL input) in the
cover/methods section (`paper-studio.js`), defaulting to the host dashboard's GitHub
Pages protocol URL when available (read from `RapidMeta.state`/page metadata), rendered
as a clickable link in the export (`paper-export.js`). Validate it's a real URL.

### 4. Can't write in some sections (e.g. title)
**Diagnosis:** title is an `inlineBox`/contenteditable (line 257, 370 "Click the
highlighted title to edit it"). If unclickable, an overlay (helper text, figure, or a
non-`pointer-events` layer) is sitting over it, OR the element gets re-rendered on input
(losing focus). **Fix:** ensure the title contenteditable has `pointer-events:auto`, is
not re-rendered on each keystroke (debounce/save without full re-render — see #8), and no
sibling overlaps it. Repro + fix the specific section(s).

### 5. Progressive disclosure — one section at a time (wizard)
**Problem:** showing all 21 sections at once scares users.
**Fix:** add a stepper in `paper-studio.js`: keep the section renderers but show ONE
section (or a small group) at a time with Back/Next + a progress bar ("Step 3 of 21 —
Methods"). Persist current step in state. Keep an "show all / outline" toggle for power
users. This is the largest change — the section renderers already exist; wrap them in a
`renderStep(i)` instead of `renderAll()`.

### 6. More guidance + examples per section
**Problem:** unclear what to write. **Fix:** expand `helper()` text and
`paper-learning-links.js` with, per section: a one-line "what goes here", a filled
EXAMPLE sentence, and 1–2 common mistakes. Keep examples in `[square brackets]`
placeholder style already used (line 370).

### 7. Show a full worked example paper (on demand)
**Fix:** add a "Show worked example" button that loads a complete example object into a
READ-ONLY preview (not the user's draft), e.g. a finished finerenone/obesity paper across
all 21 sections, with a "clear example" / "copy a section into my draft" affordance. Store
the example as a JSON constant; never overwrite the user's `studentText` silently.

### 8. Suggestions: no way to ACCEPT; typing deletes the suggestion
**Diagnosis (root cause):** suggestions are currently shown only as a CSS
`data-placeholder` on empty contenteditable boxes (`box()`/`inlineBox()`, lines 236/259) —
greyed example text that vanishes on focus/typing and can never be "kept". There is no
accept mechanism.
**Fix:** render each suggestion as a small chip/banner beside the box with an **"Use this"**
button that sets the box's content to the suggestion (then user edits freely); typing
without accepting leaves the box empty (placeholder behaviour unchanged). NEVER store the
placeholder as the value. Pairs with #4: save-on-input must not re-render and wipe what
was just accepted (update state, not innerHTML, on `input`).

## Suggested order (smallest-blast-radius first)
1. #1 full-screen + #2 dropdown (CSS only, low risk)
2. #4 + #8 input/suggestion handling (the core bug; fix save-on-input re-render + add
   "Use this") — highest user impact
3. #6 guidance/examples (content)
4. #3 GitHub protocol link
5. #7 worked-example preview
6. #5 wizard/stepper (largest; do last, on top of stable inputs)

## Propagation note
Per [[paperstudio-const-rapidmeta-bridge]], Paper Studio was injected into living-meta
dashboards via an inline RM-BRIDGE. Fixes proven here in the pilot must then be propagated
to those copies (and headless-smoke verified — structural checks alone miss the bridge).
