// askEd audience page. DOM nodes only (never innerHTML): answers come from an LLM.
(() => {
  const $ = (id) => document.getElementById(id);

  function el(tag, props = {}, ...kids) {
    const node = Object.assign(document.createElement(tag), props);
    node.append(...kids);
    return node;
  }

  // Anonymous per-phone id. Falls back to memory if storage is blocked.
  function sessionId() {
    try {
      let id = localStorage.getItem("asked_sid");
      if (!id) {
        const b = new Uint8Array(12);
        crypto.getRandomValues(b);
        id = Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
        localStorage.setItem("asked_sid", id);
      }
      return id;
    } catch {
      return (window.__sid ||= Math.random().toString(36).slice(2) + Date.now().toString(36));
    }
  }
  const SID = sessionId();

  async function api(path, body) {
    let res;
    try {
      res = await fetch(path, {
        method: body ? "POST" : "GET",
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
    } catch {
      throw new Error("Could not reach askEd. Check your connection and try again.");
    }
    if (!res.ok) {
      let detail = "";
      try { detail = (await res.json()).detail; } catch { /* not JSON */ }
      throw new Error(typeof detail === "string" && detail ? detail : `Something went wrong (${res.status}).`);
    }
    return res.json();
  }

  // ── minimal safe markdown ───────────────────────────────────────────────
  function inline(text) {
    const frag = document.createDocumentFragment();
    const re = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g;
    let last = 0;
    for (const m of text.matchAll(re)) {
      if (m.index > last) frag.append(text.slice(last, m.index));
      const t = m[0];
      if (t.startsWith("**")) frag.append(el("strong", { textContent: t.slice(2, -2) }));
      else if (t.startsWith("`")) frag.append(el("code", { textContent: t.slice(1, -1) }));
      else frag.append(el("em", { textContent: t.slice(1, -1) }));
      last = m.index + t.length;
    }
    if (last < text.length) frag.append(text.slice(last));
    return frag;
  }

  function markdown(src) {
    const root = el("div");
    let list = null;
    let para = [];
    const flush = () => {
      if (para.length) root.append(el("p", {}, inline(para.join(" "))));
      para = [];
    };
    for (const line of src.split("\n")) {
      const h = line.match(/^#{1,6}\s+(.*)/);
      const li = line.match(/^\s*(?:[-*•]|(\d+)[.)])\s+(.*)/);
      if (li) {
        flush();
        const ordered = Boolean(li[1]);
        if (!list || list.tagName !== (ordered ? "OL" : "UL")) {
          list = el(ordered ? "ol" : "ul");
          root.append(list);
        }
        list.append(el("li", {}, inline(li[2])));
        continue;
      }
      list = null;
      if (h) { flush(); root.append(el("h4", {}, inline(h[1]))); }
      else if (!line.trim()) flush();
      else para.push(line.trim());
    }
    flush();
    return root;
  }

  // ── tabs ────────────────────────────────────────────────────────────────
  function showTab(which) {
    for (const [name, tab] of [["ask", $("tab-ask")], ["quiz", $("tab-quiz")]]) {
      const on = which === name;
      tab.classList.toggle("on", on);
      tab.setAttribute("aria-selected", String(on));
      tab.tabIndex = on ? 0 : -1;
    }
    $("pane-ask").classList.toggle("hidden", which !== "ask");
    $("pane-quiz").classList.toggle("hidden", which !== "quiz");
    if (which === "quiz" && !quiz) startQuiz();
  }
  $("tab-ask").onclick = () => showTab("ask");
  $("tab-quiz").onclick = () => showTab("quiz");
  for (const tab of [$("tab-ask"), $("tab-quiz")]) {
    tab.onkeydown = (e) => {
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        const next = tab === $("tab-ask") ? "quiz" : "ask";
        showTab(next);
        $("tab-" + next).focus();
      }
    };
  }

  // ── ask ─────────────────────────────────────────────────────────────────
  const SUGGESTIONS = [
    "How does askEd avoid making things up?",
    "Does it post answers on EdStem?",
    "Is my data sent to a third party?",
    "Has it been proven to reduce TA workload?",
  ];
  const box = $("q");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let sending = false;

  function revealInView(node) {
    node.scrollIntoView({ block: "nearest", behavior: reduceMotion ? "auto" : "smooth" });
  }

  function setBusy(busy) {
    sending = busy;
    $("send").disabled = busy;
    $("send").textContent = busy ? "Thinking…" : "Ask askEd";
    document.querySelectorAll(".suggest button").forEach((b) => { b.disabled = busy; });
  }

  async function ask(text) {
    text = text.trim();
    if (!text || sending) return;
    const out = $("ask-out");
    setBusy(true);
    out.replaceChildren(el("div", { className: "muted", textContent: "askEd is thinking…" }));
    try {
      const d = await api("/live/ask", { session_id: SID, text });
      out.replaceChildren(el("div", { className: "card answer" },
        el("div", { className: "asked", textContent: text }),
        markdown(d.answer),
        el("div", { className: "chips" }, ...d.topics.map((t) => el("span", { className: "chip", textContent: t }))),
        d.sources && d.sources.length
          ? el("div", { className: "muted", textContent: "Sources: " + d.sources.slice(0, 2).join(" · ") })
          : el("div", { className: "muted", textContent: "Not found in the askEd materials, so there is no source." }),
        el("div", { className: "muted", textContent: "AI answer from approved askEd documents. It may be wrong." }),
      ));
      box.value = "";
      $("count").textContent = "0 / 500";
      revealInView(out);
    } catch (e) {
      out.replaceChildren(el("div", { className: "err", textContent: e.message }));
      revealInView(out);
    } finally {
      setBusy(false);
    }
  }

  for (const text of SUGGESTIONS) {
    const b = el("button", { type: "button", className: "suggestion", textContent: text });
    b.onclick = () => { box.value = text; $("count").textContent = `${text.length} / 500`; ask(text); };
    $("suggest").append(b);
  }

  box.oninput = () => { $("count").textContent = `${box.value.length} / 500`; };
  // Enter adds a new line on phones; Ctrl/Cmd+Enter sends on keyboards.
  box.onkeydown = (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); ask(box.value); }
  };
  $("ask-form").onsubmit = (e) => { e.preventDefault(); ask(box.value); };

  // ── quiz ────────────────────────────────────────────────────────────────
  let quiz = null;

  function say(text, cls = "muted") {
    $("quiz-card").replaceChildren(el("div", { className: cls, textContent: text }));
  }

  async function startQuiz() {
    say("Loading questions…");
    try {
      const d = await api("/live/quiz?n=10");
      quiz = { questions: d.questions, i: 0, score: 0 };
      renderQuestion();
    } catch (e) {
      quiz = null;
      say(e.message, "err");
    }
  }

  function renderQuestion() {
    const card = $("quiz-card");
    const total = quiz.questions.length;
    if (quiz.i >= total) {
      const again = el("button", { className: "primary block", textContent: "Try new questions" });
      again.onclick = () => { quiz = null; startQuiz(); };
      return card.replaceChildren(
        el("div", { className: "muted", textContent: "Your score" }),
        el("div", { className: "score", textContent: `${quiz.score} / ${total}` }),
        el("div", { className: "muted", textContent: "Thanks. Your answers are anonymous and help show which topics need more time." }),
        el("div", { className: "row" }, again),
      );
    }
    const q = quiz.questions[quiz.i];
    const fb = el("div", { className: "fb hidden" });
    const next = el("button", { className: "primary block hidden", textContent: quiz.i + 1 === total ? "See score" : "Next" });
    const opts = q.options.map((text, idx) => {
      const b = el("button", { className: "opt" },
        el("span", { className: "k", textContent: "ABCD"[idx] }), el("span", { textContent: text }));
      b.onclick = async () => {
        opts.forEach((o) => { o.disabled = true; });
        try {
          const r = await api("/live/quiz/answer", { session_id: SID, question_id: q.id, chosen_index: idx });
          opts[r.answer_index].classList.add("right");
          if (r.correct) quiz.score++; else b.classList.add("wrong");
          fb.replaceChildren(el("strong", { textContent: r.correct ? "Correct. " : "Not quite. " }), inline(r.explanation || ""));
          fb.classList.remove("hidden");
          next.classList.remove("hidden");
          revealInView(next);
        } catch (e) {
          opts.forEach((o) => { o.disabled = false; });
          fb.replaceChildren(el("span", { textContent: e.message }));
          fb.classList.remove("hidden");
        }
      };
      return b;
    });
    next.onclick = () => { quiz.i++; renderQuestion(); };
    card.replaceChildren(
      el("div", { className: "bar" }, el("div", { style: `width:${(quiz.i / total) * 100}%` })),
      el("div", { className: "qmeta", textContent: `Question ${quiz.i + 1} of ${total}` }),
      el("div", { className: "q", textContent: q.q }),
      ...opts, fb, next,
    );
  }

  // Deep link: /ask#quiz opens the quiz tab. Must run last, after `quiz` is declared.
  if (location.hash === "#quiz") showTab("quiz");
})();
