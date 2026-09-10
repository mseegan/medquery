const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message-input");
const roleSelect = document.getElementById("role-select");
const userIdInput = document.getElementById("user-id-input");

const sessionId = crypto.randomUUID();

roleSelect.addEventListener("change", () => {
  userIdInput.value = roleSelect.value === "doctor" ? "D001" : "P001";
});

function addBubble(text, kind) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${kind}`;
  bubble.textContent = text;
  chatLog.appendChild(bubble);
  chatLog.scrollTop = chatLog.scrollHeight;
  return bubble;
}

function addMeta(container, text) {
  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = text;
  container.appendChild(meta);
}

function addDisclaimer(container, text) {
  const disclaimer = document.createElement("div");
  disclaimer.className = "disclaimer";
  disclaimer.textContent = text;
  container.appendChild(disclaimer);
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();
  if (!message) return;

  addBubble(message, "user");
  messageInput.value = "";
  messageInput.disabled = true;

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        role: roleSelect.value,
        user_id: userIdInput.value.trim(),
        message,
      }),
    });

    if (!response.ok) {
      const detail = await response.text();
      addBubble(`Error: ${detail}`, "error");
      return;
    }

    const data = await response.json();
    const bubble = addBubble(data.reply, "assistant");
    if (data.agent_trace && data.agent_trace.length > 0) {
      addMeta(bubble, `via ${data.agent_trace.join(", ")}`);
    }
    if (data.disclaimer) {
      addDisclaimer(bubble, data.disclaimer);
    }
  } catch (err) {
    addBubble(`Error: ${err}`, "error");
  } finally {
    messageInput.disabled = false;
    messageInput.focus();
  }
});
