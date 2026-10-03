#!/usr/bin/env python3
"""PreToolUse policy for card-loop Claude sessions (defence in depth, not an OS sandbox)."""
import json
import os
from pathlib import Path
import re
import shlex
import sys

HERE = Path(__file__).resolve().parent
READ_TOOLS = {'Read', 'Glob', 'Grep', 'LS'}
WRITE_TOOLS = {'Edit', 'Write', 'MultiEdit', 'NotebookEdit', 'apply_patch'}


def check(event):
    tool = event.get('tool_name', '')
    data = event.get('tool_input') or {}
    text = json.dumps(data, ensure_ascii=False)
    flat = text.replace('\\/', '/').replace('\\\\', '/')
    if re.search(r'docs[/\\]+(?:api|discord)\.txt', flat, re.I):
        return 'Credential documents are not available to loop AI.'
    if '--confirm' in text:
        return 'Human confirmation actions are not available to loop AI.'
    if re.search(r'submit\.js', text, re.I):
        return 'Submission tools are not available to loop AI.'
    if re.search(r'online\.js[^\n]*\b(?:request|activate)\b', text, re.I):
        return 'Battle requests and activation are not available to loop AI.'
    if tool in WRITE_TOOLS or tool.endswith('__apply_patch'):
        paths = [data.get(k) for k in ('file_path', 'path', 'notebook_path') if data.get(k)]
        paths += re.findall(r'\*\*\* (?:Add|Update|Delete) File: (.+)', str(data.get('patch', data.get('input', ''))))
        if not paths:
            return 'Unrecognised write target; use Write or Edit with a file_path.'
        root = Path(event.get('cwd') or os.environ.get('LOOP_TREE', os.getcwd()))
        allowed = [Path(os.environ.get(k, '/nonexistent')).resolve() for k in ('LOOP_TREE', 'LOOP_OUT')]
        for name in paths:
            p = (root / name).resolve()
            if 'work/loop' in p.as_posix() or p.is_relative_to(HERE):
                return 'The loop implementation and hooks are read-only to AI.'
            if p.name in ('api.txt', 'discord.txt') and p.parent.name == 'docs':
                return 'Credential documents are not available to loop AI.'
            public_look = Path(os.environ.get('LOOP_OUT', '/nonexistent')).resolve().parent / 'look.json'
            if not any(p.is_relative_to(a) for a in allowed) and p != public_look:
                return 'Write only inside this card worktree or its output directory.'
        return None
    if tool in READ_TOOLS:
        p = data.get('file_path') or data.get('path')
        if p:
            resolved = Path(event.get('cwd', os.getcwd()), p).resolve().as_posix()
            if re.search(r'/docs/(api|discord)\.txt$', resolved):
                return 'Credential documents are not available to loop AI.'
        return None
    if tool != 'Bash':
        return 'Use only Bash, Read, Glob, Grep, Write or Edit; delegated and external write tools are disabled.'
    command = data.get('command', '')
    # Conservative on shell commands mentioning the controller: even shell reads should use Read.
    if re.search(r'(?:work[/\\]+loop|\$LOOP_GUARD|guard\.py|settings\.json)', command) or str(HERE) in command:
        return 'Use Read for loop files; shell access could alter the controller or its hooks.'
    if re.search(r'\b(?:eval|exec)\s|(?:\$\(|`)|\b(?:bash|zsh|sh)\s+-c\b', command):
        return 'Opaque shell evaluation is not permitted in loop AI steps.'
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|()<>')
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return 'Unparseable shell command.'
    words = [Path(t).name for t in tokens]
    for i, word in enumerate(words):
        tail = words[i + 1:]
        if word == 'git' and re.search(r'\bpush\b', ' '.join(tail)):
            return 'Only the runner pushes card branches.'
        if word == 'git' and any(x in tail for x in ('config', 'remote', 'alias')):
            return 'Changing git command routing is not permitted.'
        if word == 'gh':
            if any(t in tail for t in ('--method', '-X', '-f', '-F', '--field', '--raw-field', '--input')):
                return 'GitHub API mutations belong to the runner.'
            if len(tail) < 2 or (tail[0], tail[1]) not in {
                ('issue', 'list'), ('issue', 'view'), ('pr', 'list'), ('pr', 'view'), ('pr', 'diff'), ('repo', 'view')}:
                return 'Only read-only gh list/view/diff commands are available; use board.py for board writes.'
        if word == 'online.js' and (not tail or tail[0] not in ('battles', 'battle', 'download')):
            return 'Only ladder history and replay downloads are allowed.'
        if word == 'unswbc' and 'submit' in tail:
            return 'Uploads belong to the human approval route.'
    if re.search(r'\b(?:curl|wget)\b', command) or re.search(r'\b(?:python\S*|node|ruby|perl)\s+(?:-c|-e)\b', command):
        return 'Inline interpreters and raw network commands are not permitted; use reviewed local tools.'
    if re.search(r'\b(?:ident\.py|ab[23]\.py|unswbc\s+run)\b', command):
        if os.environ.get('LOOP_BATCH_LEASE') != '1':
            return 'Game execution requires the runner’s global batch lease.'
    if re.search(r'\b(?:nohup|disown)\b|(?<!&)&(?!&)', command):
        return 'Do not detach AI children; the runner owns job lifetimes.'
    return None


def main():
    try:
        event = json.load(sys.stdin)
        reason = check(event)
    except Exception as exc:
        reason = f'Invalid hook input: {type(exc).__name__}'
    if reason:
        print('Blocked by card-loop guard: ' + reason, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
