// Leaderboard. Nicknames come from visitors, so everything is inserted with textContent.
function cells(values) {
  const tr = document.createElement("tr");
  for (const v of values) {
    const td = document.createElement("td");
    td.textContent = String(v);
    tr.append(td);
  }
  return tr;
}

async function main() {
  const data = await (await fetch("/api/leaderboard")).json();
  document.getElementById("totals").textContent =
    `${data.totals.attempts} attempts so far, ${data.totals.successes} successful.`;
  const players = document.getElementById("players");
  data.players.forEach((p, i) => players.append(cells([i + 1, p.nickname, p.best_level, p.wins])));
  const levels = document.getElementById("levels");
  for (const [level, v] of Object.entries(data.by_level)) {
    levels.append(cells([level, v.attempts, v.successes]));
  }
  const recent = document.getElementById("recent");
  for (const r of data.recent_wins) {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = `/trace.html?id=${encodeURIComponent(r.trace_id)}`;
    a.textContent = `${r.nickname} beat level ${r.level} (${r.goal}, via ${r.channel})`;
    li.append(a);
    recent.append(li);
  }
}
main();
