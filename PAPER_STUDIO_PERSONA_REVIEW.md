<!-- sentinel:skip-file - planning/design-decision doc -->
# Paper Studio — multi-persona UX review (2026-06-10)

> **BUILD STATUS** (owner chose the full roadmap B → C+gate → A → D):
> - **B — left section navigator: DONE** (2026-06-10). 21 sections in 7 groups, accessible
>   `<nav>` + roving-tabindex + AT state labels + click-to-focus + skip-link; mobile collapses
>   to a tappable drawer with 44px targets. Verifier 95/95 → 100/100. The feared ~70px mobile
>   writing width did NOT reproduce — a column-stack at ≤1024px already existed (persona claim
>   of "no collapse below 640px" was wrong; there is a 1024px rule).
> - **Substantive gate upgrade (P0): DONE** (commit 15dd586). 4a anti-duplication (an unedited
>    example starter, ≥90% Levenshtein-identical, is blocking) + 4b significance-vs-null (cannot
>   claim "significant" when the CI crosses the no-effect line). 101 checks.
> - **C — one-section wizard: DONE** (2026-06-10). Owner chose the **hybrid** step size: section
>   steps with Results split into its parts (16 steps total). Post-render transform groups the
>   canvas at each H2/H3; Back/Next move focus to the heading + aria-live announce; real
>   progressbar; persisted "Show all" escape hatch; nav-jump switches steps; never hard-locks
>   Next; figures resize on reveal; export/preview/print force the whole paper (no truncated PDF).
>   Default ON for first-timers (empty draft). Verifier 101 → 107.
> - **A — focus mode: DONE** (ffd0fff). CSS full-screen (not the Fullscreen API): a toggle hides
>   the host chrome (banner/header/tabs) via display:none (removes them from tab order + a11y
>   tree); Esc exits + returns focus; persistent provenance strip; not persisted across reload.
> - **D — story-based teaching: DONE** (892327c). Label dropped (codebase confirmed secular);
>   3 real/named/sourced trial cases (CRASH, ISIS-4, Turner-FDA) each ending on a number + a
>   method rule, collapsed/optional/export-clean, hidden by "Hide tips".
> - **ROADMAP COMPLETE** (B, gate, C, A, D). Verifier **111/111**. Branch `paper-studio-ux-fixes`,
>   NOT pushed. Deferred (optional polish): the post-Results coherence checkpoint and the
>   mandatory whole-paper read-through step (anti-fragmentation) on top of this stable base.


Six target-user personas evaluated four proposed features before any build, per the
product owner's request ("do the multi-persona review first, then decide if these ideas
are the best ones"). Personas: **Amina** (anxious first-time author, ESL, East Africa),
**Carlos** (non-native English postgrad), **Dr. Osei** (supervisor who marks ~40 papers),
**Priya** (screen-reader + keyboard-only, low vision), **Sam** (mid-range Android, low
bandwidth), **Dr. Lin** (research-integrity methodologist). Run as a workflow (6 persona
agents + 1 synthesis).

## Verdict matrix

| Feature | Amina | Carlos | Osei | Priya | Sam | Lin | Overall |
|---|---|---|---|---|---|---|---|
| **A — Full-screen / focus mode** | nice | should | should | should | should | should | **Build w/ conditions (low priority)** |
| **B — Left section navigator** | should | should | **must** | **must** | should | **must** | **Build (highest-confidence, lowest-risk)** |
| **C — One-section wizard (default)** | **must** | **must** | should | should | **must** | should | **Build w/ conditions (highest user-impact)** |
| **D — "Quranic-style" secular teaching** | should | nice | nice | nice | nice | nice | **Techniques YES, drop the label** |

Zero "drop"/"would-harm" verdicts — the disagreement is about **priority and guardrails**,
not whether. But the single highest-leverage change is **none of A–D** (see below).

## Recommended build order: B → (gate upgrade + C) → A → D

### B — Grouped left section navigator  *(do first)*
Helps a beginner and a screen-reader user with no trade-off, teaches paper anatomy, and
**fixes a real shipping bug**: the sidebar is hardcoded `flex:0 0 290px` with **no collapse
rule below 640px** — on a 360px phone that crushes writing width to ~70px.
- Real `<nav>` + `<button>`/`<a>` list; status as **text+glyph, not colour** (`aria-label="Methods — complete"`); `aria-current="step"`; activating an item **moves focus** into the section; roving tabindex (one tab-stop, not 21); "Skip to writing" link.
- "Done" reflects the **substantive gate**, not "box non-empty".
- Collapse the 21 into ~8 IMRaD groups; label by job ("Results — what the numbers mean").
- **Mobile (hard req):** `@media (max-width:~700px)` turns the rail into a top/slide-out drawer; 44px targets.

### C — One-section wizard, default for first-timers  *(do with the gate upgrade, not before)*
The three real target users (Amina/Carlos/Sam) say the 21-section scroll is *the* reason a
beginner quits; the two experts warn a blindfold wizard makes 21 disconnected fragments and
a frictionless duplicate-paper rail. Resolution:
- **Default** one-at-a-time only for first-timers (empty draft); returning/revising users keep last view.
- **Escape hatches (all mandatory):** persisted "Show all/outline" toggle; **never hard-lock Next** (gate only at final PDF); non-linear jump via the nav.
- **Anti-fragmentation:** step labels name the job + grouped ("Methods 2 of 4"); a **coherence checkpoint** after Results (show the objective beside the result); a **mandatory whole-paper read-through** in reading view before the PDF gate.
- **Anti-duplication:** in wizard mode, **require a typed attempt before the "Use this example" starter is offered**; flag sections ≥90% identical to the starter.
- **A11y (non-negotiable):** Back/Next move focus to the new heading + `aria-live` "Step 4 of 21, Methods"; real `<progressbar>`; respect `prefers-reduced-motion`; **test with assistive tech, not click-through**.
- **Persist current step** in localStorage (resume after reload / phone switch).
- Warm phrasing: "21 short steps — most finish one in a few minutes" + one reassurance line/step.

