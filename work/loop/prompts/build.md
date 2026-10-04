Implement this card behind ONE new constexpr bool toggle in mybot2/main.cpp, default false. Preserve current main's release defaults. Read human answers and revisions first. If this branch predates base $base, rebase it onto that exact base and resolve conflicts; never drop another change silently.
Build the C++ source with c++ -std=c++20 -O2, writing the binary under $out. Implement a mechanism checker under work/ (reuse feedcheck/splitcheck patterns). Its CLI is:
python3 work/<check>.py --replays DIRECTORY --base base --candidate candidate --output FILE
It must measure the claimed behaviour from paired replays, emit JSON {"passed": bool, "note": "...", ...raw counts...}, and return zero for a completed measurement even when passed=false. Errors or missing replays must be nonzero. Pre-register the mechanism expectation before seeing results. Choose 2–4 suitable maps and 4 games per map per config (two seeds, both sides); total 16–32 games. Avoid tuning on held-out maps.
Write $out/build.json:
{"toggle":"AREA_NAME","mechanism_maps":["map1","map2"],"mechanism_games_per_map":4,"check":"work/card_N_check.py","expectation":"..."}
Run the existing identity check, with the toggle OFF:
REF=base IDENT_MAPS=$old_maps IDENT_SEEDS=2 python3 $sandbox/work/ident.py candidate
Run from $sandbox. It must print 40 OK comparisons and end with identical; a zero exit alone is insufficient. Save its output to $out/ident-ai.log. Do not run any other batch. Commit the default-off implementation and checker on card/$number. Never push. The runner independently repeats identity before pushing.

Automatic revision evidence (if any):
$revision_evidence
If an automatic revision was requested, use the preceding verdict's measurements and failure reason to make the intended behaviour actually trigger. Address the blocking gates and check that the mechanism run shows the intended behaviour; preserve the default-off identity requirement. Do not tune on held-out results or named maps.
