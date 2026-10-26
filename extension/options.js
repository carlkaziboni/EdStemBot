const DEFAULTS = { apiBase: "http://127.0.0.1:8000", secret: "" };
const $ = (id) => document.getElementById(id);

chrome.storage.sync.get(DEFAULTS).then((s) => {
  $("apiBase").value = s.apiBase;
  $("secret").value = s.secret;
});

$("save").onclick = async () => {
  const apiBase = $("apiBase").value.trim() || DEFAULTS.apiBase;
  // The manifest only grants access to localhost; reject anything else early.
  if (!/^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?\/?$/.test(apiBase)) {
    $("status").textContent = "URL must be http://127.0.0.1 or http://localhost";
    return;
  }
  await chrome.storage.sync.set({ apiBase, secret: $("secret").value });
  $("status").textContent = "Saved.";
};
