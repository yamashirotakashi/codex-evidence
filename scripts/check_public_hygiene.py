from __future__ import annotations

import fnmatch
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_PATTERNS = {
    "private_user": re.compile(
        r"tky" + r"99|C:/Users/tky" + r"99|/home/tky" + r"99",
        re.IGNORECASE,
    ),
    "private_project": re.compile("|".join(("TECH" + "ZIP", "At" + "om", "EV" + "O"))),
    "secret_like": re.compile(
        r"s" + r"k-[A-Za-z0-9_-]+|g" + r"hp_[A-Za-z0-9_]+|A" + r"KIA[A-Za-z0-9]+"
    ),
}

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
SKIP_FILES = {".hygiene-ignore"}


@dataclass(frozen=True)
class IgnoreRule:
    glob: str
    pattern: re.Pattern[str]
    reason: str


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    root = Path(args[0]) if args else Path.cwd()
    root = root.resolve()
    rules = _load_ignore_rules(root / ".hygiene-ignore")
    violations: list[dict[str, object]] = []
    allowed: list[dict[str, object]] = []

    for path in _iter_text_files(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for name, pattern in DEFAULT_PATTERNS.items():
                if not pattern.search(line):
                    continue
                rule = _matching_rule(rules, rel, line)
                record = {
                    "pattern": name,
                    "path": rel,
                    "line": line_number,
                    "excerpt": line.strip()[:200],
                }
                if rule is None:
                    violations.append(record)
                else:
                    record["reason"] = rule.reason
                    allowed.append(record)

    payload = {
        "status": "pass" if not violations else "fail",
        "violation_count": len(violations),
        "allowed_fixture_count": len(allowed),
        "violations": violations,
        "allowed_fixtures": allowed,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not violations else 1


def _iter_text_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel_parts = set(path.relative_to(root).parts)
        if rel_parts & SKIP_DIRS:
            continue
        if path.name in SKIP_FILES:
            continue
        try:
            path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        yield path


def _load_ignore_rules(path: Path) -> list[IgnoreRule]:
    if not path.exists():
        return []
    rules: list[IgnoreRule] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("::", 2)]
        if len(parts) != 3:
            raise ValueError(f"Invalid hygiene ignore rule: {raw_line}")
        rules.append(IgnoreRule(parts[0], re.compile(parts[1]), parts[2]))
    return rules


def _matching_rule(rules: list[IgnoreRule], rel_path: str, line: str) -> IgnoreRule | None:
    for rule in rules:
        if fnmatch.fnmatch(rel_path, rule.glob) and rule.pattern.search(line):
            return rule
    return None


if __name__ == "__main__":
    raise SystemExit(main())
