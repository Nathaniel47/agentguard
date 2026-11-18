// Arena form. Server text (answers, nicknames) is inserted with textContent, never as HTML.
const $ = (id) => document.getElementById(id);

function fill(select, entries) {
  for (const [value, label] of Object.entries(entries)) {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    select.append(opt);
  }
}

async function loadOptions() {
  const o = await (await fetch("/api/arena/options")).json();
  fill($("level"), o.levels);
  fill($("goal"), o.goals);
  fill($("channel"), o.channels);
  $("remaining").textContent = `${o.remaining_today} attempts left today`;
}

function show(kind, lines, traceId) {
  const box = $("result");
  box.hidden = false;
  box.className = `result ${kind}`;
  box.replaceChildren();
  for (const line of lines) {
    const p = document.createElement("p");
    p.textContent = line;
    box.append(p);
  }
  if (traceId) {
    const a = document.createElement("a");
    a.href = `/trace.html?id=${encodeURIComponent(traceId)}`;
    a.textContent = "See what the assistant did, step by step";
    box.append(a);
  }
}

$("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("go").disabled = true;
  try {
    const resp = await fetch("/api/arena/attempt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nickname: $("nickname").value,
        level: Number($("level").value),
        goal: $("goal").value,
        channel: $("channel").value,
        text: $("text").value,
      }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      show("safe", [data.error || JSON.stringify(data.detail || data)]);
      return;
    }
    const lines = [data.success ? "You won: the goal was reached." : "Not this time: the goal was not reached."];
    if (data.guardrails_triggered.length) lines.push(`Guardrails that acted: ${data.guardrails_triggered.join(", ")}`);
    lines.push(`Assistant's answer: ${data.answer}`);
    show(data.success ? "win" : "safe", lines, data.trace_id);
    $("remaining").textContent = `${data.remaining_today} attempts left today`;
  } catch (err) {
    show("safe", ["Could not reach the server."]);
  } finally {
    $("go").disabled = false;
  }
});

loadOptions();
