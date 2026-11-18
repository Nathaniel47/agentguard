// Renders one trace as a timeline. Everything is inserted with textContent: trace text contains
// attacker-written strings, so it must never be parsed as HTML.
const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
};

function headline(span) {
  const a = span.attrs;
  switch (span.kind) {
    case "input": return `User: ${a.text}`;
    case "llm": return `Model reply (${a.tokens} tokens): ${a.reply}`;
    case "tool": return `${span.name}(${JSON.stringify(a.args)})${a.blocked ? " — not run" : ""}`;
    case "guardrail": return `${span.name} @ ${a.hook}: ${a.action}${a.reason ? " — " + a.reason : ""}`;
    case "memory": return `Memory ${span.name}${a.text ? ": " + a.text : ""}`;
    case "output": return `Answer (${a.status}): ${a.text}`;
    default: return span.name;
  }
}

function render(trace) {
  const spans = trace.spans;
  const blocks = spans.filter((s) => s.kind === "guardrail" && s.attrs.action === "block").length;
  const flags = spans.filter((s) => s.kind === "guardrail" && s.attrs.action === "flag").length;
  document.getElementById("summary").textContent =
    `${trace.label || trace.id} · ${spans.length} spans · ${blocks} blocked · ${flags} flagged`;
  const list = document.getElementById("timeline");
  list.replaceChildren();
  for (const span of spans) {
    const action = span.kind === "guardrail" ? span.attrs.action : "";
    const li = el("li", `span ${span.kind} ${action}`);
    li.append(el("span", "badge", span.kind));
    li.append(el("span", "head", headline(span)));
    li.append(el("span", "time muted", `+${span.start_s.toFixed(2)}s`));
    const detail = el("pre", "detail", JSON.stringify(span.attrs, null, 2));
    li.append(detail);
    li.addEventListener("click", () => li.classList.toggle("open"));
    list.append(li);
  }
}

async function main() {
  const id = new URLSearchParams(location.search).get("id");
  if (id) {
    const resp = await fetch(`/api/trace/${encodeURIComponent(id)}`);
    if (!resp.ok) {
      document.getElementById("summary").textContent = "Trace not found.";
      return;
    }
    render(await resp.json());
    return;
  }
  document.getElementById("summary").textContent = "Recent traces";
  const items = await (await fetch("/api/traces")).json();
  const ul = document.getElementById("recent");
  for (const item of items) {
    const li = el("li");
    const a = el("a", "", item.label || item.id);
    a.href = `/trace.html?id=${encodeURIComponent(item.id)}`;
    li.append(a);
    ul.append(li);
  }
  if (!items.length) document.getElementById("summary").textContent = "No traces yet.";
}
main();
