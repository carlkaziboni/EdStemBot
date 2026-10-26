// Service worker: talks to the local EdStemBot API. The content script never
// sees the secret; it only sends {kind, payload} messages.

const DEFAULTS = { apiBase: "http://127.0.0.1:8000", secret: "" };

async function callApi(kind, payload) {
  if (kind !== "answer" && kind !== "quiz") throw new Error("bad request kind");
  const { apiBase, secret } = await chrome.storage.sync.get(DEFAULTS);
  if (!secret) throw new Error("Set the shared secret in the extension options.");
  let res;
  try {
    res = await fetch(`${apiBase.replace(/\/$/, "")}/ext/${kind}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-EdStemBot-Key": secret },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error("Cannot reach the EdStemBot server. Is it running?");
  }
  if (res.status === 401) throw new Error("Wrong secret. Check the extension options.");
  if (res.status === 404) throw new Error("No course material matches this thread.");
  if (!res.ok) throw new Error(`Server error (${res.status}).`);
  return res.json();
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id) return;
  callApi(msg.kind, msg.payload)
    .then((data) => sendResponse({ ok: true, data }))
    .catch((err) => sendResponse({ ok: false, error: err.message }));
  return true; // async response
});
