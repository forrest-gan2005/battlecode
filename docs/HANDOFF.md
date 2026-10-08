# Handoff: queen and economy experiments (QWQ, up to 2026-10-08)

This covers the local experiments and replay studies from QWQ's Claude session, 3-8 Oct. It covers what was tried, what held up, and where the code and scripts are. The Chinese version is [HANDOFF.zh.md](HANDOFF.zh.md). Board rules and states are in [WORKFLOW.md](WORKFLOW.md) and [LOOP.md](LOOP.md).

## 1. Goal and deadlines
- **Goal:** reach the Grand Final (17 Oct, UNSW, top 10).
  - The way in is the **Qualifiers on 10 Oct**: a seeded Bo7 knockout where the top 10 advance.
  - Seeding comes from the ladder rating.
  - The Sprint did not matter.
- **Win rule since 1 Oct:**
  - Dragons 0 and 1 are the queens. They act first each round.
  - At round 500, the longer queen wins, and a dead queen counts as length 0.
  - Ties go to the longest dragon, then to total length.
  - **So keeping our queen alive decides most games that don't end in an elimination.**
- **Freeze (LOOP.md):**
  - From **2026-10-08 20:00 KST** (22:00 AEDT), no new submissions; only rollback is allowed.
  - Qualifier submissions close **2026-10-09 15:00 KST**.
- **Hard rules:**
  - No per-map hard-coding or tuning to a fixed map set; the Qualifiers use unseen maps.
  - Map-size gates such as `QUEEN_MIN_CELLS` are allowed as heuristics.
  - New behaviour goes behind a default-off `constexpr` toggle.
  - Work happens on personal branches and reaches `main` through PRs.
  - Commit messages are in English.
  - QWQ's rule: no code comments in bot code.

