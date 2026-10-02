const known = new Set((window.__KNOWN__ || []).map(String));
const ids = new Set();
for (const page of [1, 2, 3]) {
  const h = await (await fetch('/battles?mine=1&page=' + page)).text();
  for (const m of h.matchAll(/\/battles\/(\d+)/g)) ids.add(m[1]);
}
const out = [];
for (const id of [...ids].sort((a, b) => b - a)) {
  if (known.has(id)) continue;
  const h = await (await fetch('/battles/' + id)).text();
  const mm = h.match(/match:\{id:(\d+),teamAId:(\d+),teamBId:(\d+),mapId:\d+,ranked:(true|false).*?status:"(\w+)"/);
  if (!mm || mm[5] !== 'completed') continue;
  const names = h.match(/teamAName:"([^"]*)",teamBName:"([^"]*)",teamAElo:(\d+),teamBElo:(\d+)/);
  const side = mm[2] === '852' ? 'a' : 'b';
  const games = [...h.matchAll(/\{id:(\d+),status:"(\w+)",winner:(?:"(\w)"|null),hasReplay:(true|false),mapName:"([^"]*)"\}/g)]
    .map(g => [g[1], g[5].replace(/ /g, '_'), g[2] === 'completed' ? (g[3] === side ? 'W' : g[3] ? 'L' : 'D') : g[2], g[4] === 'true' ? 1 : 0]);
  if (games.some(g => g[2] !== 'W' && g[2] !== 'L' && g[2] !== 'D')) continue;
  out.push([id, mm[4] === 'true' ? 'R' : 'U', mm[5], (side === 'a' ? names[2] : names[1]).replace(/\s+/g, '_'), side === 'a' ? names[4] : names[3], side.toUpperCase(), games.map(g => g.join(':')).join(',')].join(' '));
}
const hp = (await (await fetch('/')).text()).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
const i = hp.indexOf('Rating');
out.join('\n') + '\nHOME ' + hp.slice(i, i + 90)
