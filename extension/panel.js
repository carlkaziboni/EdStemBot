// Shadow-DOM panel: answer preview + one-question-at-a-time MCQ quiz.
// Builds DOM nodes only (never innerHTML) because content comes from an LLM.

window.EdPanel = (() => {
  const CSS = `
    :host { all: initial; display: block; max-width: 100%; }
    * { box-sizing: border-box; }
    .box { font: 14px/1.55 system-ui, -apple-system, sans-serif; color: #1f2430; background: #fff;
           border: 1px solid #d5d9e2; border-radius: 12px; margin: 12px 0; width: 100%;
           max-width: 100%; overflow: hidden; overflow-wrap: anywhere; }
    .box.float { position: fixed; right: 16px; bottom: 16px; width: min(380px, calc(100vw - 32px));
                 z-index: 2147483000; box-shadow: 0 8px 28px rgba(0,0,0,.25); margin: 0; }
    header { display: flex; justify-content: space-between; align-items: center;
             padding: 10px 14px; cursor: pointer; font-weight: 600; font-size: 14px; user-select: none; }
    .chev { transition: transform .15s; }
    .open .chev { transform: rotate(180deg); }
    .body { display: none; padding: 0 14px 14px; max-height: min(70vh, 560px); overflow-y: auto; }
    .open .body { display: block; }
    .tabs { display: flex; gap: 6px; margin-bottom: 12px; position: sticky; top: 0;
            background: inherit; padding-bottom: 4px; }
    button { font: inherit; font-size: 13px; color: inherit; border: 1px solid #c3c9d6; background: #f4f6fa;
             border-radius: 8px; padding: 5px 12px; cursor: pointer; }
    button:hover:not(:disabled) { border-color: #2b5cff; }
    button.on { background: #2b5cff; border-color: #2b5cff; color: #fff; }
    .muted { color: #667085; font-size: 12px; margin-top: 8px; }
    .err { color: #b42318; background: #fee4e2; padding: 8px 10px; border-radius: 8px; }
    .chips { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 10px; }
    .chip { font-size: 11px; padding: 2px 8px; border-radius: 99px; background: #e8eeff; color: #2b4fcc; }
    .md p { margin: 0 0 8px; }
    .md ul, .md ol { margin: 0 0 8px; padding-left: 20px; }
    .md code { font: 12.5px ui-monospace, Menlo, monospace; background: rgba(120,130,160,.18);
               padding: 1px 5px; border-radius: 4px; }
    .md h4 { margin: 10px 0 4px; font-size: 14px; }
    .md a { color: #2b5cff; }
    .qmeta { font-size: 12px; color: #667085; margin-bottom: 6px; }
    .q { font-weight: 600; margin-bottom: 10px; }
    .opt { display: flex; gap: 10px; align-items: flex-start; width: 100%; text-align: left;
           margin: 0 0 8px; padding: 9px 12px; background: transparent; font-size: 14px; }
    .opt .k { flex: none; width: 22px; height: 22px; border-radius: 50%; border: 1px solid currentColor;
              display: inline-flex; align-items: center; justify-content: center; font-size: 11px; opacity: .7; }
    .opt.right { background: #d1fadf; border-color: #12b76a; color: #054f31; }
    .opt.wrong { background: #fee4e2; border-color: #f04438; color: #7a271a; }
    .opt:disabled { cursor: default; }
    .fb { margin: 4px 0 10px; padding: 8px 10px; border-radius: 8px; background: rgba(120,130,160,.14); }
    .score { font-size: 18px; font-weight: 600; margin-bottom: 10px; }
    .bar { height: 4px; background: rgba(120,130,160,.25); border-radius: 4px; margin-bottom: 12px; }
    .bar > div { height: 100%; background: #2b5cff; border-radius: 4px; }
    @media (prefers-color-scheme: dark) {
      .box { background: #1b1f2a; color: #e6e9f0; border-color: #3a4152; }
      button { background: #272d3b; border-color: #4a5268; }
      .muted, .qmeta { color: #9aa3b8; }
      .chip { background: #26325a; color: #b8c8ff; }
      .err { background: #3b1a17; color: #fda29b; }
      .md a { color: #8aa4ff; }
      .opt.right { background: #0b3d27; color: #a6f4c5; }
      .opt.wrong { background: #4a1c18; color: #fda29b; }
    }`;

  function el(tag, props = {}, ...kids) {
    const node = Object.assign(document.createElement(tag), props);
    node.append(...kids);
    return node;
  }

  // Inline markdown: **bold**, *italic*, `code`, [text](https://...), bare URLs.
  function inline(text) {
    const frag = document.createDocumentFragment();
    const re = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\(https?:\/\/[^)\s]+\)|\*[^*\s][^*]*\*|https?:\/\/[^\s)]+)/g;
    let last = 0;
    for (const m of text.matchAll(re)) {
      if (m.index > last) frag.append(text.slice(last, m.index));
      const t = m[0];
      if (t.startsWith("**")) frag.append(el("strong", { textContent: t.slice(2, -2) }));
      else if (t.startsWith("`")) frag.append(el("code", { textContent: t.slice(1, -1) }));
      else if (t.startsWith("[")) {
        const [, label, url] = t.match(/\[([^\]]+)\]\(([^)]+)\)/);
        frag.append(el("a", { textContent: label, href: url, target: "_blank", rel: "noopener noreferrer" }));
      } else if (t.startsWith("http")) {
        frag.append(el("a", { textContent: t, href: t, target: "_blank", rel: "noopener noreferrer" }));
      } else frag.append(el("em", { textContent: t.slice(1, -1) }));
      last = m.index + t.length;
    }
    if (last < text.length) frag.append(text.slice(last));
    return frag;
  }

  // Block markdown: headings, bullet/numbered lists, paragraphs.
  function markdown(src) {
    const root = el("div", { className: "md" });
    let list = null;
    let para = [];
    const flushPara = () => {
      if (para.length) root.append(el("p", {}, inline(para.join(" "))));
      para = [];
    };
    for (const line of src.split("\n")) {
      const h = line.match(/^#{1,6}\s+(.*)/);
      const li = line.match(/^\s*(?:[-*•]|(\d+)[.)])\s+(.*)/);
      if (li) {
        flushPara();
        const ordered = Boolean(li[1]);
        if (!list || list.tagName !== (ordered ? "OL" : "UL")) {
          list = el(ordered ? "ol" : "ul");
          root.append(list);
        }
        list.append(el("li", {}, inline(li[2])));
        continue;
      }
      list = null;
      if (h) { flushPara(); root.append(el("h4", {}, inline(h[1]))); }
      else if (!line.trim()) flushPara();
      else para.push(line.trim());
    }
    flushPara();
    return root;
  }

  function create({ onRequest }) {
    const host = el("div");
    host.id = "edstembot-panel";
    const root = host.attachShadow({ mode: "closed" });
    root.append(el("style", { textContent: CSS }));

    const box = el("div", { className: "box" });
    const header = el("header", {}, el("span", { textContent: "EdStemBot study helper" }), el("span", { className: "chev", textContent: "▾" }));
    const content = el("div", { className: "body" });
    box.append(header, content);
    root.append(box);

    const tabAnswer = el("button", { textContent: "Answer preview" });
    const tabQuiz = el("button", { textContent: "Quiz me" });
    const view = el("div");
    content.append(el("div", { className: "tabs" }, tabAnswer, tabQuiz), view);

    let quiz = null;
    let answerData = null;

    function setTab(which) {
      tabAnswer.classList.toggle("on", which === "answer");
      tabQuiz.classList.toggle("on", which === "quiz");
      if (which === "answer") showAnswer(); else showQuiz();
    }

    function message(text, cls = "muted") {
      view.replaceChildren(el("div", { className: cls, textContent: text }));
    }

    async function showAnswer() {
      if (answerData) return renderAnswer(answerData);
      message("Generating preview…");
      const res = await onRequest("answer", {});
      if (!res?.ok) return message(res?.error || "No response from extension.", "err");
      answerData = res.data;
      renderAnswer(answerData);
    }

    function renderAnswer(d) {
      const chips = el("div", { className: "chips" },
        ...d.topics.map((t) => el("span", { className: "chip", textContent: t })));
      const meta = `Match confidence ${Math.round(d.confidence * 100)}%` +
        (d.sources.length ? ` · ${d.sources.join(", ")}` : "");
      view.replaceChildren(
        markdown(d.answer), chips,
        el("div", { className: "muted", textContent: meta }),
        el("div", { className: "muted", textContent: "AI preview from course notes, not an official answer." }),
      );
    }

    async function showQuiz(refresh = false) {
      if (quiz && !refresh) return renderQuestion();
      message("Writing quiz questions…");
      const res = await onRequest("quiz", { refresh });
      if (!res?.ok) return message(res?.error || "No response from extension.", "err");
      quiz = { ...res.data, i: 0, score: 0 };
      renderQuestion();
    }

    function renderQuestion() {
      const total = quiz.questions.length;
      if (quiz.i >= total) {
        const again = el("button", { textContent: "New questions" });
        again.onclick = () => showQuiz(true);
        const retry = el("button", { textContent: "Retry these" });
        retry.onclick = () => { quiz.i = 0; quiz.score = 0; renderQuestion(); };
        return view.replaceChildren(
          el("div", { className: "score", textContent: `${quiz.score} / ${total} correct` }),
          el("div", { className: "muted", textContent: quiz.topic }),
          el("div", { style: "display:flex;gap:6px;margin-top:12px" }, again, retry),
        );
      }
      const q = quiz.questions[quiz.i];
      const fb = el("div", { className: "fb", hidden: true });
      const next = el("button", { textContent: quiz.i + 1 === total ? "See score" : "Next →", hidden: true });
      const opts = q.options.map((text, idx) => {
        const b = el("button", { className: "opt" },
          el("span", { className: "k", textContent: "ABCD"[idx] }), el("span", { textContent: text }));
        b.onclick = () => {
          opts.forEach((o, j) => { o.disabled = true; if (j === q.answer_index) o.classList.add("right"); });
          const ok = idx === q.answer_index;
          if (ok) quiz.score++; else b.classList.add("wrong");
          fb.replaceChildren(el("strong", { textContent: ok ? "Correct. " : "Not quite. " }), inline(q.explanation));
          fb.hidden = false;
          next.hidden = false;
        };
        return b;
      });
      next.onclick = () => { quiz.i++; renderQuestion(); };
      const bar = el("div", { className: "bar" }, el("div", { style: `width:${(quiz.i / total) * 100}%` }));
      view.replaceChildren(
        bar,
        el("div", { className: "qmeta", textContent: `Question ${quiz.i + 1} of ${total} · ${quiz.topic}` }),
        el("div", { className: "q" }, inline(q.q)),
        ...opts, fb, next,
      );
    }

    tabAnswer.onclick = () => setTab("answer");
    tabQuiz.onclick = () => setTab("quiz");

    // No LLM call until the student first opens the panel.
    let started = false;
    header.onclick = () => {
      box.classList.toggle("open");
      if (!started && box.classList.contains("open")) {
        started = true;
        setTab("answer");
      }
    };

    return {
      host,
      mount(anchor) {
        if (anchor) { box.classList.remove("float"); anchor.after(host); }
        else { box.classList.add("float"); document.body.append(host); }
      },
      remove() { host.remove(); },
    };
  }

  return { create };
})();
