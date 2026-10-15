# meow: UNSW Battlecode 2026

中文版: branch [`qwq/readme-zh`](../../tree/qwq/readme-zh)

This is the team repository of **meow** (team 1119) for UNSW Battlecode 2026. In this two-week contest, teams write
autonomous agents for a snake-like game on a wrap-around grid. The agents play each other on a public ladder and then
in a knockout bracket on maps nobody has seen.

This README is written from my side of the project (QWQ, [forrest-gan2005](https://github.com/forrest-gan2005)). I
built the base bot that the team shipped, the local testing setup that every change went through, and most of the
strategy work: reading replays, finding why we lost, and deciding what to try next.

## At a glance

| | |
|---|---|
| Contest | UNSW Battlecode 2026, 2026-09-25 to 2026-10-10 |
| Team | QWQ (me), jun ([juntegral](https://github.com/juntegral)) and Zhe ([zhex0121](https://github.com/zhex0121)); the team formed on 2026-10-02 |
| My part | Base bot, local testing rig and A/B method, strategy and replay analysis |
| Final bot | `one21`: the base bot in `mybot2/` (8,657 lines of C++ on branch `one15-profile`) plus a profile of 49 switch values |
| Ladder | Peak rank **10**, final rank **38** |
| Qualifiers | Seed 36. Won 7-0 against Extreme Maestro and 6-1 against Knight Capital, then lost 2-5 to PhoBoDacBiet (seed 29) in the round of 64 |
| Scale | About 60 uploaded versions (v9 to v61, then the team's `one*` line), about 45,000 recorded local games, hundreds of generated maps for unseen-map testing |

## The game in brief

- Each team controls dragons: a head followed by body segments.
  - A dragon moves one tile per turn and grows by eating pearls.
  - It can split into two dragons; each part must be at least 2 long.
  - A sprint covers several tiles in one turn. The first ceil(L/4) steps are free; each later step costs a segment.
- Moving into a wall, a body or another head kills the dragon, and its body turns into pearls. Head-on kills both.
- Every map wraps around (a torus). Edges between tiles can be open, kelp (a wall) or a portal. Each dragon sees only
  a 7x7 window, and teammates can talk only by sonar: one 64-bit message per direction per turn.
- After the Sprint tournament the rules changed: dragons 0 and 1 became queens. A game not ended by elimination is
  decided at round 500 by the longer queen, where a dead queen counts as 0. Ties go to the longest dragon, then to
  total length.
- Each dragon runs as its own program under a per-turn compute limit. The unit cap is 64 dragons per team.

## What I built

### 1. The base bot (`mybot2/`)

The bot the team shipped is my base bot with the team's switches on top. Teammates added behaviour as default-off
switches; I wrote the core it runs on. One C++ file, one dragon per process, and the same decision loop every turn:

1. **Observe and remember** (`observe`, `extend_trail_from_vision`)
   - Keeps a map memory: when each tile was last seen, edge types, pearls and spawn timers.
   - Tracks bodies seen in vision and when each body cell will be free again (`enter_time`). Pathing uses this to
     step into cells that empty in time.
   - Keeps "ghosts": the last known positions of enemy heads that are now out of sight.
2. **Infer the map** (`update_symmetry`)
   - Every map is a mirror or a 180° rotation, and a tile shares its pearl countdown with its mirror tile.
   - The bot tests the three symmetry hypotheses against what it has seen and keeps the one that survives. It then
     knows edges and spawn timers on the far side of the map without seeing them.
3. **Talk** (`hear_sonar`, `broadcast_leader`, `sonar_codec.hpp`)
   - Sonar messages are sealed with a per-map, per-team key so that enemy messages are rejected.
   - They carry the current leader (id, length, position), enemy head sightings including the enemy queen, portal
     mouths, and safe-zone data.
4. **Survey and score** (`Survey`, `pick_direction`, `score_step`)
   - For each legal step, the bot runs a breadth-first search of the reachable region. It records:
     - the distances to the nearest pearl, a soon-to-spawn tile, a fountain, an unseen tile and a portal to scout;
     - the free room behind the step, and whether the step can reach the tail.
   - A step's score adds target rewards that fall off with distance to free room and threat terms.
   - Portal steps are scored through the exit tile.
5. **Act** (`act`, `take_turn`), in order of priority:
   - escapes when cornered and sprint escapes;
   - queen routines;
   - trades and hunts;
   - splits, harvest loops and strides (free sprint steps toward the target);
   - otherwise a single best step.
6. **Roles** emerge from shared state and do not need a central planner:
   - The **leader** is the longest dragon. It keeps growing, and late in the game other dragons feed it.
   - **Feeders** die next to the leader so that their bodies turn into pearls for it.
   - **Traders** swap a short dragon for a longer enemy in a head-on collision.
   - **Hunters** go after the enemy queen.
   - The **queen** follows its own safety rules.

Every new behaviour is a `constexpr` switch at the top of `main.cpp`, off by default. A build with every switch off
plays the same games as the build before it. The live bot is the source plus a short profile
([`work/server_profile.txt`](work/server_profile.txt)), and [`work/server_bot.py`](work/server_bot.py) produces the
uploaded file from them. This made it possible to ship many versions in the last days without a crash or a doubt about
what was live.

`mybot/` is the earlier, simpler bot (3,053 lines). `v60/` and `v61/` are submissions kept as fixed opponents.

### 2. Local testing

A change was only worth shipping if it won more games than the build before it on the same maps and the same seeds.
The ladder was too noisy for that, so the measuring was done locally.

- **Paired A/B runner** ([`work/ab3.py`](work/ab3.py), [`work/ab2.py`](work/ab2.py))
  - Builds one variant per `TAG@source:SWITCH=value,...` spec and plays every variant against a fixed opponent on
    every map, from both sides, with fixed seeds.
  - Records every game (map, seed, side, result, lengths), so that two runs can be compared game by game
    ([`work/paired.py`](work/paired.py)).
  - The Mac build is deterministic, so a game that changes outcome changed because of the switch.
  - [`work/distq.py`](work/distq.py) spreads games over a second machine. It is not fully deterministic across CPU
    architectures, so it was kept out of mechanism checks.
- **Map sets** ([`tune_runs/`](tune_runs))
  - The official maps (`official127`), and the new ladder maps rebuilt from replays (`newmaps`, by
    [`work/mkfrom2.py`](work/mkfrom2.py)).
  - The Sprint maps (`sprintmaps`).
  - Generated maps of several styles (blobs, islands, mazes, open, portals, rooms, stripes) and sizes, made by
    [`work/mkgen.py`](work/mkgen.py).
  - The generated maps are split into a development set (`genmaps`) and held-out sets (`genheld`, `genfresh`). The
    held-out sets were used only to confirm a result, because the qualifiers were played on unseen maps.
- **Sparring partners**
  - Old versions (`v60/`, `v61/`, `baseline/`).
  - A swarm bot that trades heads one for one (`swarm/`); it reproduced a ladder loss we never saw against our own
    versions.
  - A queen hunter that rams queens. Against a passive opponent, queen-safety changes looked useless.
- **Replay analysis** ([`replay.py`](replay.py) and the scripts in [`work/`](work))
  - Decodes the engine's packed replays and rebuilds the full game state: bodies, pearls, splits, deaths and causes.
  - The scripts measure what wins hide:
    - pearls eaten by round 50 and 100 (more sensitive than wins and deterministic);
    - queen fates ([`work/qram.py`](work/qram.py));
    - where pearls are eaten ([`work/tileeat.py`](work/tileeat.py), [`work/eatcmp.py`](work/eatcmp.py));
    - which spawns can be reached without portals ([`work/reach.py`](work/reach.py));
    - the ladder loss classifier ([`work/lossan.py`](work/lossan.py)).
- **Ladder crawling** ([`work/ladfetch.py`](work/ladfetch.py), [`work/crawl.py`](work/crawl.py))
  - Collects our series and the games among top teams from the public site, so that the analysis could compare us
    with them on the same maps.
- **Compute check**
  - Before an upload, the bot ran in the engine's sandbox on the largest maps, and the worst turn had to stay well
    under the limit.

The rule I learned the hard way: **judge a change by a mechanism metric and paired games, never by a five-game score.**
Two identical builds once scored 1 to 4 on the same map.

### 3. Strategy

The experiment log is [`work/plan.md`](work/plan.md). The main turns, in order:

- **Early ladder (rank ~140 to ~40)**
  - Scoring fixes for the economy. A steeper target falloff raised early eating by 37%.
  - Fountain farming: top teams looped over the tiles that refill every round or so.
  - Portal-safe pathing.
- **Map knowledge instead of map tables**
  - A rule for the whole project was no per-map hard-coding.
  - So the bot learns the map: symmetry inference, mirrored spawn timers, and a check for home regions closed off by
    portals.
  - Centre pulls and harvesting are gated by the observed shape of the map, not by its name.
- **The queen era**
  - After the rule change, a game left undecided by elimination was a queen contest.
  - Ladder replays showed that our queen died in most games. It was usually rammed at length 2 to 4 by a small enemy
    it could see.
  - Local guards made no difference against our own bots. Only the queen-hunting sparring bot exposed them.
  - The queen's safety rules and the late feeding of the queen came from this work. jun then carried queen survival
    much further.
- **Studying the top teams**
  - 636 games among the top 14 teams, plus our own series against them. The findings:
    - Top teams eat 1.3 to 1.7 times more spawn pearls between rounds 100 and 300, and they eat them younger.
    - They keep splitting all game, treat small dragons as disposable, and start far more head-on trades.
    - Their income on maps such as Queen of Spades and Trauma is behind portals that they cross on the first possible
      round.
- **Things that did not work**, each tested and recorded so that nobody repeated them:
  - feeding the queen earlier;
  - a "fortress" rule that keeps the queen at home (it overfitted three maps and failed on held-out maps);
  - behaviour cloning.
    - I fitted a softmax model of top teams' single steps from 141,000 decisions in their replays.
    - Adding it to our scoring made our steps look like theirs: straight moves went from 0.39 to 0.56-0.81.
    - But it lowered eating and lost games. Their edge was where their dragons went, not the next step.

## Results

- **Ladder**: we reached rank **10** in early October (v55 to v61, rating about 1914 to 1934) and ended at rank
  **38** when submissions closed.
- **Qualifiers** (best of 7, unseen maps)
  - Round of 256: won 7-0 against Extreme Maestro.
  - Round of 128: won 6-1 against Knight Capital.
  - Round of 64: lost 2-5 to PhoBoDacBiet.

## What went wrong

1. **Local sparring flattered us.** Our own old versions play the same slow economy as we do. On the ladder we lost
   the first 100 rounds on unit count, and no local opponent showed it until we built sparring bots that copied what
   strong teams did.
2. **The queen problem stayed open.** In our last eight ranked series before the deadline, our queen died in 23 of 24
   lost games, 15 of them before round 150. Every local fix was neutral, because survival depended on map structure
   and enemy numbers more than on local rules.
3. **Portal-locked income.** On maps whose pearls are mostly behind portals, our first crossing came late or never.
   Only the queen sees the portal early, and the queen is not allowed to use portals. The fix (share portal positions
   by sonar so that small dragons go) was identified but not built in time.
4. **Tuning on familiar maps.** Several ideas looked good on the official maps and failed on held-out maps. The
   held-out sets came later than they should have.

## How to run

```
cd work
python3 -m venv bc127 && bc127/bin/pip install unswbc==1.2.7
export PATH=$PWD/bc127/bin:$PATH NOSANDBOX=1 WORKERS=4 KEEP=1
SEED0=3000 python3 ab3.py "$(cat newset.txt),$(cat official.txt)" v61 2 out.json "BASE@mybot2:" "TEST@mybot2:SWITCH_A=value"
python3 paired.py out.json BASE out.json
```

- `ab3.py` builds each variant into `tune_runs/ab2/TAG`, then plays it from both sides with seeds starting at `SEED0`.
- `KEEP=1` keeps the replays for analysis.
- In zsh, write `${SRC}:` rather than `$SRC:` inside a spec; zsh reads `:X` after a variable as a modifier.

To build the uploaded bot from the source and the profile:

```
python3 work/server_bot.py out_dir --src mybot2 --profile work/server_profile.txt
```

Conventions:

- No comments in the bot code and no per-map hard-coding.
- Every new behaviour is a default-off switch, and the all-off build must play the same games as before.
- Commit messages are in English.

## Repository map

| Path | What it holds |
|---|---|
| `mybot2/` | The base bot and every team switch (the final profile is on branch `one15-profile`) |
| `mybot/` | The earlier bot |
| `v60/`, `v61/`, `baseline/` | Fixed opponents for local tests |
| `swarm/` | Sparring bot that trades heads one for one |
| `work/` | A/B runner, replay analysis, ladder crawlers, the experiment log `plan.md`, and the team's card loop (`work/loop/`) |
| `tune_runs/` | Official, rebuilt, Sprint and generated map sets |
| `maps/`, `tune_maps/` | Original map files |
| `docs/` | Team workflow and the card loop specification |
| `candidates/` | Release candidates produced by the card loop |
| `replay.py` | Replay decoder |

## Authorship

- I wrote the base bot, the local testing setup and most of the strategy analysis. Much of the code and analysis was
  written by AI coding agents (Claude Code sessions) working to my direction and checked against games and replays.
  The design, the decisions and the mistakes are mine.
- jun built the team's collaboration tooling, the card loop that turned ideas into tested switches, the online test
  harness, and most of the switches in the final profile, including the queen survival work. Their portfolio is at
  [juntegral/unsw-battlecode-portfolio](https://github.com/juntegral/unsw-battlecode-portfolio).
- Zhe supplied many of the strategic reads and idea cards. Their portfolio is at
  [zhex0121/unsw-battlecode-portfolio](https://github.com/zhex0121/unsw-battlecode-portfolio).
- The engine, the starter code (`helper.hpp`) and the official maps belong to the organisers.
