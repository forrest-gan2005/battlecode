# Team workflow

How the three of us, the issue board and the Claude loops fit together.

The agreed states, testing, approvals, and freeze rules are in [LOOP.md](LOOP.md).

## Pieces
- **Board (GitHub Issues)**: the one place for ideas, evidence and results. If it should be remembered, it goes here.
- **Loops**: each loop runs on one person's own machine and account. A loop reads the board, does its step and writes back to the board.
  - **Test loop** (QWQ): turns ideas into default-off toggles and runs the shared paired tests.
  - **Check loop** (Infra): measures on replays (local and ladder) whether the idea's mechanism actually fired and worked, especially against strong teams.
- **People**: anyone can add ideas and evidence without running a loop.
- **Discord**: chat and quick decisions.

## Idea lifecycle
1. **Open** an issue with the *Idea* template: claim, evidence, area, the signal we expect to see if it works, and what would show it's wrong.
2. **Ready**: when we agree it's worth a run, replace `status:untested` with `status:ready`. Pick Zhe's cards first, other board cards next, then AI cards.
3. **Build and look**: clarify the idea, implement a default-off toggle, and check build and toggle-off replay identity. Zhe answers edge-case questions and watches 2–3 mechanism replays before testing.
4. **Test and check**: run paired A/B against the current main release and explain the behaviour with numbers and replay links, following the states in LOOP.md.
5. **Decide**: `status:tested` means results are ready for the author. An accepted candidate goes through a PR and meowbot approvals; final states are `status:kept`, `status:rejected`, or `status:inconclusive`.

## Labels
- `area:*`: which part of the bot.
- `by:*`: whose idea it is.
- Exactly one `status:*` label gives the card's state; see LOOP.md for transitions and the migration from `loop:ready`, `loop:running`, and `status:in-progress`.

## Result comments
Every result starts with three plain summary lines, then tags so other loops can parse it:
```
What we tried: <change>.
Did it work: <yes / no / unclear, and why>.
Who decides now: <person and action>.
[test] TAG = toggles, base vN, sets x games, seed
       paired vs base: +wins -losses (per-set breakdown), CPU max
[check] signal: what was measured, on which games
        facts: numbers + replay ids
```
Always include the LOOP.md “why” table: our longest vs their longest at the end, total length, and results by map family.

## Code
- Personal branch per person, PRs into `main`, small and rebased often.
- New behaviour = default-off `constexpr` toggle with an area prefix. In `score_step` / `pick_direction` keep changes to a one-line hook.
- Uploads: human ideas need the author's OK plus one other member; AI ideas need one member's OK. Approval merges the candidate PR and submits that exact merge commit. Only an approve button or a human uploads; tag every submission and follow the LOOP.md freeze.
