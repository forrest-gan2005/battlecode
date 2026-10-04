The requester selected existing implementation $metadata. Skip all code implementation and commits.
Read the card, source and history. The implementation worktree $tree is read-only.
Only write test planning/evidence under $out. Do not invoke Bash; the runner verifies and compiles.
For an idea: identify its single default-off boolean toggle, and write $out/build.json with
{"toggle":"NAME","mechanism_maps":[...],"mechanism_games_per_map":4,"check":"work/meow_check.py"}.
Select 2–4 representative maps (16–32 total games counting both variants).
Write the mechanism checker to $sandbox/work/meow_check.py, using the interface documented in
$repo/work/loop/prompts/build.md. It must measure the card's actual claimed mechanism in replays.
Do not replace missing evidence with a pass. If the selected code lacks a usable toggle,
report that clearly and leave build.json absent; the requester can choose another implementation.
For a task: write $out/task.json with needs_info and the existing task's check argv; the checker
must produce $out/task-check.json. The runner checks identity and the task check independently.
Do not edit the selected branch, team rules, memory, or hook/settings files.
