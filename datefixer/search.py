"""Search utilities for datefixer.

Provides a small glob-based search with an EXIF-tag comparison mini-DSL
and optional move-to behaviour for matched files.
"""
from __future__ import annotations

import glob
import os
import re
import shutil
import operator
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from . import exiftool
from .utils import parse_date

_OP_MAP: Dict[str, Callable] = {
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
    "<>": operator.ne,
}

_CMP_RE = re.compile(r"^\s*(?P<a>.+?)\s*(?P<op>>=|<=|<>|!=|==|>|<)\s*(?P<b>.+)\s*$")


def _parse_cmp_expr(expr: str) -> Tuple[str, str, str]:
    m = _CMP_RE.match(expr)
    if not m:
        raise ValueError("compare expression must be: TagA OP TagB  (e.g. DateTimeOriginal > DateTimeDigitized)")
    return m.group("a"), m.group("op"), m.group("b")


def _find_tag_value(tags: Dict[str, object], name: str) -> Optional[str]:
    """Case-insensitive substring match on tag keys and return its string value.

    Returns the first matching tag's string representation or ``None`` when
    no match is found.
    """
    if not tags:
        return None
    name_l = name.lower()
    for k, v in tags.items():
        if name_l in k.lower():
            return str(v) if v is not None else None
    return None


def _coerce_value(val: Optional[str]):
    if val is None:
        return None
    # try datetime
    dt = parse_date(val)
    if dt:
        return dt
    # try numeric
    try:
        return float(val)
    except Exception:
        return val.strip()


def _eval_cmp_term(tags: Dict[str, object], term: str) -> bool:
    """Evaluate a single comparison term against exif tags for a file.

    `term` can compare two tags or a tag against a literal value. If a
    side is a tag name and a matching tag key is present in `tags`, the
    tag's value is used; otherwise the side is treated as a literal.
    """
    m = _CMP_RE.match(term)
    if not m:
        raise ValueError(f"invalid comparison term: {term!r}")
    a_raw_s = m.group("a").strip()
    op = m.group("op")
    b_raw_s = m.group("b").strip()

    # Resolve tag values if present, otherwise treat as literal
    a_tag_val = _find_tag_value(tags, a_raw_s)
    b_tag_val = _find_tag_value(tags, b_raw_s)

    if a_tag_val is None:
        a_val_raw = a_raw_s
    else:
        a_val_raw = a_tag_val
    if b_tag_val is None:
        b_val_raw = b_raw_s
    else:
        b_val_raw = b_tag_val

    a_val = _coerce_value(a_val_raw)
    b_val = _coerce_value(b_val_raw)

    opfunc = _OP_MAP.get(op)
    if not opfunc:
        raise ValueError(f"unsupported operator: {op}")
    try:
        return bool(opfunc(a_val, b_val))
    except Exception:
        return bool(opfunc(str(a_val_raw), str(b_val_raw)))


def search_files(pattern: str, compare: Optional[str] = None, move_to: Optional[str] = None, dry_run: bool = False) -> List[Path]:
    """Search for files matching `pattern` and optional `compare`.

    Args:
        pattern: glob pattern passed to ``glob.glob(..., recursive=True)``.
        compare: optional mini-DSL expression like "Exif:ExifIFD:DateTimeOriginal > DateTimeDigitized".
        move_to: optional directory to move matched files into.
        dry_run: when True, do not actually move files.

    Returns:
        List of matched file Paths (after move if applicable).
    """
    matches: List[Path] = []
    # If no compare expression provided, match all files from the pattern
    for p in glob.glob(pattern, recursive=True):
        path = Path(p)
        if not path.is_file():
            continue

        tags = exiftool.read_all_tags(path)

        ok = True
        if compare:
            # Support chaining with | (OR) and & (AND). & has higher precedence.
            or_terms = [t.strip() for t in re.split(r"\s*\|\s*", compare) if t.strip()]
            ok = False
            for or_term in or_terms:
                and_terms = [t.strip() for t in re.split(r"\s*&\s*", or_term) if t.strip()]
                and_ok = True
                for term in and_terms:
                    try:
                        res = _eval_cmp_term(tags, term)
                    except Exception:
                        res = False
                    if not res:
                        and_ok = False
                        break
                if and_ok:
                    ok = True
                    break

        if ok:
            if move_to:
                dest_root = Path(move_to)
                dest_root.mkdir(parents=True, exist_ok=True)
                dest = dest_root / path.name
                # avoid overwriting
                if dest.exists():
                    base, ext = os.path.splitext(path.name)
                    i = 1
                    while True:
                        candidate = f"{base}_{i}{ext}"
                        dest = dest_root / candidate
                        if not dest.exists():
                            break
                        i += 1
                if not dry_run:
                    shutil.move(str(path), str(dest))
                    matches.append(dest)
                else:
                    matches.append(path)
            else:
                matches.append(path)

    return matches


def cmd_search(args):
    """Argparse wrapper used by the CLI."""
    matches = search_files(
        pattern=args.pattern,
        compare=getattr(args, "compare", None),
        move_to=getattr(args, "move_to", None),
        dry_run=bool(getattr(args, "dry_run", False)),
    )
    for m in matches:
        print(m)
    print(f"Found {len(matches)} match(es).")
