// Renders the small Markdown subset used by results_table.md and limitations.md with DOM calls
// (headings, pipe tables, lists, paragraphs). Text is always set with textContent.
function el(tag, text) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  return node;
}

function strip(text) {
  return text.replace(/\*\*(.+?)\*\*/g, "$1").replace(/`([^`]+)`/g, "$1");
}

function renderTable(lines) {
  const table = el("table");
  lines.forEach((line, i) => {
    if (/^\|[-| ]+\|$/.test(line.trim())) return;
    const cells = line.trim().replace(/^\||\|$/g, "").split("|");
    const tr = el("tr");
    for (const c of cells) tr.append(el(i === 0 ? "th" : "td", strip(c.trim())));
    table.append(tr);
  });
  const wrap = el("div");
  wrap.className = "scroll";
  wrap.append(table);
  return wrap;
}

function render(markdown, target) {
  target.replaceChildren();
  const lines = markdown.split("\n");
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.startsWith("|")) {
      const block = [];
      while (i < lines.length && lines[i].startsWith("|")) block.push(lines[i++]);
      target.append(renderTable(block));
      continue;
    }
    if (line.startsWith("# ")) target.append(el("h2", strip(line.slice(2))));
    else if (line.startsWith("## ")) target.append(el("h3", strip(line.slice(3))));
    else if (/^(- |\d+\. )/.test(line)) target.append(el("p", "• " + strip(line.replace(/^(- |\d+\. )/, ""))));
    else if (line.trim()) target.append(el("p", strip(line)));
    i++;
  }
}

async function main() {
  const data = await (await fetch("/api/results")).json();
  const charts = document.getElementById("charts");
  for (const name of data.charts) {
    const img = document.createElement("img");
    img.src = `/api/results/chart/${encodeURIComponent(name)}`;
    img.alt = name.replace(/^chart_|\.png$/g, "").replace(/_/g, " ");
    img.className = "chart";
    charts.append(img);
  }
  render(data.table || "No results published yet.", document.getElementById("table"));
  render(data.limitations || "", document.getElementById("limitations"));
}
main();
