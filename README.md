# RapidMeta — Evidence Paper Studio (pilot)

A **standalone pilot** that adds an **Evidence Paper Studio** to a single RapidMeta
dashboard (finerenone in CKD + type 2 diabetes), without touching the shared
`rapidmeta-kit` template. Built from `rapidmeta-kit/configs/example_finerenone_ckd.json`.

> RapidMeta fills the evidence. The student writes the meaning.

## What it is

A new **"7. Paper Studio"** tab inside the existing single-file dashboard. It turns a
finished rapid meta-analysis into a short, readable evidence paper that the student
completes and exports as a clean PDF.

- **Auto-filled** from the live analysis: PICO, methods skeleton, effect estimate + CI,
  I²/τ², prediction interval, study/participant counts, GRADE certainty (best-effort).
- **Student-authored** (scaffolded with prompts + word targets): introduction, figure
  captions, forest/heterogeneity/certainty interpretation, discussion, conclusion.
- **Embedded figures** cloned from the analysis (PRISMA, forest, GRADE SoF, funnel) —
  Plotly plots are captured to sized PNGs so they render even from a hidden tab.
- **Learning links** ("What is a forest plot?", heterogeneity, CI, GRADE, …) open a side
  drawer with a short explanation, a common-mistake note, and a link into the live
  **Synthesis Course Collection** (`https://mahmood726-cyber.github.io/synthesis-courses/`):
  each topic deep-links to the most relevant course (methods / GRADE / risk-of-bias /
  publication-bias / advanced). Set a lesson's `url` in `paper-learning-links.js` to point
  at a specific page if per-topic deep-links become available.
- **Readiness checker**: flags missing required text/captions, unresolved placeholders,
  overclaiming, generic phrasing, and short sections; shows a 0–100% readiness score.
- **Two PDF exports** via the browser print path (offline, no library): **Working PDF**
  (keeps prompts/scaffolding) and **Clean PDF** (hides all scaffolding; gated on the
  required fields being complete).
- **Guidance for first-time writers** — a dismissible "Start here" onboarding card, a
  plain-language 💡 helper note under every section ("what goes here / how to write it"),
  good-vs-vague worked examples on the hard sections, `?` hover-tooltips on labels and the
  toolbar, and a **Hide tips** toggle for confident users. All guidance is `no-clean-pdf`
  (never appears in the exported paper) and never alters the student's text.
- **Methods & Results format control** — per-section **length** (keep present size / moderately
  longer / much longer) and **journal style** (Generic / Cochrane / JAMA / BMJ / PLOS / Lancet)
  that regenerate the auto-written grey prose only (the estimator/CI method are auto-stated in the
  longer formats, so there's no jargon box to fill).
- **Multiple outcomes** — an "Outcomes in this paper" manager: add secondary outcomes
  (name + pooled numbers), each rendered with its own forest, caption and interpretation;
  per-outcome interpretation/caption are required by the gate. The demo seeds two clearly
  **illustrative** secondaries so it's visible immediately.
- **Own forest & funnel plots** (replace the dark cloned images) — legible white theme,
  per-study CIs + pooled diamond + **prediction-interval bar**, and an **adjustable x-axis
  range** on every plot.
- **Export formats** (all offline, no libraries): **Word (.doc)**, **HTML**, **Markdown**,
  **plain text**; **figures as PNG / JPEG / SVG / TIFF** (hand-rolled TIFF encoder); and two
  **submission modes** — one combined **PDF**, or a **manuscript+figures `.zip`** (text,
  each figure file, figure-legends, and the supplementary checklists), via a hand-rolled
  store-only ZIP writer.
- **Submittable supplementary** — **PRISMA 2020** checklist, **AMSTAR-2** appraisal, and a
  **search-strategy** supplement, downloadable individually and bundled in the `.zip`.
- **Full transparency appendix (`.zip`)** — harvests everything RapidMeta produced so nothing
  is wasted: **every screened record with its full abstract + a link**, the **complete
  statistical results** (+ per-study data), the **R code and R output** to reproduce it, the
  GRADE/SoF tables, **every chart in the dashboard** as images (PNG/JPEG/SVG/TIFF), plus the
  PRISMA/AMSTAR/search supplements — all in one package.
- **Disclosures that stay in the final PDF** — automated-tool/AI-use statement, data
  provenance, and student-completed registration / funding / competing-interests (required).
- **Autosave** to `localStorage` + JSON save/load + reset, plus **pagehide flush**,
  **cross-window** change warning, a **PII notice**, and **"Clear all (shared PC)"**.
- **Build references from included studies** (opt-in button in the References section):
  emits one numbered Vancouver-style line per *included* trial, assembled **only** from
  stored identifiers (`authors`, `title`, `journal`, `year`, NCT, `pmid`, `doi`) — absent
  fields are omitted, nothing is invented, and **no LLM** is involved. It is only as correct
  as RapidMeta's extracted data, so the output is labelled "verify every PMID/DOI before
  submission." (Per the portfolio's citation-misattribution lessons: identifiers are evidence;
  the narrative is the student's.)

## Files added (the only changes vs a stock kit build)

```
assets/css/paper-studio.css
assets/js/paper-studio.js            core: state, autofill, render, figures, modes, autosave
assets/js/paper-learning-links.js    lesson cards + drawer
assets/js/paper-readiness-checks.js  readiness/overclaim/placeholder checks
assets/js/paper-export.js            clean/working PDF via window.print()
index.html                           +CSS link, +tab button, +#tab-paper section, +drawer/toast/scripts
```

Plus one pre-existing-issue fix in `index.html`: the bundled `plotly.min.js` `integrity`
hash did not match the file, which blocked Plotly when served from `file://`. SRI was
removed for that local same-origin asset. (Worth reporting upstream to `rapidmeta-kit`.)

## Run / verify

Open `index.html` in a browser (works offline). For numbers to auto-fill, complete the
analysis first (Screening → Extraction → Analysis Suite) — the Paper Studio reads
`RapidMeta.state.results`.

Headless regression test (Selenium, auto-driver):

```
python verify_paper_studio.py      # 82/82 checks
```

## Multi-person review fixes applied

A 5-lens review was run on the pilot; both P0s and all P1s were fixed and are now
regression-tested:
- **P0-1** Studio now initialises via `switchTab('paper')` (keyboard/reload/click), not click-only.
- **P0-2** Continuous (mean-difference) outcomes autofill correctly — labelled "mean difference",
  I² read from `I2`/`i2`, `confLevel` normalised (0.95→95%), CI rounded; an impossible
  "RR = −2.40" can no longer be emitted.
- **P1s** wire-once listeners (no leak); figure embedding gates host re-runs + bounded poll;
  readiness gate is load-bearing (word floors block the Clean PDF; cover finding + "least
  confident" reflection required); GRADE read from the badge class, not first-word scrape;
  overclaim detection is word-boundary; Working PDF keeps scaffolding; drawer has a focus
  trap + return-focus + inert background; checklist status is text+glyph (not colour-only).

## Known pilot limitations

- Number autofill requires a completed analysis (`RapidMeta.state.results`); PICO and the
  methods skeleton fill immediately.
- Risk-of-bias and study-characteristics figure slots show a placeholder unless a
  matching source element is present in the dashboard.
- Benchmark JSON `fetch()` is blocked under `file://` (CORS) — a pre-existing base-kit
  trait; serve over http / GitHub Pages to silence it. It does not affect Paper Studio.
- PDF export uses the print dialog ("Save as PDF"), matching the base app's own report
  export. No PDF library is bundled, so it stays fully offline.