## 2. Where things are (checked 2026-10-08 17:20 AEDT)
- `main` is `a358ec8`. Queen switches on by default: `QUEEN_WAIT` + `QW_ANY_BLOCK` (#25, PR #37), `QUEEN_SAFETY` (#39), `QUEEN_DEAD_END` (#36), `QUEEN_NO_FEED` (#48), `QH_SCOUT` (#31), `TR_STALL_RELEASE` (#51), `SN_TAIL_MOUTH` (#42).
- **Cards from this session:**
  - #25 queen-unbox: `status:kept`, merged as PR #37.
  - #33 blind-circling: closed. The hypothesis was wrong (see 3.2).
  - #38 queen-loop: closed, `status:rejected`.
    - On 7 Oct, QWQ noted that the queens of the rank-1 team at that time (nAah) don't circle at all, yet survive.
    - The third build (`QUEEN_CAREFUL`) still let the queen die early.
- Open cards waiting for a decision (`status:tested`): #55, #54, #49.
- **Local only, nothing pushed:**
  - `/Users/UNSW/battlecode` (branch `qwq/queen-wait`, based on the old main `7aa8a45`) has uncommitted experiment toggles, all off: `SCORE_LOG*`, `REVISIT_*`, `QW_HALF`, `QUEEN_NO_CORRIDOR`/`QNC_*` and `QUEEN_LOOP`/`QL_*`. Backup: `work/wip_main_cpp_2026-10-08.patch`.
  - Worktree `/Users/UNSW/bc-hloop` (branch `qwq/home-loop`, from `a358ec8`) has `QUEEN_LOOP`/`QL_*` ported onto the current main.
    - It is uncommitted. It compiles but was not tested, because QWQ stopped the test.
    - Patch: `work/home_loop_on_main_2026-10-08.patch`.
  - Analysis scripts are in `/Users/UNSW/battlecode/work/`; section 5 lists them.
    - Tracked on main: `ab3.py`, `ident.py`, `zonerun.py`, `replay.py`.
    - Local and untracked: `qab.py`, `qloopstat.py`, `qself.py`, `qstyle3.py`, `matchinfo.py`, `open50*.py`, `gsum.py`, `qlast.py`.

## 3. What we verified

All local numbers come from Mac-only runs unless noted. Sets have 22 maps (the official set plus the new set), seed 3000, both sides. "+a −b" means games this build won that the base lost (a) and games it lost that the base won (b). Opponents:
- `HQ61` hunts queens.
- `v61` does not hunt queens, so it hides ram problems.
- `RAM61` rams heads.

The rows marked DIST mixed Mac and laptop games, so they carry the extra noise described in section 6.

### 3.1 Worked (kept)
| Change | Evidence | State |
|---|---|---|
| `QUEEN_WAIT` + `QW_ANY_BLOCK`: a stuck queen of length ≥ 4 splits 2 off her tail and waits (#25) | Slithery coil-start deaths 4 → 0 vs both opponents. Wins level: HQ61 52 → 52 (+3 −3), v61 49 → 50 (+3 −2), 88 games each. Toggle off = replay-identical to main. | merged (PR #37) |
| Earlier, kept before this session: `QUEEN_SPLIT_ROUND=200`, feed alive queens from r300 (`QUEEN_SAFE_ROUND`, `QUEEN_GAME_FEED_ROUND`), `QUEEN_QUIET_ROUND=100`, `QUEEN_HOME_CLOSED`, `WEIGHT_PEARL=2.0`, `FAR_GAIN=2`, `POCKET_CAP=48` | v55-v61 A/Bs | on main |

### 3.2 Did not work (rejected; toggles stay off)
| Change | Result | Why we dropped it |
|---|---|---|
| Looser pearl contest `CONTEST_SLACK` 2 / 3, `CONTEST_MAX_LENGTH` 6 (#32; 88 games, DIST) | Wins v61 48 → 52 / 49 / 49, RAM61 38 → 39 / 34 / 37. Eats at r50/r100 unchanged (42.2/108.4 → 42.4/108.6). | The mechanism did not move. Local bots don't invade like top teams. |
| Blind circling (#33; 88 games, DIST): `WEIGHT_TERRITORY` 0.75 / 0.3, `FAR_GAIN=8`, `WEIGHT_UNSEEN=0.6` | Circling share r<100 stays at about 18% with territory 0.3. Less circling (unseen 0.6) gives fewer eats and units (wins 55 → 42). | Territory doesn't cause circling. Circles are partly productive (waiting for spawns). |
| `REVISIT_PENALTY` 50-400 on cells the head held in the last 3 rounds (88 games, DIST) | Circling 18.9% → 13.4-15.9%. Eats and units unchanged. | Circling is a symptom, not the cause of the eat gap. |
| `QUEEN_NO_CORRIDOR` (penalise queen moves into one-way corridors; 88 games) | HQ61 52 → 41 (+3 −14), v61 50 → 44 (+11 −16) | No drop in box-ins or dead ends; eliminations went up. |
| `QW_HALF` (stuck queen splits half instead of 2; 88 games, DIST) | HQ61 53 → 48 | Worse than peeling 2. |
| jun's #23 `QUEEN_NO_TRAP` (Mac re-test, 88 games) | HQ61 54 → 49 (+12 −17), v61 53 → 45 (+8 −16) | Loses wins. |
| Queen loop v1 (#38): a queen of length ≤ 3 circles a 2x2 when nothing is near, anywhere on the map | HQ61 22 → 14 (+2 −10), v61 25 → 17 (+6 −14), 44 games each. Rams 24 → 23 / 14 → 15. Alive at end 8 → 8 / 10 → 12. | Hunters catch her off the loop. Not chasing pearls costs economy. |
| Home loop (#38, ql2): loop only within 6 tiles of her start, pulled home when no enemy is within 6 (`QL_HOME_RADIUS=6`, `QL_HOME_PULL=300`) | All maps from r0: HQ61 22 → 16, v61 25 → 15. On small maps (≤ 600 cells), eliminations rose 2 → 9 and 3 → 10. | A queen who doesn't grow or split early means fewer dragons on small maps. |
| Same, gated to big maps and from r40 (`QL_BIG_ONLY`, `QL_START_ROUND=40`) | Wins level: 21 + 27 = 48 vs 47 of 88; small-map games identical. Queen alive at end v61 10 → 15, HQ61 8 → 8. Rams HQ61 24 → 27. | No protection against a hunter. Card rejected by QWQ on 7 Oct. |
| Older (3 Oct, DIST): hard kill-reach veto, escorts (`QUEEN_DEFEND_RADIUS`), `QUEEN_KEEP=5`, early split stop | Queen survival unchanged vs HQ61 (11-14%) and v61 (11-20%) | Local rule tweaks alone did not change where she dies. |

### 3.3 What the replays say
- **The opening gap vs top teams** (dev1 and ftm ladder series) is a search and positioning gap, not a contest-rule problem:
  - Pearls eaten in r0-50: we get 37 vs dev1's 50, and 35 vs ftm's 46. Units at r99: 17.9 vs 31.5 (dev1).
  - Per dragon, steps, approach rate and contest losses are the same as theirs.
  - Our dragons are "blind" (no pearl in their 7x7 view) 53-54% of the time vs their 48-50%. When blind, ours revisit a cell within 5 rounds 12-14% of the time vs 7-8%.
  - Pearls in view per dragon-round: 1.65 vs 2.20.
  - About 30% of their eats in our half are pearls that had lain there 16+ rounds, and we never saw about half of them.
- **How our queen dies:**
  - Recent ladder games (≥ 870k, 123 games): rammed 68, boxed by allies 16, dead end 14, own move into a head 8.
  - Rams are mostly in open cells (58 of 68), by 2-3 long enemies that were 1-2 tiles away when the round started.
  - Of the self-inflicted deaths after r5, 26 of 30 happen in corridors.
  - In 52 of 56 logged local self-deaths, she had not picked a trapped move over a safe one. The trap closes after her move, as other dragons move in. Fixing that needs a room check that accounts for the other dragons' moves (#23 tried and lost wins).
- **Kill reach** of an enemy of length L in one turn: ceil(L/4) + (L − 2). That is 2 long → 1 tile, 3 → 2, 4 → 3, 5 → 5. A sprint's first ceil(L/4) steps are free.
- **test4** (series 1124881-95): her queen loops about 25% of rounds, about 5 tiles from her start. She was alive 12 of 15 games with 0 rams. She visits about 41 cells per 100 rounds vs our 72, and has 0.75 enemy heads within 8 vs our 1.75. Our home-loop A/B (3.2) shows the loop itself is not what protects her.
- **"dev test 1 :P"**, rank 1 on 5 Oct (rated 2495 then, 2382 on 8 Oct). Series 1129793-807 on 5 Oct; we were side A, and they won 13 of 15:

| per queen | us | dev1 |
|---|---|---|
| alive at the end | 2/15 | 9/15 |
| deaths | rammed 8, other 5 | rammed 4, no legal move 2 |
| median death round | r80 | r147 |
| mean length while alive | 5.2 | 9.6 (5-13 mid game) |
| pearls she ate r0-99 / r100-299 / r300+ | 46 / 3 / 41 | 87 / 103 / 239 |
| rounds with a multi-tile sprint | 3.9% | 15.3% |
| U-turn ("loop") share | 36% | 18% |
| enemy heads within 8 | 2.13 | 1.00 |
| any enemy head within 3 | 19.9% of rounds | 6.9% |
| own heads within 6 | 1.12 | 2.92 |
| own body cells within 2 | 0.56 | 2.01 |
| enemy within 4 → next round farther / closer | 27% / 16% | 45% / 17% |
| enemy dragons that died within 4 of her | 13 | 44 |
| own dragons that died within 4 of her (late feeding) | 32 | 264 |

  - **Reading:** their queen does not circle more. She is longer, sits among her own dragons, backs off when a head comes within 4 and sprints. Our dragons die near her. Late in the game, her team suicides next to her to feed her.
  - Schooltime is in these numbers, but both queens were shut in their start pocket all game, which inflates the U-turn share.
  - The script is `work/qstyle3.py 1129793 1129807 us dev1`.

## 4. Switches and parameters worth knowing (main, `mybot2/main.cpp`)
| Switch | Default on main | Meaning |
|---|---|---|
| `QUEEN_MODE`, `QUEEN_MIN_CELLS=600` | on | Queen rules. `is_queen()` needs more than 600 cells or a closed home (`QUEEN_HOME_CLOSED`); `real_queen()` = id 0/1 on any map. |
| `QUEEN_SPLIT_ROUND=200` | 200 | No queen growth splits after r200. |
| `QUEEN_SAFE_ROUND=300`, `QUEEN_GAME_FEED_ROUND=300`, `ENDGAME_ROUND=400` | | `feeding_phase()` means round > `feed_round`. `feed_round` is 400, or 300 once a queen game starts: `is_queen()` and r ≥ 300, or no enemy seen by r100. |
| `QUEEN_QUIET_ROUND=100` | | A queen that has seen no enemy by r100 starts a queen game, and the team feeds her from r300. |
| `QUEEN_WAIT`, `QW_MIN_LENGTH=4`, `QW_ANY_BLOCK` | on | Stuck queen peels 2 and waits. |
| `QUEEN_SAFETY`, `QS_*` | on | Queen stays off tiles an enemy head can hit this turn, with escape splits (#39). `QS_HIT_PENALTY=3e8` and `QS_PAY_PENALTY=2e8`, so in practice these are hard rules. |
| `QUEEN_DEAD_END`, `QUEEN_ROOM=8` | on | Dead-end penalty and room margin (#36). |
| `QUEEN_NO_FEED` | on | The queen never takes a feeding role (#48). |
| `CONTEST_SLACK=1`, `CONTEST_MAX_LENGTH=4` | | Pearl contest rule (looser values tested, 3.2). |
| `WEIGHT_PEARL=2.0`, `WEIGHT_TERRITORY=1.5`, `WEIGHT_UNSEEN=0.20`, `FAR_GAIN=2` | | Main economy weights. |
| `QUEEN_LOOP`, `QL_*` (only in my local copies) | off | `QL_BONUS=2000`, `QL_MAX_LEN=3`, `QL_CLEAR=6`, `QL_COOLDOWN=8`, `QL_PEARL_RANGE=2`, `QL_MIN_EXITS=3`, `QL_HOME_RADIUS`, `QL_HOME_PULL=300`, `QL_START_ROUND`, `QL_BIG_ONLY`. |

**Scale check:**
- Before `QUEEN_SAFETY` (v61), a length-2 queen next to a length-2 enemy cost about 340 points, while an adjacent pearl was worth about 740. That soft penalty is why she stepped into reach.
- Any new soft queen term has to be weighed against `target_bonus` (≈ w·(260 − 40·distance)) and the `QS_*` hard penalties.

## 5. How to test and measure
- **Local A/B,** from `work/`:
  ```bash
  export PATH=$PWD/bc123/bin:$PATH NOSANDBOX=1 WORKERS=4 KEEP=1; unset DIST
  SEED0=3000 python3 ab3.py "$(cat newset.txt),$(cat official.txt)" tune_runs/ab2/HQ61 2 out.json "BASE@mybot2" "TRY@mybot2:QUEEN_LOOP=true,QL_HOME_RADIUS=6"
  ```
  - `TAG@src:K=V,...` builds a copy with those constants overridden. `src` can be an absolute path to another worktree.
  - Use tags that haven't been used before. `KEEP=1` writes `work/ab2/TAG_*.replay`, with no logs. `zonerun.py` keeps logs.
- **Queen fates per tag:** `python3 qab.py ab2 TAG1,TAG2`. It reports alive at the end, rammed, self-inflicted with sub-types, and the median death round.
- **Loop share and rams on the loop:** `python3 qloopstat.py ab2 TAGS`.
- **Ladder replays:**
  - Replay: `curl -sL https://game.battlecode.au/api/matches/<id>/replay -o work/nr/<id>.replay` (gzip, read by `replay.py`). No login needed.
  - Teams, current ratings, map and the other games of the series: `python3 matchinfo.py <id>`.
    - It reads `https://game.battlecode.au/visualiser/__data.json?match=<id>`, a SvelteKit devalue array.
    - It needs a User-Agent header; Python's default gets 403.
  - The game ids in a series are consecutive.
- **Other scripts:**
  - `qstyle3.py first last labA labB`: queen behaviour profile for a ladder series.
  - `qself.py`: queen self-death taxonomy over ladder games.
  - `open50*.py`: opening economy.
  - `gsum.py` / `qlast.py`: series summaries.
  - `ident.py`: replay identity, toggle off vs main.

## 6. Pitfalls
- **Machine effect.** Games run on the laptop worker (x86, `DIST=1`) play differently from the Mac. Mac native (arm64) and `--sandbox` (wasm, like the server) gave identical games. DIST mixes both: identical configs diverged in 17-24 of 88 games, and wins went 48 vs 55. **Run mechanism checks on the Mac only (`unset DIST`).** On the Mac, the same config and seeds are deterministic.
- **Noise.** A win gap under about 8 of 88 is noise. Judge by a direct metric as well: eats at r50/r100, queen alive at the end, rams, eliminations.
- **Sparring bias.**
  - `v61` doesn't hunt queens, so test queen changes against `HQ61` too.
  - Neither bot invades like the top teams: enemy eats in our half are 28-33 vs 49-57 for dev1 and ftm. So local tests under-rate economy-defence ideas.
- **Small maps.** Anything that keeps the queen passive early costs eliminations on maps ≤ 600 cells. Always split results by map size.
- **Stopping ab3.** Killing `ab3.py` leaves orphaned `multiprocessing.spawn` workers that keep launching games. Kill those workers and their `unswbc run` children too.
- **CPU.** Don't run `ident.py` (6 threads) at the same time as an A/B (4 workers). The Mac froze and rebooted once.
- **macOS quirks.**
  - Multiprocessing scripts must be files, not stdin.
  - BSD `seq` prints big numbers as `1.12979e+06`; use `seq -f %.0f`.
- **Replay decoding.**
  - `tileChange` with u32 = 0 (a removal) comes before the eating `dragonUpdate`. Count an eat when a head enters a pearl cell.
  - A dragon's death turns every other body cell into a pearl.
- **Loop metric.** "Loop share" in `qloopstat.py` counts any 4 consecutive head cells that form a 2x2 square, so one U-turn counts. The base already shows about 30%. Compare it only within one table, not with jun's strict 0.3%.
- **Ladder account.**
  - Don't change team settings.
  - Run browser scripts in a separate tab, not the one QWQ browses in.
  - The loop never requests ranked battles.
  - Manual battles use whatever submission is active.

## 7. To do
1. **Before the freeze (20:00 KST, 8 Oct):** QWQ picks the final submission. Nothing from this handoff is waiting to be submitted.
2. Decide the open `status:tested` cards #55, #54, #49.
3. **Queen-protection ideas the dev1 data supports (not built or tested):**
   - a longer queen mid game (5-13 instead of 2-3), so she gets 2+ free sprint steps;
   - keep her among our own dragons rather than alone;
   - always step away when a head comes within 4. `QUEEN_SAFETY` covers part of this; measure how often she backs off now with `qstyle3.py` on new series.
   - Test against `HQ61` and split results by map size.
4. Self-deaths where the trap closes after her move (52 of 56) are still open. They need a room check that predicts other dragons' moves; #23 lost wins.
5. Optional: the home-loop port in `/Users/UNSW/bc-hloop` is untested on the current main. #38 is rejected, so only revive it if there is a new reason.
6. Cleanup when convenient:
   - `zz_mainref/` and `zz_mwh/` (root-level copies for `ident.py`);
   - the old builds under `tune_runs/ab2/`;
   - the worktree `/Users/UNSW/bc-qwait` (PR #37 is merged);
   - the local experiment toggles on `qwq/queen-wait` (backed up as a patch).