### ★ Substantive gate upgrade  *(P0 — the actual highest-leverage change; peer of C)*
**Not one of A–D, but the review's #1 finding.** Today's gate checks word-floor +
placeholder-absence + overclaim phrases — satisfiable by fluent-but-empty text. **The wizard
built on this gate is a duplicate-paper machine.** Deterministic (no LLM) upgrade:
- interpretation **direction matches this analysis**; no significance claim when the CI crosses null; mentions the actual I² band; no causal claim from observational pooling;
- per-statistic **"say it in your own words"** micro-prompt for each auto-filled number;
- refuse to let an **unedited starter** (≥90% identical) satisfy the gate.

### A — Full-screen / focus mode  *(ergonomic win, strict rules)*
- **CSS full-width mode, NOT the browser Fullscreen API** (which blacks out OS/SR chrome and traps keyboard users); `<button aria-pressed>` in tab order, icon+word; **Esc always exits**; hidden header `inert`/`aria-hidden`; announce + return focus on exit.
- **Never auto-enter.** On phone, "full-screen" = reclaim **height** (collapse header), not width; hardware Back exits focus mode, not the app.
- **Never hide** per-box prompts, Good/Too-vague boxes, "Use this example", or the readiness panel (flagged as the most harmful possible regression).
- Keep a persistent in-canvas **provenance strip** ("Effect, CI, I², figures auto-filled — view numbers").

### D — Secular story-based teaching  *(ship last; techniques in, label out)*
**Unanimous: adopt the techniques, DROP the "Quranic"/"Quranic-style" label — it must never
appear in any UI, tooltip, doc, OR internal code/feature name.** In a global multi-faith,
secular cohort the label (even with zero religious content) reads as preachy / exclusionary /
appropriative-as-branding; the *techniques* are sound and origin is invisible design
inspiration. Call it **"Story cards" / "plain-language teaching"** to users and engineers.
- **Direct address ("you")**, **rhetorical question-then-answer** — keep (good for ESL + audio/SR).
- **Concrete parables from REAL, NAMED, SOURCED trials** — each names the trial, links evidence, ends on a number + the method point (doubles as a worked example; an unsourced morality tale is exactly what integrity warns against).
- **Memorable/repeated phrasing — sparingly:** every phrase encodes a **method rule** ("always state the prediction interval, not just the CI"), **never a ready-made interpretive sentence about the student's own data** (a cohort-wide duplication vector); repetition rhetorical, **never duplicated DOM nodes** (SR reads twice; ESL find repetition harder).
- **Optional + dismissible always:** collapsed-by-default `<button aria-expanded>`; persisted global "Hide tips"; never blocks a step or gate; short + text-only for mobile/bandwidth; offer a register-neutral one-line alternative beside each card.

## Other high-value features that recurred (ranked)
1. **Substantive readiness gate** (above) — P0, biggest lever against templated papers.
2. **Per-statistic "say it in your own words"** micro-prompt.
3. **Robust VISIBLE offline autosave + resume** ("Saved on this phone", survive reload/drop).
4. **Anti-duplication / originality surfacing** (≥90%-identical flag + nudge).
5. **ESL phrase-bank / sentence-frames + "fix my grammar, not my meaning" helper.**
6. **True mobile-first pass** (44px, no h-scroll, the 290px collapse) — test on a real ~360px Android.
7. **Glossary openable anywhere** + reassurance that simple English is fine.
8. **Show the finished worked example FIRST** ("here's what you're building") + a time expectation.
9. **Supervisor authorship-breakdown view/export** (student-authored vs starter-derived vs auto-filled).
10. **"Defend it" / viva-readiness prompt** per interpretation.
11. **Reference-verification tick-gate** before References counts as done.

## Top risks to flag before building
1. **Gate measures completion, not comprehension — and none of A–D fix it.** Building C on this gate **worsens** the duplicate-paper risk. Ship the gate upgrade as a precondition.
2. **Cohort homogeneity / integrity exposure:** same analysis + same starters + same worked example + stepper → 40 near-duplicate papers.
3. **Concrete mobile bug already in code:** sidebar `flex:0 0 290px`, no collapse <640px; Fix #1 tuned for 1920px → ~70px writing width on a 360px phone. Test on real hardware.
4. **A11y regressions concentrate in A and C** (focus traps, content swapped without focus-move/announce, Fullscreen-API blackout). Test with AT.
5. **The "Quranic-style" label is an inclusion/reputational landmine** even with zero religious content — strip the name everywhere, incl. internal code.
6. **Auto-filled numbers defended by nobody** + certainty is best-effort → pair every stat with a "check this is right" nudge.

## Bottom line
Build **B now** (lowest risk, universal benefit, fixes the mobile bug). Build **C as the
first-timer default but only behind the §C guardrails and the substantive-gate upgrade** —
the wizard without the gate fix is a duplicate-paper machine. **A** is a solid ergonomic win
with strict a11y/mobile rules. **D**'s techniques are welcome, but ship last, **label-free**,
optional, and short. The highest-leverage single investment is **not any of A–D — it is
making the gate check *thinking***, which is what makes the studio teach rather than
templatise.
