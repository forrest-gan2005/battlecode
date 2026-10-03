中文版: [LOOP.zh.md](LOOP.zh.md)

The loop takes ideas from the board, builds them, tests them, and brings decisions back to us.
Zhe's ideas go first, other people's cards next, and AI ideas last.
One GitHub state label tells everyone what happens next, even after a restart.
People answer questions, check the intended behaviour, and approve releases.
The loop never uploads by itself or requests ranked games.
Proposed by 준싱 on 2026-10-04 — shout in Discord if anything looks off.

## How the loop runs

A card is a GitHub issue made with the Idea template: the claim, evidence, area, expected change, and what would show it is wrong. A toggle is an on/off switch for a change; new toggles start off.

`main` is the shared release branch. The base is its current released bot; a candidate is a proposed replacement. A commit ID identifies one exact saved code version. A/B compares the candidate with the base; smoke is an optional short online behaviour check.

There are no timed waves. A runner script polls GitHub every few minutes without using AI tokens. It calls an AI only when a card's state needs AI work. There is no call cap.

| Work | AI tier |
|---|---|
| Clarifying questions, implementation plan and code, verdict draft, hypotheses from ladder games | Opus 5.5 high |
| Plain formatting, wiring, and summaries | Light model |

The ladder is the online competition and its game history. After each new batch of our ladder games, the loop writes new idea cards from what it saw and labels them `by:ai`.

| Pick order | Cards |
|---|---|
| 1 | `by:zhe`: ideas Zhe is confident are real improvements; always clarify and look together |
| 2 | Other board cards |
| 3 | `by:ai`: hypotheses from our latest ladder games |

Within a group, pick the oldest ready card first. Waiting for a person does not block work on other cards.

## One state per card

Exactly one `status:*` label is the source of truth for each card's stage. Replace it on every transition; never stack state labels. Author labels (`by:*`) and area labels (`area:*`) describe the card, not its state.

The runner resumes the next step from the label alone, without a private queue or a remembered timer. Keep questions, answers, base and candidate commit IDs, batch progress, replay links, and approvals on the card or linked PR so resumed work can reuse them. A PR (pull request) is the proposed code change for review and merging.

| State | Who acts | Exit condition / next state |
|---|---|---|
| `status:untested` | People | New idea awaiting agreement to run; then `status:ready`. |
| `status:ready` | Runner | Pick by priority; Zhe's cards go to `status:needs-info`, others there if unclear, otherwise `status:building`. |
| `status:needs-info` | AI, then author | AI posts “what if…” edge-case questions and @mentions the author through meowbot. Author answers on the card or in Discord; record Discord answers on the card, then build. No timeout. |
| `status:building` | AI | Implement a default-off toggle; build passes and toggle-off play is replay-identical to the current base on the old 10 maps. Then `status:needs-look`; failure returns to `status:ready` with a note explaining what needs fixing. |
| `status:needs-look` | AI, then author | Small run checks whether the intended behaviour happens; keep a few replays picked by `tools/smoke_pick.py`. Zhe watches 2–3 and says “that's what I meant”; otherwise revise in `status:building`. This check auto-passes for other authors. Then `status:testing`. |
| `status:testing` | Runner and AI | Run local outcome A/B, one batch at a time; post results and move to `status:tested`. |
| `status:tested` | Author | Results are ready, not accepted. Author chooses a candidate (optionally requesting smoke), rejection, or inconclusive. AI may promote its own idea. |
| `status:candidate` | AI prepares; people approve | Open a candidate PR; meowbot posts approve buttons. After required OKs and release checks, merge to main and submit that exact merge commit; then `status:smoke` if requested, otherwise `status:kept`. |
| `status:smoke` | Human or approve action starts; owner decides | Optional online behaviour check. Area owner plus one other OK chooses keep or rollback; finish as kept, rejected, or inconclusive, recording any rollback. |
| `status:kept` | Nobody pending | Accepted release; final. |
| `status:rejected` | Nobody pending | Dropped, with reason; final. |
| `status:inconclusive` | Nobody pending | Evidence did not settle it; final, with what is missing. |

Replay-identical means the same game actions and events, not merely the same winner. The old 10 maps are our existing regression set: they check that earlier behaviour still works.

## Mapping the old labels

Reuse existing names where they fit. The table is based on the checked-in workflow, template, and `work/board.py`; it is not an inventory fetched from GitHub.

