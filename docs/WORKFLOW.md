# Team workflow

How the three of us, the issue board and the Claude loops fit together.

## Pieces
- **Board (GitHub Issues)**: the one place for ideas, evidence and results. If it should be remembered, it goes here.
- **Loops**: each loop runs on one person's own machine and account. A loop reads the board, does its step and writes back to the board.
  - **Test loop** (QWQ): turns ideas into default-off toggles and runs the shared paired tests.
  - **Check loop** (Infra): measures on replays (local and ladder) whether the idea's mechanism actually fired and worked, especially against strong teams.
- **People**: anyone can add ideas and evidence without running a loop.
- **Discord**: chat and quick decisions.

## Idea lifecycle
1. **Open** an issue with the *Idea* template: claim, evidence, area, the signal we expect to see if it works, and what would show it's wrong.
2. **Ready**: when we agree it's worth a run, add `loop:ready`.
3. **Test**: the test loop picks up `loop:ready` issues, implements the toggle, runs the protocol and comments the result.
4. **Check**: the check loop measures the expected signal and comments facts (numbers and replay ids, no verdict).
5. **Decide**: we read both comments and set `status:tested` (keep) or `status:rejected`. Kept toggles are candidates for the next upload.

## Labels
- `area:*`: which part of the bot.
- `status:untested | in-progress | tested | rejected`
- `loop:ready`: go for the loops. `loop:running`: a loop is working on it (remove when done).

## Result comments
Loops start their comment with a tag so other loops can parse it:
```
[test] TAG = toggles, base vN, sets x games, seed
       paired vs base: +wins -losses (per-set breakdown), CPU max
[check] signal: what was measured, on which games
        facts: numbers + replay ids
```

## Code
- Personal branch per person, PRs into `main`, small and rebased often.
- New behaviour = default-off `constexpr` toggle with an area prefix. In `score_step` / `pick_direction` keep changes to a one-line hook.
- Uploads: QWQ picks the toggles, quick ok in Discord first, tag every submission.
