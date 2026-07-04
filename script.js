// If the frontend is served by FastAPI, same-origin "" works.
// If you host the frontend separately (e.g. GitHub Pages), set this to
// your backend URL, e.g. "https://your-backend.onrender.com".
const API_BASE = "";

const thread = document.getElementById("thread");
const welcome = document.getElementById("welcome");
const form = document.getElementById("composer");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");

// Full conversation history sent to the model each turn.
const history = [
  { role: "system", content: "You are a helpful, concise assistant." },
];

let busy = false;

// ---------- health check ----------
(async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    const data = await res.json();
    statusDot.classList.add("online");
    statusText.textContent = data.model || "ready";
  } catch {
    statusDot.classList.add("offline");
    statusText.textContent = "backend offline";
  }
})();

// ---------- helpers ----------
function addMessage(role, text) {
  welcome?.remove();
  const el = document.createElement("div");
  el.className = `msg ${role}`;
  el.textContent = text;
  thread.appendChild(el);
  thread.scrollTop = thread.scrollHeight;
  return el;
}

function showTyping() {
  welcome?.remove();
  const el = document.createElement("div");
  el.className = "msg assistant";
  el.innerHTML = '<div class="typing"><span></span><span></span><span></span></div>';
  thread.appendChild(el);
  thread.scrollTop = thread.scrollHeight;
  return el;
}

function autoGrow() {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 160) + "px";
}
input.addEventListener("input", autoGrow);

// Enter to send, Shift+Enter for newline.
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});

// ---------- send ----------
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text || busy) return;

  busy = true;
  sendBtn.disabled = true;
  input.value = "";
  autoGrow();

  addMessage("user", text);
  history.push({ role: "user", content: text });

  const typingEl = showTyping();

  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: history, max_tokens: 512, temperature: 0.7 }),
    });

    if (!res.ok) throw new Error(`server responded ${res.status}`);

    const data = await res.json();
    typingEl.remove();
    addMessage("assistant", data.reply);
    history.push({ role: "assistant", content: data.reply });
  } catch (err) {
    typingEl.remove();
    const el = addMessage("error", `Couldn't reach the model. ${err.message}`);
    el.className = "msg error";
  } finally {
    busy = false;
    sendBtn.disabled = false;
    input.focus();
  }
});