| Existing label | Meaning in this loop |
|---|---|
| `status:untested` | Keep for new cards not yet accepted into the queue. |
| `loop:ready` | Replace with `status:ready`; remove the old label. |
| `status:in-progress`, `loop:running` | Replace with the actual active state after checking progress; remove the old labels. |
| `status:tested` | Reuse for “results ready; author decides,” never as shorthand for keep. Review old cards before migrating them. |
| `status:rejected`, `status:inconclusive` | Reuse as final states; `inconclusive` is already supported by `board.py`. |
| `area:*`, `by:*`, `wf:*` | Descriptive labels only; `wf:*` identifies the old workflow group, not the current state. |

New state labels needed: `status:ready`, `status:needs-info`, `status:building`, `status:needs-look`, `status:testing`, `status:candidate`, `status:smoke`, `status:kept`. Ensure `status:inconclusive` exists too. Keep the existing author labels `by:zhe`, `by:junsing`, `by:qwq`, and `by:ai`.

## What the local tests answer

A/B compares the candidate with its new toggle on against the current main release. Paired games use matching maps and random seeds (numbers that reproduce the same random setup) and swap starting sides so a lucky start does not decide the result.

Test on held-out maps (maps not used to design or tune the change), transposed copies (rows and columns exchanged), and the old 10 maps. Run one batch at a time. First check the intended behaviour in the small mechanism run; then check game outcomes in A/B.

Tests always use the current main release as their base and record its exact commit. When a new release ships, mark results still running “old base” in their comments; that is a result annotation, not a second state label. Queued tests switch to the new base. Old-base evidence must be refreshed against current main before shipping.

Before shipping a candidate containing two or more new toggles, run one short combined check: all new toggles off must preserve identity on the old maps, then run a short A/B with the proposed combination on. Separate wins do not prove the combination works.

## Every result explains why

Every result comment starts with these three plain lines, including small-run and smoke results. Put machine tags such as `[test]` or `[check]` after them.

```text
What we tried: <the change in ordinary words>.
Did it work: <yes / no / unclear, and the main reason>.
Who decides now: <person and the action needed>.
```

Always include a “why” table alongside wins, using base and candidate values where available. If something was not measured, say so. A map family is a group of maps with similar layouts; show each family separately.

| Why | Base | Candidate | What it tells us |
|---|---|---|---|
| Our longest vs their longest at game end | Both lengths and gap | Both lengths and gap | Did we improve the length that decides the game relative to the opponent? |
| Total length | Both teams | Both teams | Where did the rest of the growth go? |
| Results by map family | Games, wins, lengths per family | Games, wins, lengths per family | Is the gain broad, or hiding a loss on one kind of map? |

Games are decided by the longest dragon. On 10-03, one change made our longest longer but the opponent's longer still; “we grew more” alone was misleading.

Below the summary and table, include toggles, base/candidate commits, maps, seeds, batch size, results by starting side, uncertainty, and replay links showing the claimed behaviour. The AI drafts a verdict; the named decision-maker decides.

## Approval and shipping

| Idea source | Required OKs on the meowbot card |
|---|---|
| Human idea | The author plus one other team member |
| AI idea | One OK from any team member; AI promotion counts as the author's OK |

Approvals belong to the exact PR revision: changing its head commit resets them. Approval merges the candidate PR into `main` and submits that exact merge commit. Record the merge commit, submission ID, and previous active submission for rollback; tag every submission.

The loop prepares candidates but never uploads on its own. Only the approve button or a human initiates an upload, including a smoke upload. Freeze rules apply to both routes.

## Coin-flip results and the optional smoke check

“Inside noise” means the local A/B difference is too small to distinguish reliably from chance. The author can request smoke: a short online check of behaviour. Carry that request through the candidate approval step, or have a human explicitly initiate the upload.

Upload the candidate, then play about 60 unranked games against DEV team `dev_test_1` (ID **545**). DEV games have their own **60 games/hour** allowance. Compare with a **v61 baseline recorded once**. Judge behaviour in selected replays, not the win count. The area owner plus one other member's OK decides keep or rollback.

The tools below live in the sibling `unsw-swarm` repo; run these commands from there. `BOT_DIR` means the directory containing the chosen bot's `bot.toml`; `CANDIDATE` is its saved smoke name. Commands with `--confirm` perform real actions and require the human/approve route above.

