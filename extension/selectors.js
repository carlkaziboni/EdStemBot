// All EdStem DOM knowledge lives here. EdStem is a SPA whose markup can change,
// so each lookup is a fallback chain. Adjust here if the panel stops appearing.
// Everything is read-only: we never modify EdStem's own elements.

window.EdSelectors = {
  // Thread URLs look like /courses/<cid>/discussion/<tid>
  threadId() {
    const m = location.pathname.match(/\/courses\/(\d+)\/discussion\/(\d+)/);
    return m ? `${m[1]}:${m[2]}` : null;
  },

  title() {
    const candidates = [
      "[class*='thread'] h1",
      "main h1",
      "h1",
      "[class*='title']",
    ];
    for (const sel of candidates) {
      const el = document.querySelector(sel);
      const text = el && el.innerText.trim();
      if (text) return text;
    }
    return document.title.replace(/\s*[|·-]\s*Ed.*$/i, "").trim();
  },

  body() {
    const candidates = [
      "[class*='thread-view'] [class*='content']",
      "[class*='dccb']",
      "[class*='document'] ",
      "main article",
      "main",
    ];
    for (const sel of candidates) {
      const el = document.querySelector(sel);
      const text = el && el.innerText.trim();
      if (text && text.length > 20) return text.slice(0, 6000);
    }
    return "";
  },

  // Element after which the panel is inserted; null means float bottom-right.
  anchor() {
    return document.querySelector("[class*='thread-view'] h1")?.parentElement ?? null;
  },
};
