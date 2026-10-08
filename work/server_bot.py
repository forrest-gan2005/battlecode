"""Build the live bot: python3 work/server_bot.py OUT [--src mybot2]
[--profile work/server_profile.txt] [--on NAME:value ...] [--no-compile].
"""

import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("--src", type=Path, default=Path("mybot2"))
    parser.add_argument("--profile", type=Path, default=Path("work/server_profile.txt"))
    parser.add_argument("--on", nargs="+", action="append", default=[])
    parser.add_argument("--no-compile", action="store_true")
    args = parser.parse_args()
    try:
        settings = {}
        for number, line in enumerate(args.profile.read_text().splitlines(), 1):
            line = line.partition("#")[0].strip()
            if line:
                entry = line.split(maxsplit=1)
                if len(entry) != 2:
                    raise ValueError(f"{args.profile}:{number}: expected NAME value")
                settings[entry[0]] = entry[1]
        for group in args.on:
            for entry in group:
                name, separator, value = entry.partition(":")
                if not separator:
                    raise ValueError(f"invalid --on {entry!r}: expected NAME:value")
                settings[name] = value
        source = (args.src / "main.cpp").read_text()
        failures = []
        for name, value in settings.items():
            if not re.fullmatch(r"[A-Za-z_]\w*", name) or not value.strip() or any(
                char in value for char in ";\r\n"
            ):
                raise ValueError(f"invalid constant setting: {name} {value!r}")
            pattern = re.compile(r"(\bconstexpr\s+[^;=\n]+?\s+" + re.escape(name) + r"\s*=\s*)[^;]*;")
            count = len(pattern.findall(source))
            if count != 1:
                failures.append(f"{name} (matches: {count})")
            else:
                source = pattern.sub(lambda match: match[1] + value + ";", source)
        if failures:
            raise ValueError("constants must match exactly once: " + ", ".join(failures))
        if args.out.resolve() == args.src.resolve():
            raise ValueError("out dir must differ from source dir")
        args.out.mkdir(parents=True, exist_ok=True)
        for name in ("main.cpp", "helper.hpp", "sonar_codec.hpp", "bot.toml"):
            shutil.copy2(args.src / name, args.out / name)
        (args.out / "main.cpp").write_text(source)
        if not args.no_compile:
            with tempfile.TemporaryDirectory(prefix=".compile-", dir=args.out) as temporary:
                subprocess.run(
                    ["c++", "-std=c++20", "-O2", str(args.out / "main.cpp"), "-o", str(Path(temporary) / "bot")],
                    check=True,
                )
        print("Constants set:")
        for name, value in sorted(settings.items()):
            print(f"{name} {value}")
        print(f"Out dir: {args.out.resolve()}")
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"server_bot.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
