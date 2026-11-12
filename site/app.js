// Open Book site. Plain JavaScript, no libraries, no requests to other sites.
// Every result shown on the site comes from data.js, which tools/build_site_data.py writes.
"use strict";
(function () {
  const D = window.OPEN_BOOK_DATA;
  if (!D) return;

  // ---------- helpers ----------
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = (x, d = 2) => (x === null || x === undefined || Number.isNaN(Number(x))) ? "—" : Number(x).toFixed(d);
  const signed = (x, d = 2) => (x > 0 ? "+" : x < 0 ? "−" : "") + fmt(Math.abs(x), d);
  const count = x => Number(x).toLocaleString("en-US");
  const el = id => document.getElementById(id);
  const test = id => D.tests.find(t => t.id === id);
  const isYes = t => t.verdict === "supported";

  const TESTS = {
    H1: ["reading", "Giving the model the best library that the project could build beats giving it nothing to read", "A passage from a legal encyclopedia, compared with nothing to read. Llama 3, old MBE questions."],
    H2: ["reading", "An encyclopedia helps more than court opinions", "Encyclopedia compared with court opinions as the library. Llama 3, old MBE questions."],
    H3: ["reading", "The right passage beats the best library that the project could build", "The passage that a law student marked, compared with the encyclopedia. Llama 3, old MBE questions."],
    H4a: ["search", "Adding the model's own reasoning to the search words helps a word-matching search engine", "How often the marked passage is among the first 100 results. Search engine: BM25."],
    H4b: ["search", "The same, for a search model that compares meanings", "How often the marked passage is among the first 100 results. Search model: E5."],
    H5: ["search", "Searching only the right state's laws beats searching every state's laws", "Yes-or-no questions about state housing law. Llama 3 reads the top result."],
    H6: ["search", "Extra training on some states' laws helps the search model on states that it has not seen", "How often a right statute is among the first 10 results, in states that training did not use."],
    H7: ["oldlaw", "Reading only the overruled decision makes the model pick the outdated rule more often", "Old decision only, compared with nothing to read. Share of outdated answers. Llama 3."],
    H8: ["oldlaw", "Removing overruled decisions from search results lowers outdated answers", "Search results, compared with the same results without overruled decisions. Llama 3."],
    H9: ["oldlaw", "Search often ranks the overruled decision above the decision that overruled it", "Share of questions where the old decision outranks the new one. Search model: E5."],
    H10: ["oldlaw", "An AI agent that can check the law picks the outdated rule less often than plain search", "Agent with tools, compared with plain search. Share of outdated answers. Qwen3."]
  };
  const GROUPS = { all: "All 11", reading: "Reading (H1 to H3)", search: "Search engines (H4 to H6)", oldlaw: "Old law (H7 to H10)" };
  const CONDITIONS = {
    "closed": ["Nothing to read", "The model sees only the question."],
    "old-only": ["Only the old decision", "A passage from the overruled decision."],
    "new-only": ["Only the new decision", "A passage from the decision that overruled it."],
    "both": ["Both decisions, no dates", "Both passages, without names or years."],
    "both-dated": ["Both decisions, with names and years", "Both passages, each with its case name and year."],
    "retrieved": ["Top search result", "The first result of a search over Supreme Court opinions."],
    "citator": ["Search without overruled decisions", "The same search, after overruled decisions are taken out."],
    "note": ["Search with a warning note", "The same top result, with a note if it was overruled."]
  };
  const LABELS = {
    "retrieval": "The search did not find the deciding rule",
    "reading": "The rule was there, but the model chose wrong",
    "out-of-library": "The rule is in a source that the library does not have",
    "law-changed": "The official answer rests on law that has changed",
    "key-dispute": "The official answer looks doubtful",
    "other": "Something else"
  };

  // ---------- numbers in running text: <span data-bind="H3.diff"> ----------
  function bindings() {
    const b = {};
    b["tests.count"] = D.tests.length;
    b["tests.supported"] = D.tests.filter(isYes).length;
    b["tests.notsupported"] = D.tests.filter(t => !isYes(t)).length;
    D.tests.forEach(t => {
      b[t.id + ".diff"] = signed(t.difference);
      b[t.id + ".abs"] = fmt(Math.abs(t.difference));
      b[t.id + ".round"] = String(Math.round(Math.abs(t.difference)));
      b[t.id + ".low"] = signed(t.low);
      b[t.id + ".high"] = signed(t.high);
      b[t.id + ".n"] = count(t.questions);
      b[t.id + ".verdict"] = t.verdict;
      b[t.id + ".need"] = String(t.threshold);
    });
    const h9 = test("H9");
    b["H9.share"] = fmt(h9.difference) + "%";
    b["H9.lowshare"] = fmt(h9.low) + "%";
    b["H9.highshare"] = fmt(h9.high) + "%";
    const G = D.goodlaw, R = G.rates;
    Object.keys(CONDITIONS).forEach(c => {
      const r = R["llama8:" + c];
      b["gl." + c + ".current"] = fmt(r.current, 1) + "%";
      b["gl." + c + ".old"] = fmt(r.superseded, 1) + "%";
    });
    b["gl.search.old"] = fmt(R["qwen3:retrieved"].superseded, 1) + "%";
    b["gl.agent.old"] = fmt(R["qwen3:agent"].superseded, 1) + "%";
    b["gl.tested"] = count(R["llama8:closed"].questions);
    b["gl.written"] = count(G.written);
    b["gl.leftout"] = String(G.left_out.length);
    b["gl.sample"] = String(G.sample.length);
    b["h9.count"] = count(G.h9.old_outranks_new);
    b["h9.n"] = count(G.h9.questions);
    b["date.both"] = fmt(G.date_test_both_forms_correct, 1) + "%";
    b["err.count"] = String(D.errors.length);
    b["err.byGold"] = String(D.errors.filter(e => e.gold_passage === e.answer).length);
    b["err.byClosed"] = String(D.errors.filter(e => e.closed_book === e.answer).length);
    const mbe = D.reproduction.find(r => r.id === "R1a");
    b["mbe.all"] = count(mbe.questions);
    b["mbe.tests"] = count(test("H1").questions);
    b["mbe.validation"] = count(mbe.questions - test("H1").questions);
    return b;
  }
  const B = bindings();
  document.querySelectorAll("[data-bind]").forEach(node => {
    const v = B[node.dataset.bind];
    if (v !== undefined) node.textContent = v;
  });

  // ---------- the 11 tests ----------
  function intervalChart(t) {
    const W = 600, H = 58, pad = 34;
    const share = t.id === "H9";
    const need = share ? 30 : Number(t.threshold);
    const vals = [t.low, t.high, need, t.difference].concat(share ? [] : [0]);
    let lo = Math.min(...vals), hi = Math.max(...vals);
    const span = Math.max(hi - lo, 4);
    lo -= span * 0.14; hi += span * 0.14;
    const x = v => (pad + (v - lo) / (hi - lo) * (W - 2 * pad)).toFixed(1);
    const alt = share
      ? `${t.id}: ${fmt(t.difference)} percent of questions, with a range from ${fmt(t.low)} to ${fmt(t.high)} percent. The plan needed the low end above 30 percent.`
      : `${t.id}: a difference of ${signed(t.difference)} points, with a range from ${signed(t.low)} to ${signed(t.high)}. The plan needed at least plus ${need}.`;
    const zero = share ? "" : `<line x1="${x(0)}" y1="8" x2="${x(0)}" y2="38" stroke="currentColor" stroke-width="1.5"/><text x="${x(0)}" y="54" text-anchor="middle">0</text>`;
    return `<svg class="interval" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(alt)}" style="color:var(--ink-mute)">
      ${zero}
      <line x1="${x(need)}" y1="4" x2="${x(need)}" y2="38" stroke-dasharray="5 4" stroke-width="2" style="stroke:var(--good)"/>
      <text x="${x(need)}" y="54" text-anchor="middle" style="fill:var(--good)">${share ? "30% bar" : "needed +" + esc(need)}</text>
      <line x1="${x(t.low)}" y1="23" x2="${x(t.high)}" y2="23" stroke-width="7" stroke-linecap="round" style="stroke:var(--accent);opacity:.4"/>
      <line x1="${x(t.low)}" y1="15" x2="${x(t.low)}" y2="31" stroke-width="2" style="stroke:var(--accent)"/>
      <line x1="${x(t.high)}" y1="15" x2="${x(t.high)}" y2="31" stroke-width="2" style="stroke:var(--accent)"/>
      <circle cx="${x(t.difference)}" cy="23" r="7.5" style="fill:var(--accent)"/>
    </svg>`;
  }

  function pageTests() {
    const list = el("tests-list");
    let classroom = false, revealed = false, group = "all";
    const guesses = {};
    const chips = el("group-chips");
    chips.innerHTML = Object.entries(GROUPS).map(([k, name]) =>
      `<button type="button" class="chip" data-group="${esc(k)}" aria-pressed="${k === group}">${esc(name)}</button>`).join("");
    chips.addEventListener("click", e => {
      const b = e.target.closest("[data-group]");
      if (!b) return;
      group = b.dataset.group;
      chips.querySelectorAll("[data-group]").forEach(c => c.setAttribute("aria-pressed", String(c.dataset.group === group)));
      render();
    });

    function render() {
      const hide = classroom && !revealed;
      const shown = D.tests.filter(t => group === "all" || TESTS[t.id][0] === group);
      list.innerHTML = shown.map(t => {
        const [, claim, what] = TESTS[t.id];
        const yes = isYes(t);
        const g = guesses[t.id];
        const nums = t.id === "H9"
          ? `${fmt(t.difference)}% of ${count(t.questions)} questions (range ${fmt(t.low)}% to ${fmt(t.high)}%). The plan needed the low end above 30%.`
          : `Difference: ${signed(t.difference)} points on ${count(t.questions)} questions (range ${signed(t.low)} to ${signed(t.high)}). The plan needed at least +${esc(t.threshold)}.`;
        const verdict = hide ? '<span class="verdict hidden">verdict hidden</span>'
          : `<span class="verdict ${yes ? "yes" : "no"}">${yes ? "✓ supported" : "– not supported"}</span>`;
        const mark = revealed && g ? `<span class="muted">${(g === "yes") === yes ? "✓ Your guess was right." : "✗ Not this time."}</span>` : "";
        const predict = classroom ? `<div class="predict" role="group" aria-label="Your guess for ${esc(t.id)}">
            <button type="button" class="chip" data-t="${esc(t.id)}" data-g="yes" aria-pressed="${g === "yes"}">I think it held</button>
            <button type="button" class="chip" data-t="${esc(t.id)}" data-g="no" aria-pressed="${g === "no"}">I think it did not</button>
            ${mark}</div>` : "";
        return `<article class="card test">
          <div class="tid">${esc(t.id)}</div>
          <div><h3 class="claim">${esc(claim)}</h3><p class="what">${esc(what)}</p>${verdict}${predict}</div>
          ${hide ? "" : `<div class="chart">${intervalChart(t)}<p class="nums">${nums}</p></div>`}
        </article>`;
      }).join("");
      el("reveal").hidden = !classroom;
      el("reveal").textContent = revealed ? "Hide the verdicts again" : "Reveal the verdicts";
      const made = Object.keys(guesses).length;
      const right = D.tests.filter(t => guesses[t.id] && (guesses[t.id] === "yes") === isYes(t)).length;
      el("classroom-status").textContent = !classroom ? "" : revealed ? `Guesses right: ${right} of ${made}.` : `Guesses made: ${made} of ${D.tests.length}.`;
    }
    list.addEventListener("click", e => {
      const b = e.target.closest("[data-g]");
      if (!b) return;
      guesses[b.dataset.t] = b.dataset.g;
      render();
      const again = list.querySelector(`[data-t="${b.dataset.t}"][data-g="${b.dataset.g}"]`);
      if (again) again.focus();
    });
    el("classroom-toggle").addEventListener("click", e => {
      classroom = !classroom; revealed = false;
      e.currentTarget.setAttribute("aria-pressed", String(classroom));
      e.currentTarget.textContent = "Classroom mode: " + (classroom ? "on" : "off");
      el("classroom-help").hidden = !classroom;
      render();
    });
    el("reveal").addEventListener("click", () => { revealed = !revealed; render(); });
    render();
  }

  // ---------- the old-law trap ----------
  function stackRow(name, sub, r) {
    const alt = `${name}: current rule ${fmt(r.current, 1)} percent, outdated rule ${fmt(r.superseded, 1)} percent, another wrong answer ${fmt(r.other, 1)} percent.`;
    return `<div class="cond"><p class="name">${esc(name)}</p><p class="sub">${esc(sub)}</p>
      <div class="stack" role="img" aria-label="${esc(alt)}">
        <span class="seg-current" style="width:${Number(r.current)}%"></span><span class="seg-old" style="width:${Number(r.superseded)}%"></span><span class="seg-other" style="width:${Number(r.other)}%"></span>
      </div>
      <p class="vals">Current rule ${fmt(r.current, 1)}% · <b class="old">Outdated rule ${fmt(r.superseded, 1)}%</b> · Another wrong answer ${fmt(r.other, 1)}%</p></div>`;
  }
  function pageOldLaw() {
    const R = D.goodlaw.rates;
    el("cond-chart").innerHTML = D.goodlaw.conditions.map(c => stackRow(CONDITIONS[c][0], CONDITIONS[c][1], R["llama8:" + c])).join("");
    const a = R["qwen3:agent"];
    el("agent-chart").innerHTML =
      stackRow("Plain search", "Qwen3 reads the first search result.", R["qwen3:retrieved"]) +
      stackRow("Agent with tools", `Qwen3 may search, read and check a case. It used ${fmt(a.tool_calls_per_question, 1)} tools per question on average.`, a);
    const types = D.goodlaw.h9.opinion_types_in_top10;
    const slots = Object.values(types).reduce((x, y) => x + y, 0);
    el("dissent-share").textContent = Math.round(100 * (types.dissent || 0) / slots) + "%";
  }

  // ---------- try a question ----------
  function pageQuestions() {
    const S = D.goodlaw.sample, select = el("q-select");
    let hidden = true;
    const kind = (q, letter) => letter === q.current ? "current" : letter === q.superseded ? "old" : "other";
    const word = { current: "current rule", old: "outdated rule", other: "another answer" };
    select.innerHTML = S.map((q, i) => `<option value="${i}">Question ${i + 1}</option>`).join("");
    function render() {
      const i = Number(select.value), q = S[i];
      const rows = D.goodlaw.conditions.map(c => ["llama8:" + c, "Llama 3", CONDITIONS[c][0]])
        .concat([["qwen3:retrieved", "Qwen3", "Top search result"], ["qwen3:agent", "Qwen3", "Agent with tools"]]);
      const options = q.options ? `<ul class="options">${["A", "B", "C", "D"].map(L => {
        const k = hidden ? "other" : kind(q, L);
        const tag = k === "other" ? "" : ` <span class="tag ${k}">${word[k]}</span>`;
        return `<li class="${k === "other" ? "" : k}"><strong>${L}.</strong> ${esc(q.options[L])}${tag}</li>`;
      }).join("")}</ul>` : `<p class="muted">The question text is not published in this version.</p>`;
      let answers;
      if (q.left_out) {
        answers = `<p class="info">This question left the test before any model answered it, because the newer decision was itself overruled later. So there are no model answers to show.</p>`;
      } else if (hidden) {
        answers = `<p class="muted">The answers are hidden. Decide which option you think is the current rule. Then press “Show the answers”.</p>`;
      } else {
        answers = `<div class="scroll"><table><caption class="sr">How each model answered this question</caption>
          <thead><tr><th scope="col">Model</th><th scope="col">What it read</th><th scope="col">It chose</th></tr></thead><tbody>${rows.map(([key, model, cond]) => {
            const letter = q.answers[key], k = letter ? kind(q, letter) : "other";
            return `<tr><td>${esc(model)}</td><td>${esc(cond)}</td><td><span class="pick ${k}">${esc(letter || "—")}</span> ${letter ? word[k] : ""}</td></tr>`;
          }).join("")}</tbody></table></div>
          <p class="muted">In a search of all Supreme Court opinions, the best passage from the new decision ranked ${esc(q.rank_new ?? "—")}. The best passage from the old decision ranked ${esc(q.rank_old ?? "—")}.</p>`;
      }
      const quotes = hidden ? "" : (q.quotes || []).map(x => `<blockquote>“${esc(x.text)}”<br><small>From ${esc(x.from)}</small></blockquote>`).join("");
      el("q-card").innerHTML = `
        <article class="card">
          <p class="label">Question ${i + 1} of ${S.length}</p>
          ${hidden ? "" : `<p class="muted">${esc(q.new)} overruled ${esc(q.old)}${q.partial ? " in part" : ""}.</p>`}
          ${q.question ? `<h2 style="margin-top:6px;font-size:1.2rem">${esc(q.question)}</h2>` : ""}
          ${options}
          <p class="note">An AI model wrote this question, and no person has checked it yet. The tags show which answer the project's AI marked as the current rule. This is not a statement of the law.</p>
        </article>`;
      el("q-answers").innerHTML = `<h2>How the models answered</h2>${answers}
        ${quotes ? `<h2>Sentences from the two decisions</h2>${quotes}` : ""}`;
      el("q-prev").disabled = i === 0;
      el("q-next").disabled = i === S.length - 1;
    }
    select.addEventListener("change", () => { hidden = true; syncHide(); render(); });
    function syncHide() {
      el("q-hide").setAttribute("aria-pressed", String(!hidden));
      el("q-hide").textContent = hidden ? "Show the answers" : "Hide the answers";
    }
    el("q-hide").addEventListener("click", () => { hidden = !hidden; syncHide(); render(); });
    el("q-prev").addEventListener("click", () => { select.value = String(Number(select.value) - 1); hidden = true; syncHide(); render(); });
    el("q-next").addEventListener("click", () => { select.value = String(Number(select.value) + 1); hidden = true; syncHide(); render(); });
    syncHide(); render();
  }

  // ---------- why answers went wrong ----------
  function pageErrors() {
    const E = D.errors, n = E.length, counts = {};
    E.forEach(e => { counts[e.ai_label] = (counts[e.ai_label] || 0) + 1; });
    el("err-cards").innerHTML = Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([k, v]) =>
      `<div class="card"><p class="label">AI-assigned label: ${esc(k)}</p><p class="big">${esc(v)} of ${esc(n)}</p><p>${esc(LABELS[k] || k)}.</p></div>`).join("");
    const filter = el("err-filter");
    filter.innerHTML = `<option value="">All ${esc(n)}</option>` + Object.keys(counts).map(k => `<option value="${esc(k)}">${esc(LABELS[k] || k)}</option>`).join("");
    function render() {
      const want = filter.value;
      el("err-list").innerHTML = E.filter(e => !want || e.ai_label === want).map(e => `
        <details><summary>${esc(e.id)}<span class="lbl">${esc(e.ai_label)} · right answer ${esc(e.answer)}, the model chose ${esc(e.predicted)}</span></summary>
          <p>${esc(e.ai_reason)}</p>
          <p class="muted">Passage that the model read: <code>${esc(e.passages)}</code>${e.quote ? `. A short quotation: “${esc(e.quote)}”` : ""}</p>
          <div class="bars" role="img" aria-label="How sure the model was: ${["A", "B", "C", "D"].map(L => `${L} ${fmt(e.probabilities[L], 1)} percent`).join(", ")}.">
            ${["A", "B", "C", "D"].map(L => `<span>${L}</span><div class="track"><div class="bar ${L === e.answer ? "right" : L === e.predicted ? "chosen" : ""}" style="width:${Math.max(Number(e.probabilities[L]) || 0, 1)}%"></div></div><span class="num">${fmt(e.probabilities[L], 1)}%</span>`).join("")}
          </div>
          <p class="muted">The right answer is ${esc(e.answer)} (solid bar). The model chose ${esc(e.predicted)} (striped bar). With nothing to read, it chose ${esc(e.closed_book)}. With the marked passage, it chose ${esc(e.gold_passage)}.</p>
        </details>`).join("");
    }
    filter.addEventListener("change", render);
    render();
  }

  // ---------- reproduction table (engineers page) ----------
  function pageEngineers() {
    const what = { mbe: "MBE questions", housing: "housing law questions" };
    el("repro-body").innerHTML = D.reproduction.map(r =>
      `<tr><td>${esc(r.id)}</td><td>${esc(what[r.dataset] || r.dataset)}</td><td>${esc(r.method)}</td><td class="n">${r.questions ? esc(count(r.questions)) : "—"}</td><td>${esc(r.verdict)}</td></tr>`).join("");
  }

  const pages = { tests: pageTests, oldlaw: pageOldLaw, questions: pageQuestions, errors: pageErrors, engineers: pageEngineers };
  const run = pages[document.body.dataset.page];
  if (run) run();
})();
