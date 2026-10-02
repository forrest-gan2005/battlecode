const seen = new Set();
const out = [];
for (const page of ['/battles?mine=1', '/battles?mine=1&page=2']) {
  const h = await (await fetch(page)).text();
  for (const m of h.matchAll(/\/battles\/(\d+)/g)) seen.add(m[1]);
}
for (const id of [...seen].slice(0, 25)) {
  const h = await (await fetch('/battles/' + id)).text();
  const mm = h.match(/match:\{id:(\d+),teamAId:(\d+),teamBId:(\d+),mapId:\d+,ranked:(true|false)[^}]*?status:\\?"(\w+)\\?"/) || h.match(/match:\{id:(\d+),teamAId:(\d+),teamBId:(\d+),mapId:\d+,ranked:(true|false).*?status:"(\w+)"/);
  if (!mm) continue;
  const names = h.match(/teamAName:"([^"]*)",teamBName:"([^"]*)",teamAElo:(\d+),teamBElo:(\d+)/);
  const side = mm[2] === '852' ? 'a' : 'b';
  const games = [...h.matchAll(/\{id:(\d+),status:"(\w+)",winner:(?:"(\w)"|null),hasReplay:(true|false),mapName:"([^"]*)"\}/g)]
    .map(g => [g[1], g[5].replace(/ /g, '_'), g[2] === 'completed' ? (g[3] === side ? 'W' : g[3] ? 'L' : 'D') : g[2], g[4] === 'true' ? 1 : 0]);
  const opp = names ? (side === 'a' ? names[2] : names[1]) : '?';
  const oe = names ? (side === 'a' ? names[4] : names[3]) : '?';
  out.push([id, mm[4] === 'true' ? 'R' : 'U', mm[5], opp.replace(/\s+/g, '_'), oe, side.toUpperCase(), games.map(g => g.join(':')).join(',')].join(' '));
}
out.join('\n')
