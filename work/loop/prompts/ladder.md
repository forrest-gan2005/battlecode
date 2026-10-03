Track 3: new completed battle IDs are listed in the card body. Use only these read-only tools:
node "$swarm/tools/online.js" battles --json
node "$swarm/tools/online.js" download <comma-separated-new-battle-ids>
These reads/downloads cost no tickets. Download has its own data/online output policy; do not request or activate anything. Inspect the new replays and existing board ideas (gh issue list/view are read-only). Avoid duplicate ideas.
Write at most two proposals to $out/ladder.json as a JSON array. Each object must have title, summary (the three plain summary lines), Area, Claim, Evidence, Expected signal, and What would show it's wrong. Name exact new replay evidence. Area uses queen, terrain, late-game, economy, infra or other. Propose general behaviour on unseen maps. The runner creates the cards with by:ai, status:ready and wf:3; do not write GitHub yourself. An empty array is valid when nothing useful is supported.
