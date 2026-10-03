Decide whether the intended behaviour and edge cases are clear. Zhe idea cards always need questions; task cards need questions only if unclear.
Write $out/clarify.json as {"needs_info": true|false}.
Write $out/questions.md beginning "Questions before we build", with 2–4 concrete edge-case questions and the author's name (meowbot handles the ping). Write questions even if needs_info is false so missing-question recovery can use them.
Do not implement anything. If earlier replies already answer an issue, ask only about unresolved details.
