// Detects EdStem thread pages (a single-page app), reads the title/body from
// the DOM, and mounts the study panel. Never writes to EdStem or posts anything.

(() => {
  let currentThread = null;
  let panel = null;
  let timer = null;

  function request(kind, extra) {
    const payload = {
      title: EdSelectors.title(),
      body: EdSelectors.body(),
      ...extra,
    };
    return chrome.runtime.sendMessage({ kind, payload });
  }

  function sync() {
    const id = EdSelectors.threadId();
    if (id === currentThread && (!id || panel)) return;
    panel?.remove();
    panel = null;
    currentThread = id;
    console.log("[EdStemBot] thread id:", id, "url:", location.pathname);
    if (!id) return;
    panel = EdPanel.create({ onRequest: request });
    const anchor = EdSelectors.anchor();
    console.log("[EdStemBot] mounting panel", anchor ? "inline" : "floating", "title:", EdSelectors.title());
    panel.mount(anchor);
  }

  // Debounced: EdStem mutates the DOM constantly.
  const schedule = () => {
    clearTimeout(timer);
    timer = setTimeout(sync, 400);
  };
  new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
  console.log("[EdStemBot] content script loaded on", location.href);
  sync();
})();
