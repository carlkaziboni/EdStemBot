// askEd presenter page: join screen with QR, then a live reveal of the weakest topics.
(() => {
  const $ = (id) => document.getElementById(id);
  const key = new URLSearchParams(location.search).get("key") || "";
  let reveal = false;
  let lastOk = 0;

  function el(tag, props = {}, ...kids) {
    const node = Object.assign(document.createElement(tag), props);
    node.append(...kids);
    return node;
  }

  function setPhase(showResults) {
    reveal = showResults;
    $("join").classList.toggle("hidden", reveal);
    $("reveal").classList.toggle("hidden", !reveal);
    $("toggle").textContent = reveal ? "Show QR (space)" : "Show results (space)";
  }
  $("toggle").onclick = () => { setPhase(!reveal); $("toggle").blur(); }; // blur: keep Space from double-toggling
  document.addEventListener("keydown", (e) => {
    if (e.code === "Space") { e.preventDefault(); setPhase(!reveal); }
  });

  // Green (confident) to red (struggled): 0% incorrect is green, 60%+ is fully red.
  const colour = (pct) => `hsl(${Math.max(0, Math.round(120 - pct * 2))} 72% 52%)`;

  function render(d) {
    $("people").textContent = d.participants;
    $("totals").textContent =
      `${d.participants} ${d.participants === 1 ? "person" : "people"} · ${d.attempts} quiz answers · ${d.questions_asked} questions asked` +
      (d.needs_followup ? ` · ${d.needs_followup} need follow-up (not answered from the materials)` : "");

    const topics = $("topics");
    if (!d.topics.length) {
      topics.replaceChildren(el("div", { className: "empty", textContent: "No quiz answers yet." }));
    } else {
      topics.replaceChildren(...d.topics.map((t, i) => {
        const row = el("div", { className: "trow" + (t.ranked ? "" : " low") });
        const label = t.ranked
          ? `${t.pct_incorrect}% incorrect · ${t.attempts} answers`
          : `needs ${d.min_attempts - t.attempts} more answers`;
        row.append(
          el("div", { className: "head" },
            el("span", { textContent: t.topic }), el("span", { textContent: label })),
          el("div", { className: "track" },
            el("div", { className: "fill", style: `width:${t.pct_incorrect}%;background:${colour(t.pct_incorrect)}` })),
        );
        const h = t.hardest_question;
        if (t.ranked && i < 3 && h) {
          const text = el("div", { className: "hard" },
            el("b", { textContent: `${h.pct_incorrect}% missed: ` }), document.createTextNode(h.q));
          if (h.top_wrong && h.top_wrong.text) {
            text.append(el("div", { textContent: `Most common wrong answer: ${h.top_wrong.text}` }));
          }
          row.append(text);
        }
        return row;
      }));
    }

    const asked = $("asked");
    asked.replaceChildren(...(d.asked_topics.length
      ? d.asked_topics.slice(0, 8).map((a) =>
          el("div", { className: "askrow" }, el("span", { textContent: a.topic }), el("b", { textContent: a.count })))
      : [el("div", { className: "empty", textContent: "No questions yet." })]));
  }

  async function poll() {
    try {
      const res = await fetch("/live/stats", { headers: { "X-Presenter-Key": key } });
      if (res.status === 401) {
        $("status").textContent = "Wrong or missing presenter key. ";
      } else if (!res.ok) {
        $("status").textContent = `Server error ${res.status}. `;
      } else {
        render(await res.json());
        lastOk = Date.now();
        $("status").textContent = "";
      }
    } catch {
      $("status").textContent = Date.now() - lastOk > 9000 ? "Offline, retrying. " : "";
    }
  }
  // /present?key=...&view=results opens straight on the reveal (useful as a rehearsal bookmark).
  if (new URLSearchParams(location.search).get("view") === "results") setPhase(true);
  poll();
  setInterval(poll, 3000);
})();
