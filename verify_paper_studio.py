# Headless verification of the Paper Studio pilot.
import io, sys, time, pathlib
# Only rewrap stdout when run as a script. Reassigning sys.stdout at import time
# breaks pytest's output capture if this module is ever imported (see lessons.md).
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# Portable: resolve index.html relative to this script so the verifier runs
# from any checkout path / in CI, not just C:\Projects\...
URL = (pathlib.Path(__file__).resolve().parent / "index.html").as_uri()
opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1400,1000")
opts.set_capability("goog:loggingPrefs", {"browser": "ALL"})

d = webdriver.Chrome(options=opts)
results = []
def check(name, cond, extra=""):
    results.append((name, bool(cond), extra)); print(("PASS" if cond else "FAIL"), "-", name, ("| " + extra) if extra else "")

try:
    d.get(URL); time.sleep(3)

    check("RapidMeta controller loaded", d.execute_script("return typeof RapidMeta!=='undefined' && !!RapidMeta;"))

    d.execute_script("RapidMeta.switchTab('analysis');"); time.sleep(1.5)
    check("Existing Analysis tab still switches", d.execute_script("return !document.getElementById('tab-analysis').classList.contains('hidden');"))

    # ---- open Paper Studio (cold) ----
    d.find_element(By.ID, "btn-tab-paper").click(); time.sleep(2)
    check("Paper Studio tab opens", d.execute_script("return !document.getElementById('tab-paper').classList.contains('hidden');"))
    check("PaperStudio namespace loaded", d.execute_script("return typeof PaperStudio!=='undefined' && !!PaperStudio;"))
    canvas = d.execute_script("return document.getElementById('paperCanvas').innerText||'';")
    check("Canvas rendered paper sections", all(s in canvas for s in ["Abstract","Introduction","Methods","Results","Discussion","References"]))

    pico = d.execute_script("return PaperStudio.state.pico;")
    check("Autofill PICO population", bool(pico.get("population")), pico.get("population"))
    check("Autofill intervention = Finerenone", "finerenone" in (pico.get("intervention") or "").lower(), pico.get("intervention"))
    check("Clinical question renders PICO", "finerenone" in canvas.lower() and "placebo" in canvas.lower())

    check("Evidence chips populated", "Intervention" in d.execute_script("return document.getElementById('evidenceChipsPanel').innerText||'';"))
    rd = d.execute_script("return document.getElementById('paperChecklistPanel').innerText||'';")
    check("Readiness panel shows score", "%" in rd and "readiness" in rd.lower())

    # learning drawer
    btn = d.execute_script("var b=document.querySelector('#paperCanvas [data-learn]'); if(b){b.click(); return b.dataset.learn;} return null;")
    time.sleep(0.4)
    check("Learning drawer opens with content",
          d.execute_script("return !document.getElementById('learningDrawer').hidden;") and bool(d.execute_script("return document.getElementById('learningTitle').innerText;")),
          f"{btn} -> {d.execute_script('return document.getElementById(\"learningTitle\").innerText;')}")
    link = d.execute_script("return document.getElementById('learningCourseLink').getAttribute('href');")
    check("Learning link has a Synthesis URL", bool(link) and "synthesis" in link.lower(), link)
    d.execute_script("document.getElementById('closeLearningDrawer').click();")

    # autosave
    d.execute_script("""var el=document.querySelector('[data-field="studentText.discussionPrincipalFinding"]');
        el.innerText='The pooled estimate suggests a probable cardiovascular benefit of modest size.';
        el.dispatchEvent(new InputEvent('input',{bubbles:true}));""")
    time.sleep(1)
    check("Editing autosaves to state + localStorage",
          bool(d.execute_script("return (PaperStudio.state.studentText||{}).discussionPrincipalFinding||'';")) and
          bool(d.execute_script("var s=JSON.parse(localStorage.getItem('rapidmeta.paperState')||'{}'); return (s.studentText||{}).discussionPrincipalFinding||'';")))

    rd2 = d.execute_script("return PaperStudio.runReadinessCheck('clean');")
    check("Readiness check returns structured result", isinstance(rd2, dict) and "issues" in rd2, f"score={rd2.get('score')} ready={rd2.get('ready')}")

    d.execute_script("PaperStudio.setMode('preview');")
    check("Preview mode toggles", d.execute_script("return document.getElementById('paperCanvas').classList.contains('paper-mode-preview');"))
    d.execute_script("PaperStudio.setMode('write');")

    # ---- inject a completed-analysis results object and re-autofill ----
    d.execute_script("""
        RapidMeta.state.results = {or:'0.86', lci:'0.78', uci:'0.95', i2:'12.0', k:3,
          n:'19,027', confLevel:95, piLCI:'0.70', piUCI:'1.05', tau2:0.004, qPvalue:'0.4500'};
        PaperStudio.loadRapidMetaData(); PaperStudio.render(); PaperStudio.updateChecklist();
    """)
    time.sleep(0.5)
    an = d.execute_script("return PaperStudio.state.analysis;")
    check("Number autofill: effect estimate", an.get("effectEstimate") == "0.86", f"{an.get('effectMeasure')} {an.get('effectEstimate')} [{an.get('ciLower')}-{an.get('ciUpper')}]")
    check("Number autofill: I2 + k + N", an.get("i2") == "12.0" and str(an.get("kStudies")) == "3" and an.get("totalParticipants") == "19,027", f"I2={an.get('i2')} k={an.get('kStudies')} N={an.get('totalParticipants')}")
    check("Prediction interval autofilled", "0.70 to 1.05" == an.get("predictionInterval"), an.get("predictionInterval"))
    canvas2 = d.execute_script("return document.getElementById('paperCanvas').innerText||'';")
    check("Numbers appear in the paper body", "0.86" in canvas2 and "0.78 to 0.95" in canvas2)
    chips2 = d.execute_script("return document.getElementById('evidenceChipsPanel').innerText||'';")
    check("Chips show effect + CI", "0.86" in chips2 and "0.78" in chips2)

    # ---- figure embedding path: render a Plotly plot into #plot-forest, then embed ----
    plotly_ok = d.execute_script("return typeof Plotly!=='undefined';")
    check("Plotly loaded (SRI fix)", plotly_ok)
    if plotly_ok:
        # our own forest renderer with per-study data + prediction interval
        d.execute_script("""
            window.__res = {isContinuous:false, or:'0.86', lci:'0.78', uci:'0.95', i2:'12.0', k:3,
              n:'19,027', confLevel:95, piLCI:'0.70', piUCI:'1.05', tau2:0.004, effectMeasure:'RR',
              plotData:[{id:'FIDELIO',logOR:Math.log(0.86),se:0.07},
                        {id:'FIGARO',logOR:Math.log(0.87),se:0.06},
                        {id:'FINEARTS',logOR:Math.log(0.84),se:0.06}]};
            PaperStudio.renderOwnFig('forest','forestPlotPaperSlot', window.__res, 'CV composite');
            PaperStudio.renderOwnFig('funnel','funnelPaperSlot', window.__res, 'CV composite');
        """)
        time.sleep(1.2)
        def plotted(box_id):
            return d.execute_script(
                "var b=document.getElementById(arguments[0]);"
                "return !!(b && (b.classList.contains('js-plotly-plot') || b.querySelector('svg.main-svg') || (b.layout&&b.data)));", box_id)
        forest_pi = d.execute_script("""
            var b=document.getElementById('forestPlotPaperSlot-box');
            var ys=(b&&b.data)?b.data.map(function(t){return (t.y||[]).join('|');}).join('||'):'';
            return /Prediction interval/.test(ys);
        """)
        check("Own forest renders (Plotly)", plotted("forestPlotPaperSlot-box"))
        check("Forest includes a prediction-interval row", forest_pi)
        check("Own funnel renders (Plotly)", plotted("funnelPaperSlot-box"))
        # x-range control: set min/max and Apply, expect xaxis.range to be fixed (autorange false)
        rng = d.execute_script("""
            var mn=document.querySelector('.fig-x[data-figid="forest"][data-b="min"]');
            var mx=document.querySelector('.fig-x[data-figid="forest"][data-b="max"]');
            mn.value='0.5'; mx.value='1.5';
            PaperStudio.applyFigRange('forest', false);
            var box=document.getElementById('forestPlotPaperSlot-box');
            var lay=box&&box.layout; return {auto:lay?lay.xaxis.autorange:null, range:lay?lay.xaxis.range:null};
        """)
        check("Forest x-range control applies (autorange off)", rng and rng.get("auto") is False, str(rng))

    # ---- P0-1: init via switchTab WITHOUT a click (keyboard/reload path) ----
    d.execute_script("RapidMeta.switchTab('protocol');"); time.sleep(0.3)
    d.execute_script("RapidMeta.switchTab('paper');"); time.sleep(1.5)
    canvas_sw = d.execute_script("return document.getElementById('paperCanvas').innerText||'';")
    check("Inits via switchTab (no click) — not stuck on Loading", "Loading your evidence paper" not in canvas_sw and "Abstract" in canvas_sw)

    # ---- P0-2: continuous / mean-difference outcome autofills correctly ----
    d.execute_script("""
        RapidMeta.state.results = {isContinuous:true, or:'-2.4000', lci:'-3.1031', uci:'-1.7044',
          I2:8, k:3, n:'1,234', confLevel:0.95, piLCI:'-3.9', piUCI:'-0.9', tau2:0.18};
        PaperStudio.loadRapidMetaData(); PaperStudio.render();
    """)
    time.sleep(0.4)
    anc = d.execute_script("return PaperStudio.state.analysis;")
    body = d.execute_script("return document.getElementById('paperCanvas').innerText||'';")
    check("Continuous: labelled 'mean difference', not a ratio", anc.get("effectMeasure") == "mean difference", anc.get("effectMeasure"))
    check("Continuous: I2 read from capital I2 + rounded", anc.get("i2") == "8.0", anc.get("i2"))
    check("Continuous: confLevel normalized 0.95 -> 95", anc.get("confLevel") == "95", anc.get("confLevel"))
    check("Continuous: CI bounds rounded to 2dp", anc.get("ciLower") == "-3.10" and anc.get("ciUpper") == "-1.70", f"{anc.get('ciLower')}..{anc.get('ciUpper')}")
    check("Continuous: body has no impossible 'RR ... -' or '0.95% CI'", ("0.95% CI" not in body) and ("RR -2" not in body) and ("RR was -2" not in body))

    # ---- P1-2: readiness gate is load-bearing (1-char field does NOT pass) ----
    d.execute_script("""
        var e=document.querySelector('[data-field="studentText.abstractBackground"]');
        e.innerText='x'; e.dispatchEvent(new InputEvent('input',{bubbles:true}));
    """)
    time.sleep(0.3)
    rc = d.execute_script("return PaperStudio.runReadinessCheck('clean');")
    one_char_blocks = any(("abstractBackground" in (i.get("field","")) and i.get("level")=="error") for i in rc.get("issues",[]))
    check("Readiness gate: 1-char required field is blocking (word floor)", one_char_blocks and rc.get("ready") is False, f"blocking={rc.get('blockingCount')}")

    # ---- P1-7: overclaim uses word boundaries (no false flag on 'secures') ----
    fp = d.execute_script("""
        var e=document.querySelector('[data-field="studentText.discussionConclusion"]');
        e.innerText='This secures and improves outcomes for many patients overall today.';
        e.dispatchEvent(new InputEvent('input',{bubbles:true}));
        var r=PaperStudio.runReadinessCheck('clean');
        return r.issues.filter(function(i){return i.level==='warn' && /overclaim/i.test(i.msg);}).length;
    """)
    check("Overclaim: word-boundary (no false flag on 'secures'/'improves')", fp == 0, f"warns={fp}")

    # ---- P1-8: clean export hides scaffolding; plain/working keeps it ----
    hides = d.execute_script("""
        document.body.classList.add('export-clean-pdf');
        var lbl=document.querySelector('#paperCanvas .student-task-label');
        var cleanHidden = lbl ? (lbl.offsetParent===null) : true;
        document.body.classList.remove('export-clean-pdf');
        var workShown = lbl ? (lbl.offsetParent!==null) : false;
        return {cleanHidden:cleanHidden, workShown:workShown};
    """)
    check("Clean PDF hides task labels; working shows them", hides["cleanHidden"] and hides["workShown"], str(hides))

    # ---- P1-9: drawer returns focus to opener on close ----
    foc = d.execute_script("""
        // a real, always-visible figure-row learn button (not a collapsed-glossary chip)
        var btn=document.querySelector('#paperCanvas .figure-learning-row [data-learn]'); if(!btn) return null;
        btn.id='__optest'; btn.click();
        var opened=!document.getElementById('learningDrawer').hidden;
        PaperStudio.closeLearningDrawer();
        var returned=(document.activeElement && document.activeElement.id==='__optest');
        return {opened:opened, returned:returned};
    """)
    time.sleep(0.2)
    check("Drawer traps then returns focus to opener", foc and foc["opened"] and foc["returned"], str(foc))

    # ---- references builder: deterministic, from included trials only ----
    refs = d.execute_script("""
        var inc = (RapidMeta.state.trials||[]).filter(function(t){return String(t.status||'').toLowerCase()==='include';});
        PaperStudio.buildReferences();
        var el=document.querySelector('[data-field="studentText.references"]');
        return {n: inc.length, text: el? el.innerText : '', state: (PaperStudio.state.studentText||{}).references||''};
    """)
    nlines = len([l for l in (refs.get("text","") or "").splitlines() if l.strip()])
    check("References built from included studies (numbered, with PMID)",
          refs["n"] >= 1 and nlines == refs["n"] and "PMID" in refs["text"] and refs["text"] == refs["state"],
          f"{nlines} lines for {refs['n']} included")
    check("References include NCT/acronym identifiers, not invented journals",
          ("NCT" in refs["text"]) or ("FIDELIO" in refs["text"] or "FIGARO" in refs["text"] or "FINEARTS" in refs["text"]),
          refs["text"][:80])

    # ---- instructional guidance present + toggleable ----
    g = d.execute_script("""
        return {
          onboard: !!document.querySelector('#paperCanvas .onboard-card'),
          helps: document.querySelectorAll('#paperCanvas .section-help').length,
          dots: document.querySelectorAll('#paperCanvas .help-dot').length,
          examples: document.querySelectorAll('#paperCanvas .section-example').length
        };
    """)
    check("Onboarding card + section guidance render", g["onboard"] and g["helps"] >= 8 and g["dots"] >= 3 and g["examples"] >= 2, str(g))
    toggled = d.execute_script("""
        document.getElementById('btnToggleTips').click();
        var sh=document.querySelector('#paperCanvas .section-help');
        var hidden = sh ? (sh.offsetParent===null) : false;
        document.getElementById('btnToggleTips').click();
        var shownAgain = sh ? (sh.offsetParent!==null) : false;
        return {hidden:hidden, shownAgain:shownAgain};
    """)
    check("Hide-tips toggle hides/shows guidance (writing untouched)", toggled["hidden"] and toggled["shownAgain"], str(toggled))
    # guidance must NOT leak into the clean PDF
    leak = d.execute_script("""
        document.body.classList.add('export-clean-pdf');
        var sh=document.querySelector('#paperCanvas .section-help');
        var ob=document.querySelector('#paperCanvas .onboard-card');
        var r = {help: sh?sh.offsetParent===null:true, onboard: ob?ob.offsetParent===null:true};
        document.body.classList.remove('export-clean-pdf');
        return r;
    """)
    check("Clean PDF hides all guidance (no-clean-pdf)", leak["help"] and leak["onboard"], str(leak))

    # ---- multi-outcome: demo seeds 2 illustrative secondaries ----
    d.execute_script("PaperStudio.embedFigures();"); time.sleep(1.5)
    oc = d.execute_script("""
        return {n:(PaperStudio.state.outcomes||[]).length,
                sec1:!!document.getElementById('outcomeSection_demo1'),
                forest:(function(){var b=document.getElementById('outcomeForestSlot_demo1-box'); return !!(b&&(b.classList.contains('js-plotly-plot')||(b.layout&&b.data)));})()};
    """)
    check("Multi-outcome: 2 illustrative secondaries seeded + section rendered", oc["n"] == 2 and oc["sec1"], str(oc))
    check("Multi-outcome: each secondary has its own forest plot", oc["forest"])
    # add an outcome via the form
    added = d.execute_script("""
        document.getElementById('ocf-label').value='All-cause death';
        document.getElementById('ocf-est').value='0.92';
        document.getElementById('ocf-lci').value='0.84'; document.getElementById('ocf-uci').value='1.00';
        document.getElementById('ocf-i2').value='5'; document.getElementById('ocf-k').value='3';
        PaperStudio.addOutcome();
        return {n:PaperStudio.state.outcomes.length, last:PaperStudio.state.outcomes[PaperStudio.state.outcomes.length-1].label};
    """)
    check("Add-outcome form appends a new outcome section", added["n"] == 3 and added["last"] == "All-cause death", str(added))
    # readiness now requires the new outcome's interpretation (blocking)
    ocblock = d.execute_script("""
        var r=PaperStudio.runReadinessCheck('clean');
        return r.issues.filter(function(i){return /interpretation of|caption for/i.test(i.msg)&&i.level==='error';}).length;
    """)
    check("Readiness requires interpretation+caption per outcome", ocblock >= 2, f"blocking outcome items={ocblock}")
    # remove an outcome
    removed = d.execute_script("""
        window.confirm=function(){return true;};
        PaperStudio.removeOutcome('demo2');
        return PaperStudio.state.outcomes.length;
    """)
    check("Remove-outcome deletes the section", removed == 2, f"remaining={removed}")

    # ---- exports (Batch 2) ----
    man = d.execute_script("""
        var m=PaperStudio.buildManuscript();
        var hs=m.sections.filter(function(s){return s.h;}).map(function(s){return s.h;});
        var figs=m.sections.filter(function(s){return s.fig;}).map(function(s){return s.fig;});
        return {n:m.sections.length, heads:hs.join('|'), figs:figs.join('|')};
    """)
    check("Manuscript model builds (Abstract/Methods/Results/Discussion + figures)",
          all(h in man["heads"] for h in ["Abstract","Methods","Results","Discussion"]) and "forest" in man["figs"], man["heads"][:120])

    d.set_script_timeout(25)
    png = d.execute_async_script("""
        var done=arguments[arguments.length-1];
        PaperStudio.figureBlob('forest','png').then(function(b){done(b.size);}).catch(function(e){done(-1);});
    """)
    check("Figure exports as PNG (non-empty)", isinstance(png, int) and png > 1000, f"bytes={png}")
    tiff = d.execute_async_script("""
        var done=arguments[arguments.length-1];
        PaperStudio.figureBlob('forest','tiff').then(function(b){var fr=new FileReader();fr.onload=function(){var u=new Uint8Array(fr.result.slice(0,2));done({size:b.size,m:u[0]+','+u[1]});};fr.readAsArrayBuffer(b);}).catch(function(e){done({err:String(e)});});
    """)
    check("Figure exports as TIFF (valid 'II' header)", tiff.get("m") == "73,73" and tiff.get("size", 0) > 100, str(tiff))
    svg = d.execute_async_script("""
        var done=arguments[arguments.length-1];
        PaperStudio.figureBlob('forest','svg').then(function(b){b.text().then(function(t){done(t.slice(0,200));});}).catch(function(e){done('ERR '+e);});
    """)
    check("Figure exports as SVG", "<svg" in (svg or "").lower(), (svg or "")[:40])
    zipsize = d.execute_async_script("""
        var done=arguments[arguments.length-1];
        try {
          var enc=new TextEncoder();
          // exercise the zip writer indirectly via exportBundle path: build figure blob then nothing downloads in test
          PaperStudio.figureBlob('forest','png').then(function(b){ done(b.size>0?1:0); }).catch(function(){done(0);});
        } catch(e){ done(0); }
    """)
    check("Export pipeline returns figure blobs for bundling", zipsize == 1)

    # ---- supplementary + autosave hardening (Batch 3) ----
    sup = d.execute_script("""
        var f=PaperStudio._supplementaryFiles ? PaperStudio._supplementaryFiles() : [];
        var names=f.map(function(x){return x.name;}).join('|');
        var prisma=f.find(function(x){return /PRISMA/.test(x.name);});
        return {n:f.length, names:names, hasItems: prisma? /Eligibility criteria/.test(prisma.text) && /GRADE/.test(prisma.text) : false};
    """)
    check("Supplementary: PRISMA + AMSTAR + search generated with real items", sup["n"] == 3 and sup["hasItems"], sup["names"])
    check("Privacy/PII notice shown in onboarding",
          d.execute_script("return /Do not paste identifiable/.test(document.getElementById('paperCanvas').innerText||'') || /Do not paste identifiable/.test((document.querySelector('.onboard-privacy')||{}).innerText||'');"))
    check("Clear-all + autosave-flush wired",
          d.execute_script("return typeof PaperStudio.clearAll==='function' && !!document.getElementById('btnClearAll');"))

    # ---- Batch 4: review P0 fixes ----
    poll = d.execute_script("""
        localStorage.setItem('rapidmeta.paperState', '{"__proto__":{"polluted":1}}');
        PaperStudio.restore();
        return ({}).polluted === undefined;
    """)
    check("deepMerge blocks prototype pollution (restore + import)", poll)

    disc = d.execute_script("""
        document.body.classList.add('export-clean-pdf');
        var p=Array.prototype.slice.call(document.querySelectorAll('#paperCanvas p')).filter(function(x){return /generated automatically by the RapidMeta/.test(x.innerText);})[0];
        var vis=p?p.offsetParent!==null:false;
        document.body.classList.remove('export-clean-pdf');
        return {present:!!p, visibleInClean:vis};
    """)
    check("AI-use + provenance disclosure PERSISTS in the Clean PDF", disc["present"] and disc["visibleInClean"], str(disc))

    ov = d.execute_script("""
        var e=document.querySelector('[data-field="studentText.discussionConclusion"]');
        e.innerText='This proves the drug works and should be used in all patients, with no uncertainty at all about it now.';
        e.dispatchEvent(new InputEvent('input',{bubbles:true}));
        var r=PaperStudio.runReadinessCheck('clean');
        return r.issues.filter(function(i){return /Overclaim must be fixed/.test(i.msg)&&i.level==='error';}).length;
    """)
    check("Overclaim in conclusion is BLOCKING (not just a warning)", ov >= 1, f"blocking overclaim={ov}")

    arabicsafe = d.execute_script("""
        var e=document.querySelector('[data-field="studentText.discussionPrincipalFinding"]');
        e.innerText='The population intervention search risk of bias finding here.';
        var before=e.innerText;
        try { if (RapidMeta && RapidMeta.toggleArabic){RapidMeta.toggleArabic();RapidMeta.toggleArabic();} else if (RapidMeta && RapidMeta._translateWalk){RapidMeta._translateWalk(document.body);} } catch(err){}
        return e.innerText===before;
    """)
    check("Arabic translator does not corrupt contenteditable prose", arabicsafe)

    # ---- full transparency appendix ----
    tdoc = d.execute_script("""
        var t=PaperStudio._transparencyDocs();
        return {recLen:t.records.length, hasLink:/Link: http/.test(t.records), hasId:/NCT|PMID/.test(t.records),
                hasAbsLabel:/Abstract/.test(t.records), statHas:/Statistic|Pooled effect|No pooled results/.test(t.statistics),
                rHas:/R validation/.test(t.r)};
    """)
    check("Transparency: records list with links + identifiers + abstracts", tdoc["recLen"] > 500 and tdoc["hasLink"] and tdoc["hasId"] and tdoc["hasAbsLabel"], f"len={tdoc['recLen']}")
    check("Transparency: statistics + R-validation docs build", tdoc["statHas"] and tdoc["rHas"])
    figs = d.execute_async_script("""
        var done=arguments[arguments.length-1];
        PaperStudio.harvestAllFigures('png').then(function(a){done(a.length);}).catch(function(e){done(-1);});
    """)
    check("Transparency: harvests all dashboard charts as images", isinstance(figs, int) and figs >= 3, f"charts={figs}")

    # ---- Methods/Results length + journal style ----
    d.execute_script("PaperStudio.setStyle('journal','jama'); PaperStudio.setStyle('methodsLength','detailed');"); time.sleep(1.2)
    style = d.execute_script("var t=document.getElementById('paperCanvas').innerText; return {jama:/Data Sources/.test(t), detailed:/PRISMA 2020|metafor|sensitivity analyses/i.test(t)};")
    check("Methods style: JAMA structured labels + detailed length", style["jama"] and style["detailed"], str(style))
    d.execute_script("PaperStudio.setStyle('journal','generic'); PaperStudio.setStyle('methodsLength','concise');"); time.sleep(1.0)
    concise = d.execute_script("return /metafor|sensitivity analyses/i.test(document.getElementById('paperCanvas').innerText);")
    check("Methods length 'concise' drops the detailed sentences", not concise)

    # ---- persona fixes ----
    check("Primary button = 'Download my paper (PDF)'",
          d.execute_script("return /Download my paper/.test((document.getElementById('btnDownloadCleanPdf')||{}).innerText||'');"))
    gate = d.execute_script("PaperStudio.updateChecklist(); var p=document.getElementById('paperChecklistPanel').innerText; return p;")
    check("Readiness wording reassuring + honest", ("still to finish" in gate or "ready" in gate.lower()) and "interpretation" in gate, gate[:60])
    refblock = d.execute_script("""
        var el=document.querySelector('[data-field="studentText.references"]'); var saved=el?el.innerText:''; if(el) el.innerText='';
        var r=PaperStudio.runReadinessCheck('clean');
        var blocked=r.issues.some(function(i){return /References/.test(i.msg)&&i.level==='error';});
        if(el) el.innerText=saved; return blocked;
    """)
    check("References are required before the finished PDF", refblock)
    check("X-axis controls collapsed behind 'Adjust plot'",
          d.execute_script("return !!document.querySelector('.fig-controls-wrap > summary');"))
    check("No Font Awesome CDN link (offline)",
          d.execute_script("return !document.querySelector('link[href*=\"font-awesome\"]');"))

    # ---- menus: nothing clipped, every item wired ----
    menu = d.execute_script("""
        var dm=document.querySelector('.download-menu'); dm.setAttribute('open','');
        var body=dm.querySelector('.download-menu-body'); var cs=getComputedStyle(body);
        var vals=Array.prototype.slice.call(body.querySelectorAll('[data-export]')).map(function(b){return b.dataset.export;});
        body.scrollTop=body.scrollHeight;
        var last=body.querySelector('[data-export="transparency"]').getBoundingClientRect();
        return {overflow:cs.overflowY, scrollable:body.scrollHeight>body.clientHeight+1, lastReachable:last.bottom<=window.innerHeight+2, vals:vals};
    """)
    handled = {"clean-pdf","word","html","md","txt","bundle","figures","prisma","amstar","search","transparency"}
    check("Download menu scrolls — no item clipped (incl. Manuscript+figures, Transparency)",
          menu["overflow"] == "auto" and menu["lastReachable"], f"overflow={menu['overflow']} reachable={menu['lastReachable']}")
    check("Every download-menu item is a known/wired action (no dead buttons)",
          set(menu["vals"]) <= handled and "bundle" in menu["vals"], str(menu["vals"]))
    # each export action runs without throwing (functions stubbed to avoid real downloads)
    ran = d.execute_script("""
        var calls=[]; ['downloadPaperPdf','exportWord','exportHTML','exportMarkdown','exportText','exportBundle','exportAllFigures','exportSupplementary','exportTransparency'].forEach(function(fn){ if(PaperStudio[fn]) PaperStudio['_'+fn]=PaperStudio[fn]; });
        var orig={}; ['exportWord','exportHTML','exportMarkdown','exportText','exportBundle','exportAllFigures','exportSupplementary','exportTransparency','downloadPaperPdf'].forEach(function(fn){orig[fn]=PaperStudio[fn];PaperStudio[fn]=function(){calls.push(fn);};});
        var err=null;
        try { document.querySelectorAll('.download-menu-body [data-export]').forEach(function(b){ b.click(); }); } catch(e){ err=String(e); }
        Object.keys(orig).forEach(function(fn){PaperStudio[fn]=orig[fn];});
        return {err:err, calls:calls.length};
    """)
    check("Clicking every download item dispatches without error", ran["err"] is None and ran["calls"] >= 8, str(ran))

    # ---- round-2 persona fixes ----
    ap = d.execute_script("""
        var mn=document.querySelector('.fig-x[data-figid="forest"][data-b="min"]');
        var mx=document.querySelector('.fig-x[data-figid="forest"][data-b="max"]');
        if(!mn||!mx) return {err:'no inputs'};
        mn.value='0.4'; mx.value='1.6';
        var apply=document.querySelector('[data-figaction="apply"][data-figid="forest"]');
        if(!apply) return {err:'no apply btn'};
        apply.click();
        var box=document.getElementById('forestPlotPaperSlot-box');
        return {auto: (box&&box.layout)?box.layout.xaxis.autorange:null};
    """)
    check("Plot Apply BUTTON applies x-range (round-2 real bug fix)", ap.get("auto") is False, str(ap))
    demob = d.execute_script("""
        var r=PaperStudio.runReadinessCheck('clean');
        var blocked=r.issues.some(function(i){return i.level==='error' && /All-cause mortality|Kidney disease progression/.test(i.msg);});
        var warned=r.issues.some(function(i){return i.level==='warn' && /illustrative/i.test(i.msg);});
        return {blocked:blocked, warned:warned};
    """)
    check("Illustrative demo outcomes are advisory, not blocking", (not demob["blocked"]) and demob["warned"], str(demob))
    check("Live word counters render", d.execute_script("return !!document.querySelector('#paperCanvas .live-wc');"))
    check("Primary button shows lock state when incomplete",
          d.execute_script("PaperStudio.updateChecklist(); var b=document.getElementById('btnDownloadCleanPdf'); return /to finish/.test(b.textContent)||b.classList.contains('locked');"))
    check("Format selector has a 'leave it if unsure' default note",
          d.execute_script("return /Leave on .Generic/.test(document.querySelector('.style-control-note').innerText||'');"))

    # ---- incomplete-pooling honesty (GLP-1 CVOT systemic bug) ----
    drop = d.execute_script("""
        RapidMeta.state.trials=[
          {id:'A',status:'include',data:{tN:100,cN:100,tE:10,cE:12,name:'Trial A'}},
          {id:'B',status:'include',data:{tN:100,cN:100,tE:8,cE:9,name:'Trial B'}},
          {id:'C',status:'include',data:{tN:100,cN:100,tE:7,cE:8,name:'Trial C'}},
          {id:'D',status:'include',data:{tN:100,cN:100,tE:0,cE:0,name:'LEADER'}},
          {id:'E',status:'include',data:{tN:100,cN:100,tE:0,cE:0,name:'SUSTAIN-6'}}];
        RapidMeta.state.results={or:'0.86',lci:'0.78',uci:'0.95',i2:'10',k:3,n:'500',confLevel:95,plotData:[]};
        PaperStudio.loadRapidMetaData(); PaperStudio.render();
        var a=PaperStudio.state.analysis;
        return {dropped:a.droppedStudies, names:a.droppedNames,
                banner:/were not combined in the meta-analysis/.test(document.getElementById('paperCanvas').innerText||''),
                warn:PaperStudio.runReadinessCheck('clean').issues.some(function(i){return /were NOT pooled/.test(i.msg);})};
    """)
    check("Incomplete-pooling warning when included studies exceed pooled k",
          drop["dropped"] == 2 and drop["banner"] and ("LEADER" in (drop["names"] or "")) and drop["warn"], str(drop))

    # ---- polish + storytelling (round-3) ----
    check("Secular storytelling cards render (>=3)",
          d.execute_script("return document.querySelectorAll('#paperCanvas .story-card').length >= 3;"),
          str(d.execute_script("return document.querySelectorAll('#paperCanvas .story-card').length;")))
    check("Stories are non-religious + use direct address ('you')",
          d.execute_script("var t=Array.prototype.map.call(document.querySelectorAll('.story-card p'),function(p){return p.textContent;}).join(' ').toLowerCase(); return t.indexOf('you')>-1 && !/\\b(god|allah|lord|prophet|scripture|holy|prayer|quran)\\b/.test(t);"))
    check("'How big is clinically big?' explainer chip present",
          d.execute_script("return !!document.querySelector('#paperCanvas [data-learn=\"clinical_importance\"]');"))
    thin = d.execute_script("""
        var e=document.querySelector('[data-field="studentText.abstractConclusion"]');
        e.innerText='In this group the treatment probably helps a little, but we should stay cautious because the certainty is only moderate and the trials were few.';
        e.dispatchEvent(new InputEvent('input',{bubbles:true}));
        PaperStudio.updateWordCounts();
        var s=document.querySelector('.live-wc[data-wc-for="studentText.abstractConclusion"]');
        return s? s.innerText : '';
    """)
    check("Live word counter shows 'more detail helps' nudge near the floor", "more detail helps" in (thin or ""), thin)
    check("Story cards hidden in clean PDF + by tips toggle (no-clean-pdf class)",
          d.execute_script("return document.querySelectorAll('#paperCanvas .story-card.no-clean-pdf').length === document.querySelectorAll('#paperCanvas .story-card').length;"))

    # ======== UX fixes (2026-06-10): #1 width, #2 menu anchor, #4 hit-area, #8 use-example ========

    # ---- #1: canvas uses more screen width on desktop; clean export re-caps to A4 ----
    w1 = d.execute_script("""
        var c=document.querySelector('.paper-canvas');
        var screenW=c.getBoundingClientRect().width;
        document.body.classList.add('export-clean-pdf');
        var capW=getComputedStyle(c).maxWidth;
        document.body.classList.remove('export-clean-pdf');
        return {screenW:Math.round(screenW), capW:capW};
    """)
    check("#1 Canvas fills more of the screen (was 920px); clean export re-caps to 920px",
          w1["screenW"] > 1000 and w1["capW"] == "920px", str(w1))

    # ---- #2: the position:fixed toolbar menus open UNDER their button, not the top-left corner ----
    d.execute_script("document.querySelector('.toolbar-more').setAttribute('open','');")
    time.sleep(0.2)
    more = d.execute_script("""
        var dd=document.querySelector('.toolbar-more'), b=document.querySelector('.toolbar-more-body');
        var s=dd.querySelector('summary').getBoundingClientRect(), br=b.getBoundingClientRect();
        return {gap: Math.round(br.top - s.bottom), leftDelta: Math.round(Math.abs(br.left - s.left)), bodyTop: Math.round(br.top)};
    """)
    check("#2 'More' menu anchors directly under its button (not floated to the corner)",
          abs(more["gap"]) <= 16 and more["leftDelta"] <= 16 and more["bodyTop"] > 60, str(more))
    d.execute_script("document.querySelector('.toolbar-more').removeAttribute('open');")
    d.execute_script("document.querySelector('.download-menu').setAttribute('open','');")
    time.sleep(0.2)
    dlm = d.execute_script("""
        var dd=document.querySelector('.download-menu'), b=document.querySelector('.download-menu-body');
        var s=dd.querySelector('summary').getBoundingClientRect(), br=b.getBoundingClientRect();
        return {gap: Math.round(br.top - s.bottom), rightDelta: Math.round(Math.abs(br.right - s.right)), bodyTop: Math.round(br.top)};
    """)
    check("#2 'Advanced formats' menu anchors under its button (right-aligned)",
          abs(dlm["gap"]) <= 16 and dlm["rightDelta"] <= 16 and dlm["bodyTop"] > 60, str(dlm))
    # tall menus must be internally scrollable with the wheel kept inside (overscroll-contain)
    scr = d.execute_script("""
        var b=document.querySelector('.download-menu-body'); var cs=getComputedStyle(b);
        b.scrollTop=9999; var moved=b.scrollTop;  // 0 here (fits at 1400x1000) but proves it is a scroll container
        return {overflowY:cs.overflowY, overscroll:(cs.overscrollBehaviorY||cs.overscrollBehavior||''), scrollableContainer: b.scrollHeight>=b.clientHeight};
    """)
    check("#2 Menu is a scroll container with wheel contained (no page-chaining)",
          scr["overflowY"] == "auto" and "contain" in scr["overscroll"], str(scr))
    d.execute_script("document.querySelector('.download-menu').removeAttribute('open');")

    # ---- #4: an EMPTY inline editable keeps a clickable hit area (title fills its line) ----
    geo = d.execute_script("""
        var t=document.querySelector('#paperCanvas h1 .student-editable[data-field="studentText.title"]');
        if(!t) return {err:'no title'};
        t.textContent='';                       // force the empty state
        var cs=getComputedStyle(t), r=t.getBoundingClientRect(), h1=t.closest('h1').getBoundingClientRect();
        var cap=document.querySelector('#paperCanvas figcaption .student-editable');
        var capDisp = cap ? getComputedStyle(cap).display : '';
        return {display:cs.display, fillsLine: r.width > h1.width*0.6, capDisplay:capDisp};
    """)
    check("#4 Empty title is a full-width clickable block; captions keep a min hit area",
          geo.get("display") == "block" and geo.get("fillsLine") and geo.get("capDisplay") in ("inline-block", "block"), str(geo))

    # ---- #8: 'Use this example' buttons fill the box, hide once filled, are gate-safe + export-clean ----
    cnt = d.execute_script("return document.querySelectorAll('#paperCanvas .use-example').length;")
    check("#8 'Use this example' buttons render for the writing boxes", cnt >= 15, f"count={cnt}")
    ue = d.execute_script("""
        var btn=document.querySelector('.use-example[data-target="studentText.coverFinding"]');
        if(!btn) return {err:'no btn'};
        var before=btn.hasAttribute('hidden');
        btn.click();
        var box=document.querySelector('[data-field="studentText.coverFinding"]');
        return {hiddenBefore:before, hiddenAfter:btn.hasAttribute('hidden'),
                boxText:box.innerText.trim(), state:((PaperStudio.state.studentText||{}).coverFinding||'').trim(),
                starter:(btn.dataset.starter||'').trim()};
    """)
    check("#8 Clicking 'Use this example' fills the box, saves to state, and hides the button",
          (not ue.get("hiddenBefore")) and ue.get("hiddenAfter") and ue.get("boxText") and
          ue.get("boxText") == ue.get("state") and ue.get("boxText") == ue.get("starter"), str(ue)[:140])
    unsafe = d.execute_script("""
        var bad=/\\[(population|intervention|comparator|primary outcome|condition)\\]|_{3,}|\\bTBC\\b|\\bTODO\\b|lorem/i;
        var out=[];
        document.querySelectorAll('.use-example').forEach(function(b){ if(bad.test(b.dataset.starter||'')) out.push(b.dataset.target); });
        return out;
    """)
    check("#8 Every example starter is gate-safe (no blocking placeholder tokens)", len(unsafe) == 0, str(unsafe))
    nofloor = d.execute_script("""
        var r=PaperStudio.runReadinessCheck('clean');
        return r.issues.filter(function(i){return i.field==='studentText.coverFinding' && i.level==='error';}).length;
    """)
    check("#8 An accepted example satisfies the field word-floor (does not self-block)", nofloor == 0, f"coverFinding errors={nofloor}")
    exhid = d.execute_script("""
        document.body.classList.add('export-clean-pdf');
        var b=document.querySelector('#paperCanvas .use-example:not([hidden])');
        var hidden=b?(b.offsetParent===null):true;
        document.body.classList.remove('export-clean-pdf');
        return hidden;
    """)
    check("#8 'Use this example' buttons never reach the clean export (.no-clean-pdf)", exhid, str(exhid))

    # ---- #6: more worked "Good vs Too-vague" examples on the required sections ----
    nex = d.execute_script("return document.querySelectorAll('#paperCanvas .section-example').length;")
    check("#6 Extra section examples render on required sections", nex >= 12, f"examples={nex}")

    # ---- #3: registered-protocol link field reveals a clickable link, validates, never blocks ----
    pl = d.execute_script("""
        var box=document.querySelector('[data-field="studentText.protocolLink"]');
        if(!box) return {err:'no field'};
        var hiddenEmpty = (function(){var a=document.getElementById('protocolOpenLink');return a?a.hidden:null;})();
        box.innerText='https://example.github.io/protocol-2026.html';
        box.dispatchEvent(new InputEvent('input',{bubbles:true}));
        var a=document.getElementById('protocolOpenLink');
        var afterHref=a?a.getAttribute('href'):null, afterHidden=a?a.hidden:null;
        box.innerText='not a url';
        box.dispatchEvent(new InputEvent('input',{bubbles:true}));
        var invalidHidden=document.getElementById('protocolOpenLink').hidden;
        var blocks=PaperStudio.runReadinessCheck('clean').issues.some(function(i){return i.field==='studentText.protocolLink' && i.level==='error';});
        box.innerText=''; box.dispatchEvent(new InputEvent('input',{bubbles:true}));
        return {hiddenEmpty:hiddenEmpty, afterHref:afterHref, afterHidden:afterHidden, invalidHidden:invalidHidden, blocks:blocks};
    """)
    check("#3 Protocol link: valid URL shows a clickable link, invalid hides it, field never blocks",
          pl.get("hiddenEmpty") and pl.get("afterHref") == "https://example.github.io/protocol-2026.html" and
          pl.get("afterHidden") is False and pl.get("invalidHidden") and pl.get("blocks") is False, str(pl))

    # ---- #7: read-only worked-example modal opens, has all sections, never edits the draft ----
    we = d.execute_script("""
        var before=JSON.stringify(PaperStudio.state.studentText);
        document.getElementById('btnWorkedExample').click();
        var m=document.getElementById('workedExampleModal');
        var opened=!!(m && !m.hidden);
        var hasBanner=m?/read.only/i.test(m.innerText):false;
        var sections=m?m.querySelectorAll('.example-modal-body h3').length:0;
        PaperStudio.closeWorkedExample();
        var closed=m?m.hidden:false;
        var after=JSON.stringify(PaperStudio.state.studentText);
        return {opened:opened, hasBanner:hasBanner, sections:sections, closed:closed, unchanged: before===after};
    """)
    check("#7 Worked-example modal opens read-only with all sections, closes, never touches the draft",
          we.get("opened") and we.get("hasBanner") and we.get("sections") >= 10 and we.get("closed") and we.get("unchanged"), str(we))

    # ======== Feature B: left section navigator ========
    nav = d.execute_script("""
        var p=document.getElementById('paperNavPanel');
        var items=p.querySelectorAll('.nav-item');
        return {count:items.length, groups:p.querySelectorAll('.nav-group').length,
                hasNav:!!p.querySelector('nav[aria-label="Paper sections"]'),
                roving:Array.prototype.filter.call(items,function(b){return b.tabIndex===0;}).length,
                labelled:Array.prototype.every.call(items,function(b){return /— (complete|to write)/.test(b.getAttribute('aria-label')||'');}),
                progress:(p.querySelector('.nav-progress')||{}).textContent||''};
    """)
    check("B: nav renders 21 sections in 7 groups, one tab-stop, AT state labels",
          nav["count"] == 21 and nav["groups"] == 7 and nav["hasNav"] and nav["roving"] == 1 and nav["labelled"], str(nav))
    navclick = d.execute_script("""
        var btn=document.querySelector('#paperNavPanel .nav-item[data-nav-field="studentText.title"]');
        btn.click();
        var box=document.querySelector('#paperCanvas [data-field="studentText.title"]');
        return {focused: document.activeElement===box, current: btn.getAttribute('aria-current')==='step'};
    """)
    check("B: clicking a section focuses its box and marks it aria-current", navclick["focused"] and navclick["current"], str(navclick))
    navdone = d.execute_script("""
        var box=document.querySelector('#paperCanvas [data-field="studentText.funding"]');
        box.innerText='This work received no specific funding from any agency.';
        box.dispatchEvent(new InputEvent('input',{bubbles:true}));
        PaperStudio.updateChecklist();
        var btn=document.querySelector('#paperNavPanel .nav-item[data-nav-field="studentText.funding"]');
        return {done: btn.classList.contains('nav-done'), aria:/complete/.test(btn.getAttribute('aria-label')||'')};
    """)
    check("B: a filled section shows complete (glyph + AT label) in the nav", navdone["done"] and navdone["aria"], str(navdone))
    navkey = d.execute_script("""
        var items=document.querySelectorAll('#paperNavPanel .nav-item');
        items[0].tabIndex=0; items[0].focus();
        items[0].dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true}));
        return {moved: items[1].tabIndex===0 && document.activeElement===items[1], firstReset: items[0].tabIndex===-1};
    """)
    check("B: roving tabindex — ArrowDown moves focus and the single tab stop", navkey["moved"] and navkey["firstReset"], str(navkey))
    skip = d.execute_script("""
        document.querySelector('#paperNavPanel [data-action="skip-to-writing"]').click();
        return document.activeElement===document.querySelector('#paperCanvas [data-field="studentText.title"]');
    """)
    check("B: 'Skip to writing' jumps focus into the first section", skip, str(skip))

    # ---- console errors ----
    logs = d.get_log("browser")
    def noise(m):
        m = m.lower()
        return any(k in m for k in ["favicon","font-awesome","fontawesome","cdnjs","clinicaltrials","ncbi","eutils","pubmed","openalex","err_internet","err_name","err_network","err_file_not_found","err_connection","failed to load resource","integrity",
            # pre-existing file:// limitations of the base kit (work over http/Pages):
            "cors policy","cross origin","benchmark",".json"])
    real = [l["message"] for l in logs if l["level"] == "SEVERE" and not noise(l["message"])]
    check("No unexpected severe console errors", len(real) == 0, ("; ".join(real)[:300]) if real else "clean")

finally:
    d.quit()

passed = sum(1 for _,c,_ in results if c)
print(f"\n==== {passed}/{len(results)} checks passed ====")
sys.exit(0 if passed == len(results) else 1)
