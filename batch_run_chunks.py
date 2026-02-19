#!/usr/bin/env python3
"""
Batch runner for lexical chunks.

For each chunk in lexical-chunks.js:
1) Set TITLE_CARD_TEXT in generate.py from the `// Title` comment.
2) Replace `phrases = [...]` in generate.py with that chunk's phrases.
3) Run ./run.sh and wait for it to finish before moving to the next chunk.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path


BLOCK_RE = re.compile(
    r"^\s*//\s*(?P<title>[^\n]+)\s*$\s*^\s*const\s+\w+\s*=\s*\[(?P<body>.*?)\];",
    re.MULTILINE | re.DOTALL,
)
STRING_RE = re.compile(r'"((?:\\.|[^"\\])*)"')

TITLE_RE = re.compile(r"^TITLE_CARD_TEXT\s*=\s*.*$", re.MULTILINE)
PHRASES_RE = re.compile(r"^phrases\s*=\s*\[.*?^\];\s*$", re.MULTILINE | re.DOTALL)
OUTPUT_DIR_RE = re.compile(r'^OUTPUT_DIR\s*=\s*["\'](?P<dir>[^"\']+)["\']', re.MULTILINE)


def parse_chunks(chunks_path: Path) -> list[tuple[str, list[str]]]:
    source = chunks_path.read_text(encoding="utf-8")
    chunks: list[tuple[str, list[str]]] = []

    for match in BLOCK_RE.finditer(source):
        title = match.group("title").strip()
        body = match.group("body")
        phrases = [json.loads(f'"{raw}"') for raw in STRING_RE.findall(body)]
        if phrases:
            chunks.append((title, phrases))

    return chunks


def format_phrases_block(phrases: list[str]) -> str:
    lines = ["phrases = ["]
    for phrase in phrases:
        lines.append(f"  {json.dumps(phrase, ensure_ascii=False)},")
    lines.append("];")
    return "\n".join(lines)


def update_generate_file(generate_path: Path, title: str, phrases: list[str]) -> None:
    content = generate_path.read_text(encoding="utf-8")

    new_content, title_replacements = TITLE_RE.subn(
        f"TITLE_CARD_TEXT = {json.dumps(title, ensure_ascii=False)}",
        content,
        count=1,
    )
    if title_replacements != 1:
        raise RuntimeError("Could not find TITLE_CARD_TEXT in generate.py")

    phrases_block = format_phrases_block(phrases)
    new_content, phrases_replacements = PHRASES_RE.subn(
        phrases_block, new_content, count=1
    )
    if phrases_replacements != 1:
        raise RuntimeError("Could not find phrases array block in generate.py")

    generate_path.write_text(new_content, encoding="utf-8")


def detect_output_dir(generate_path: Path, override: str | None) -> Path:
    if override:
        return Path(override)

    content = generate_path.read_text(encoding="utf-8")
    match = OUTPUT_DIR_RE.search(content)
    if match:
        return Path(match.group("dir"))

    return Path("output")


def infer_resume_start(output_dir: Path) -> int:
    if not output_dir.exists() or not output_dir.is_dir():
        return 1

    mp4_files = [p for p in output_dir.iterdir() if p.is_file() and p.suffix.lower() == ".mp4"]
    if not mp4_files:
        return 1

    indexed = []
    for file_path in mp4_files:
        prefix, sep, _rest = file_path.name.partition("-")
        if sep and prefix.isdigit():
            indexed.append(int(prefix))

    if indexed:
        return max(indexed) + 1

    return len(mp4_files) + 1


def select_chunks(
    chunks: list[tuple[str, list[str]]],
    start: int,
    end: int | None,
    titles: list[str] | None,
    contains: str | None,
) -> list[tuple[int, str, list[str]]]:
    indexed = [(idx + 1, title, phrases) for idx, (title, phrases) in enumerate(chunks)]

    if start < 1:
        raise ValueError("--start must be >= 1")

    if end is not None and end < start:
        raise ValueError("--end must be >= --start")

    filtered = [row for row in indexed if row[0] >= start and (end is None or row[0] <= end)]

    if titles:
        title_set = {t.strip().lower() for t in titles}
        filtered = [row for row in filtered if row[1].lower() in title_set]

    if contains:
        needle = contains.lower()
        filtered = [row for row in filtered if needle in row[1].lower()]

    return filtered


def run_batch(
    selected: list[tuple[int, str, list[str]]],
    generate_path: Path,
    run_cmd: str,
    workdir: Path,
    dry_run: bool,
    write_only: bool,
    continue_on_error: bool,
) -> int:
    if not selected:
        print("No chunks selected.")
        return 1

    cmd = shlex.split(run_cmd)

    for pos, (idx, title, phrases) in enumerate(selected, start=1):
        print(f"\n[{pos}/{len(selected)}] Chunk #{idx}: {title}")
        print(f"   Phrases: {len(phrases)}")

        if dry_run:
            print("   Dry-run mode: no file changes and no command execution")
            continue

        update_generate_file(generate_path, title, phrases)
        print("   Updated generate.py")

        if write_only:
            print("   Write-only mode: skipped run command")
            continue

        print(f"   Running: {run_cmd}")
        result = subprocess.run(cmd, cwd=workdir)
        if result.returncode == 0:
            print("   Finished successfully")
            continue

        print(f"   Failed with exit code {result.returncode}")
        if not continue_on_error:
            return result.returncode

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Update generate.py from lexical-chunks.js and run ./run.sh per chunk."
    )
    parser.add_argument("--chunks-file", default="lexical-chunks.js")
    parser.add_argument("--generate-file", default="generate.py")
    parser.add_argument("--run-cmd", default="./run.sh")
    parser.add_argument(
        "--start",
        type=int,
        help="1-based start chunk index. If omitted, auto-resume picks next index from output folder.",
    )
    parser.add_argument("--end", type=int, help="1-based end chunk index (inclusive)")
    parser.add_argument(
        "--output-dir",
        help="Output folder used to infer resume start (default: OUTPUT_DIR from generate.py).",
    )
    parser.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Auto-resume from output folder when --start is not provided (default: enabled).",
    )
    parser.add_argument(
        "--title",
        action="append",
        help="Exact title to include. Can be repeated.",
    )
    parser.add_argument(
        "--contains",
        help="Case-insensitive title substring filter.",
    )
    parser.add_argument("--list", action="store_true", help="List selected chunks and exit")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview selected chunks only (no file changes, no command execution)",
    )
    parser.add_argument(
        "--write-only",
        action="store_true",
        help="Update generate.py per chunk but do not execute the run command",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue with next chunk if run command fails.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    chunks_path = Path(args.chunks_file).resolve()
    generate_path = Path(args.generate_file).resolve()
    workdir = generate_path.parent

    if not chunks_path.exists():
        print(f"Chunks file not found: {chunks_path}")
        return 1
    if not generate_path.exists():
        print(f"Generate file not found: {generate_path}")
        return 1

    chunks = parse_chunks(chunks_path)
    if not chunks:
        print("No chunks were parsed from lexical-chunks.js")
        return 1

    output_dir = detect_output_dir(generate_path, args.output_dir)
    if not output_dir.is_absolute():
        output_dir = (generate_path.parent / output_dir).resolve()

    if args.start is not None:
        start = args.start
        print(f"Start index (manual): {start}")
    elif args.resume:
        start = infer_resume_start(output_dir)
        print(f"Start index (auto-resume): {start} (from {output_dir})")
    else:
        start = 1
        print("Start index: 1 (resume disabled)")

    selected = select_chunks(
        chunks=chunks,
        start=start,
        end=args.end,
        titles=args.title,
        contains=args.contains,
    )

    if start > len(chunks):
        print(
            f"Nothing to run. Start index {start} is after the last chunk ({len(chunks)})."
        )
        return 0

    if args.list:
        for idx, title, phrases in selected:
            print(f"{idx:>4}: {title} ({len(phrases)} phrases)")
        print(f"\nTotal selected: {len(selected)}")
        return 0

    return run_batch(
        selected=selected,
        generate_path=generate_path,
        run_cmd=args.run_cmd,
        workdir=workdir,
        dry_run=args.dry_run,
        write_only=args.write_only,
        continue_on_error=args.continue_on_error,
    )


if __name__ == "__main__":
    sys.exit(main())