| Action | Command |
|---|---|
| Record baseline once, while v61 is active | `python3 tools/smoke.py baseline --name v61 --opp 545 --games 60 --confirm` |
| Preview candidate upload and games | `python3 tools/smoke.py plan BOT_DIR --name CANDIDATE --opp 545 --games 60 --baseline v61` |
| Upload and run the authorised smoke | `python3 tools/smoke.py start BOT_DIR --name CANDIDATE --opp 545 --games 60 --baseline v61 --confirm` |
| Collect results and replay picks | `python3 tools/smoke.py report CANDIDATE` |
| Roll back in one command | `python3 tools/smoke.py rollback CANDIDATE --confirm` |

Rollback reactivates the saved previous submission. Baseline recording also spends DEV allowance, so do not assume baseline and candidate both fit in one hour. The current smoke tool withholds comparison if the saved baseline and candidate are incompatible, including when the rollback submission differs from v61. Report that limitation; do not present a missing comparison as evidence. The fixed v61 smoke reference does not replace current-main local A/B.

## Freeze and hard rules

| Time (KST) | Rule |
|---|---|
| From **2026-10-08 20:00** | No new submissions, including smoke uploads; only rollback to a previous submission. |
| **2026-10-09 15:00** | Qualifier submissions close. |

No per-map hardcoding or tuning to a fixed map set: the qualifier uses unseen maps. No orientation dependence: behaviour must not rely on which way a map faces.

Refactors (code rearrangement without intended behaviour changes) must keep the old 10 maps replay-identical. Real fixes may change play with the toggle on, but must not lose much on those maps; show the size of any loss for the author to judge. The toggle-off identity check still applies.

The loop never requests ranked battles. Discord pings happen only when a human must act: questions, look, approve, or results awaiting a decision. Routine progress stays on the board. meowbot's `/loop` and `/board` show card states.

## What still needs wiring

This is the loop spec, not a claim that every tool already follows it. `work/board.py` still queues via `loop:ready`, claims via `loop:running`, prepends tags before summaries, and records the local HEAD as the base. It needs the state transitions, priority, summary order, and actual release base described here. The Issue template's `status:untested` remains valid.

meowbot already documents author-aware OKs and real merges, but `UPLOAD_ENABLED = False` means uploads are currently mocked. Its state displays and human-action-only pings must follow this spec when wired. `tools/smoke_pick.py` currently expects downloaded online replay inputs; the local mechanism run needs compatible inputs or an adapter. Do not auto-pass Zhe's look step because that wiring is missing.

## Running the loop

Use Python 3.10+, authenticated `gh` and `claude`, a C++20 compiler, and the 1.2.7 `unswbc` engine on PATH.
Start from this checkout: `python3 work/loop/runner.py`; it polls every 180 seconds.
`--once` runs one poll; detached jobs continue after it exits. `--dry-run` only reads GitHub and prints plans.
Offline check: `python3 -m unittest discover -s work/loop/tests -v` (fake GitHub, no AI or games).
Cards use `~/meow-cards/card-N` on `card/N`, initially from `origin/main`; release source is `mybot2/` at the recorded base.
Outputs, per-attempt job records, logs and replays live in `~/meow-loop-out/card-N/`; `look.json` lists the selected replays.
`~/meow-loop-out/status.json` is local status; the Loop status issue receives the `card-loop` heartbeat.
Machine locks live in `~/.meow-card-loop-locks/`: one runner, one AI step, one game batch (including identity checks).
Stopping the poller leaves detached jobs running; restarting reuses their leases and completion records.
A killed supervisor's child retains its lease; once all children exit, an unfinished job can resume on the next poll.
Step errors stay visible in status/logs; fix the cause and remove only that job's `done.json` to retry. Build failures return to ready.
Board comments record the base, implementation commit, job paths and replay evidence; human-waiting cards never time out.
For Zhe cards created by a bot, set `LOOP_ZHE_LOGIN` to Zhe's GitHub login; copied Discord replies use `Answer from Zhe: ...`.
Optional engine setup: `--game-env PATH=/path/to/bc127/bin:$PATH`; `--game-env NOSANDBOX=1` explicitly selects native games.
Held and fresh maps use two games per variant; their `_T` copies are generated locally, and the old 10 use eight.
Incomplete batches are retained as incomplete files and never produce a verdict; result tables distinguish unmeasured lengths.
Only `card/N` is git-pushed. Candidate branches/manifests use the GitHub Git data API, then `gh pr create` opens review.
Candidate preparation stops at 2026-10-08 20:00 KST and requires current-base evidence. Approval, merging and uploads remain human actions.
Track 3 checks for new completed ladder battles every four hours; the runner posts at most two AI ideas per review.
The hook checks shell commands and file tools; it is a policy guard, not an operating-system sandbox.
