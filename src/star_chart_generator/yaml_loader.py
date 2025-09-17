"""Minimal YAML loader supporting the subset needed for generator configs."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Sequence, Tuple


@dataclass
class _Line:
    indent: int
    content: str


def load_yaml(path: Path | str) -> Any:
    """Load a YAML file using a minimal subset parser.

    The loader supports mappings, sequences, floats, ints, booleans and strings
    with optional inline dictionaries or lists. It ignores comments and blank
    lines and expects indentation with spaces.
    """

    path = Path(path)
    text = path.read_text(encoding="utf-8")
    return loads(text)


def loads(text: str) -> Any:
    lines = _prepare_lines(text)
    if not lines:
        return {}
    value, index = _parse_block(lines, 0, lines[0].indent)
    # consume optional trailing lines with lower indent
    return value


def _prepare_lines(text: str) -> List[_Line]:
    lines: List[_Line] = []
    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        stripped = raw_line.split("#", 1)[0].rstrip()
        if not stripped:
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        content = stripped.lstrip(" ")
        lines.append(_Line(indent=indent, content=content))
    return lines


def _parse_block(lines: Sequence[_Line], index: int, indent: int) -> Tuple[Any, int]:
    mapping: dict[str, Any] | None = None
    sequence: List[Any] | None = None

    while index < len(lines):
        line = lines[index]
        if line.indent < indent:
            break
        if line.indent > indent:
            break

        text = line.content
        if text.startswith("- "):
            if mapping is not None:
                raise ValueError("Cannot mix mapping and sequence at same indentation level")
            if sequence is None:
                sequence = []
            value_text = text[2:].strip()
            if value_text:
                if ":" in value_text and not value_text.strip().startswith(("{", "[")):
                    item, index = _parse_inline_sequence_mapping(lines, index, indent, value_text)
                    sequence.append(item)
                else:
                    value = _parse_scalar(value_text)
                    sequence.append(value)
                    index += 1
            else:
                index += 1
                value, index = _parse_block(lines, index, indent + 2)
                sequence.append(value)
        else:
            if sequence is not None:
                raise ValueError("Cannot mix sequence and mapping at same indentation level")
            if mapping is None:
                mapping = {}
            if ":" not in text:
                raise ValueError(f"Expected ':' in mapping entry: {text!r}")
            key, remainder = text.split(":", 1)
            key = key.strip()
            remainder = remainder.strip()
            if remainder:
                mapping[key] = _parse_scalar(remainder)
                index += 1
            else:
                index += 1
                value, index = _parse_block(lines, index, indent + 2)
                mapping[key] = value

    if sequence is not None:
        return sequence, index
    return mapping if mapping is not None else {}, index


def _parse_scalar(text: str) -> Any:
    if not text:
        return ""
    if text.startswith("\"") and text.endswith("\""):
        return _unescape_string(text[1:-1])
    if text.startswith("'") and text.endswith("'"):
        return text[1:-1]
    if text.startswith("{") and text.endswith("}"):
        return _parse_inline_mapping(text[1:-1])
    if text.startswith("[") and text.endswith("]"):
        return _parse_inline_sequence(text[1:-1])
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none"}:
        return None
    try:
        if any(ch in text for ch in [".", "e", "E"]):
            return float(text)
        return int(text)
    except ValueError:
        return text


def _unescape_string(value: str) -> str:
    return value.replace("\\\"", "\"").replace("\\n", "\n").replace("\\t", "\t")


def _parse_inline_mapping(body: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if not body.strip():
        return result
    for item in _split_top_level(body, ","):
        if not item:
            continue
        if ":" not in item:
            raise ValueError(f"Invalid inline mapping entry: {item!r}")
        key, value = item.split(":", 1)
        result[key.strip()] = _parse_scalar(value.strip())
    return result


def _parse_inline_sequence(body: str) -> List[Any]:
    if not body.strip():
        return []
    return [_parse_scalar(part.strip()) for part in _split_top_level(body, ",") if part.strip()]


def _split_top_level(text: str, delimiter: str) -> Iterable[str]:
    parts: List[str] = []
    current: List[str] = []
    depth_brace = depth_bracket = depth_paren = 0
    in_quote = False
    quote_char = ""
    escape = False
    for ch in text:
        if escape:
            current.append(ch)
            escape = False
            continue
        if ch == "\\":
            current.append(ch)
            escape = True
            continue
        if in_quote:
            current.append(ch)
            if ch == quote_char:
                in_quote = False
            continue
        if ch in {'"', "'"}:
            in_quote = True
            quote_char = ch
            current.append(ch)
            continue
        if ch == "{":
            depth_brace += 1
        elif ch == "}":
            depth_brace -= 1
        elif ch == "[":
            depth_bracket += 1
        elif ch == "]":
            depth_bracket -= 1
        elif ch == "(":
            depth_paren += 1
        elif ch == ")":
            depth_paren -= 1
        if ch == delimiter and depth_brace == depth_bracket == depth_paren == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current).strip())
    return parts


def _parse_inline_sequence_mapping(
    lines: Sequence[_Line], index: int, indent: int, value_text: str
) -> Tuple[dict[str, Any], int]:
    key, remainder = value_text.split(":", 1)
    item: dict[str, Any] = {key.strip(): _parse_scalar(remainder.strip())}
    index += 1
    while index < len(lines) and lines[index].indent > indent:
        line = lines[index]
        if ":" not in line.content:
            raise ValueError(f"Expected ':' in mapping entry: {line.content!r}")
        child_key, child_remainder = line.content.split(":", 1)
        child_key = child_key.strip()
        child_remainder = child_remainder.strip()
        if child_remainder:
            item[child_key] = _parse_scalar(child_remainder)
            index += 1
        else:
            index += 1
            nested_value, index = _parse_block(lines, index, line.indent + 2)
            item[child_key] = nested_value
    return item, index


__all__ = ["load_yaml", "loads"]
