from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class DraftFinding:
    category: str
    message: str
    location: str
    excerpt: str = ""


_WORD = re.compile(r"[\w’'-]+", re.UNICODE)
_SENTENCE = re.compile(r'[^.!?]+[.!?]+(?:["”’\')\]]*)|[^.!?]+$', re.DOTALL)
_AI_START = re.compile(
    r"^(?:(?:certainly|of course|sure)[,!. ]{1,12}(?:here(?:'s| is)|below is)\b|"
    r"here(?:'s| is)\s+(?:the|your)\s+(?:scene|story|draft)\b|"
    r"below is\s+(?:the|your)\s+(?:scene|story|draft)\b|as an ai\b|i can help with that\b)",
    re.I,
)
_AI_END = re.compile(
    r"(?:i hope you (?:enjoy|like) (?:the )?(?:scene|story|draft)|"
    r"let me know if you(?:'d| would) like|hope this helps|happy writing)[.!\s]*$",
    re.I,
)
_CONNECTORS = {
    "and", "but", "because", "although", "though", "while", "when", "if", "as",
    "that", "which", "who", "whom", "whose", "where", "to", "with", "of", "for",
    "from", "in", "on", "at", "by", "between", "into", "onto", "the", "a", "an", "his",
    "her", "their", "its", "our", "your", "my",
}
_STOP = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by",
    "for", "from", "had", "has", "have", "he", "her", "hers", "him", "his",
    "i", "if", "in", "into", "is", "it", "its", "me", "my", "of", "on", "or",
    "our", "ours", "she", "so", "that", "the", "their", "theirs", "them", "they",
    "this", "those", "to", "us", "was", "we", "were", "what", "when", "where",
    "which", "who", "with", "you", "your", "yours",
}


def _words(value: str) -> tuple[str, ...]:
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return tuple(m.group(0).replace("’", "'") for m in _WORD.finditer(value))


def _excerpt(value: str, limit: int = 160) -> str:
    value = " ".join(value.split())
    return value if len(value) <= limit else value[:limit - 1].rstrip() + "…"


def _paragraphs(text: str):
    number = 0
    for match in re.finditer(r"\S.*?(?=(?:\n[ \t]*\n+)|\Z)", text, re.S):
        value = match.group(0).strip()
        if value:
            number += 1
            yield number, match.start(), value


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, max(0, offset)) + 1


def analyze_draft(text: str) -> list[DraftFinding]:
    """Return conservative advisory findings. The input is never modified."""
    source = str(text or "")
    if not source.strip():
        return []
    paras = list(_paragraphs(source))
    findings: list[DraftFinding] = []
    duplicate_para_nums: set[int] = set()
    excluded_spans: list[tuple[int, int]] = []

    # Identical substantial paragraphs.
    para_groups: dict[tuple[str, ...], list[tuple[int, int, str]]] = defaultdict(list)
    for number, start, value in paras:
        words = _words(value)
        if len(words) >= 10 and len(value) >= 55:
            para_groups[words].append((number, start, value))
    for occurrences in para_groups.values():
        if len(occurrences) < 2:
            continue
        duplicate_para_nums.update(item[0] for item in occurrences)
        excluded_spans.extend((start, start + len(value)) for _n, start, value in occurrences)
        findings.append(DraftFinding(
            "Duplicate paragraph",
            "The same substantial paragraph appears more than once.",
            "Paragraphs " + ", ".join(str(item[0]) for item in occurrences),
            _excerpt(occurrences[0][2]),
        ))

    # Identical complete sentences outside paragraphs already reported above.
    sentence_groups: dict[tuple[str, ...], list[tuple[int, int, int, str]]] = defaultdict(list)
    for para_num, para_start, para in paras:
        if para_num in duplicate_para_nums:
            continue
        sentence_num = 0
        for match in _SENTENCE.finditer(para):
            value = match.group(0).strip()
            words = _words(value)
            if len(words) < 8 or len(value) < 48:
                continue
            sentence_num += 1
            sentence_groups[words].append((para_num, sentence_num, para_start + match.start(), value))
    for occurrences in sentence_groups.values():
        if len(occurrences) < 2:
            continue
        first = occurrences[0]
        labels = [f"paragraph {p}, sentence {s}" for p, s, _start, _value in occurrences]
        findings.append(DraftFinding(
            "Duplicate sentence",
            "The same complete sentence appears more than once.",
            " and ".join(labels),
            _excerpt(first[3]),
        ))
        excluded_spans.extend((start, start + len(value)) for _p, _s, start, value in occurrences)

    # Repeated six-word phrases: at least three times, with two meaningful words.
    normalised = unicodedata.normalize("NFKC", source).casefold()
    matches = list(_WORD.finditer(normalised))
    tokens = [m.group(0).replace("’", "'") for m in matches]
    phrase_groups: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for i in range(max(0, len(tokens) - 5)):
        phrase = tuple(tokens[i:i + 6])
        if sum(word not in _STOP and len(word) > 2 for word in phrase) >= 2:
            phrase_groups[phrase].append(i)
    repeated = sorted(
        ((positions[0], phrase, positions) for phrase, positions in phrase_groups.items()
         if len(positions) >= 3 and positions[-1] - positions[0] <= 500),
        key=lambda item: item[0],
    )
    used: list[tuple[int, int]] = []
    for _first, phrase, positions in repeated:
        spans = [(matches[i].start(), matches[i + 5].end()) for i in positions]
        if any(a < used_end and b > used_start
               for a, b in spans for used_start, used_end in used):
            continue
        if all(any(x <= a and b <= y for x, y in excluded_spans) for a, b in spans):
            continue
        findings.append(DraftFinding(
            "Repeated phrase",
            "A distinctive six-word phrase appears at least three times within a relatively short span.",
            ", ".join(f"line {_line(source, a)}" for a, _b in spans[:3]),
            " ".join(phrase),
        ))
        used.extend(spans)
        if sum(f.category == "Repeated phrase" for f in findings) >= 3:
            break

    # Only flag clear signs of an unfinished ending or unmatched delimiters.
    stripped = source.rstrip()
    final_line = next((line.strip() for line in reversed(stripped.splitlines()) if line.strip()), "")
    final_words = _words(final_line)
    final_char = stripped[-1]
    if final_words and final_words[-1] in _CONNECTORS and final_char not in ".!?\"”’)]}…":
        findings.append(DraftFinding(
            "Possible abrupt ending",
            "The final line ends with a word that often introduces unfinished text.",
            f"Line {_line(source, len(stripped))}",
            _excerpt(final_line),
        ))
    elif final_char in {",", ":", ";", "—", "–"}:
        findings.append(DraftFinding(
            "Possible abrupt ending",
            "The draft ends with punctuation that may indicate an unfinished sentence.",
            f"Line {_line(source, len(stripped))}",
            _excerpt(final_line),
        ))

    pairs = {"(": ")", "[": "]", "{": "}"}
    closing = {value: key for key, value in pairs.items()}
    stack: list[tuple[str, int]] = []
    for i, char in enumerate(source):
        if char in pairs:
            stack.append((char, i))
        elif char in closing and stack and stack[-1][0] == closing[char]:
            stack.pop()
    if stack:
        char, offset = stack[-1]
        findings.append(DraftFinding(
            "Possible truncation",
            f"An opening '{char}' has no matching closing character.",
            f"Line {_line(source, offset)}",
            _excerpt(source[offset:offset + 100]),
        ))
    if source.count("“") > source.count("”") or source.count('"') % 2:
        findings.append(DraftFinding(
            "Possible truncation",
            "A quotation appears to be left open at the end of the draft.",
            f"Line {_line(source, len(stripped))}",
            _excerpt(final_line),
        ))

    # Assistant boilerplate is checked only at the document's outer edges.
    if paras:
        first_num, _first_start, first = paras[0]
        last_num, _last_start, last = paras[-1]
        first_line = first.splitlines()[0].strip()
        last_line = last.splitlines()[-1].strip()
        if _AI_START.search(first_line):
            findings.append(DraftFinding(
                "Possible AI commentary",
                "The opening looks like an assistant preamble rather than story prose.",
                f"Opening paragraph {first_num}",
                _excerpt(first_line),
            ))
        elif _AI_END.search(last_line):
            findings.append(DraftFinding(
                "Possible AI commentary",
                "The ending looks like assistant commentary rather than story prose.",
                f"Final paragraph {last_num}",
                _excerpt(last_line),
            ))
    return findings


def format_draft_health_report(findings: list[DraftFinding]) -> str:
    """Format results for the Writer's selectable, copyable review dialog."""
    if not findings:
        return (
            "No obvious mechanical issues found.\n\n"
            "This check looks for a few common text problems. It does not judge story quality, "
            "continuity, or whether a stylistic choice is intentional."
        )
    lines = [
        f"Found {len(findings)} possible mechanical issue(s). These are advisory only.",
        "Nothing has been changed in your draft. Review each finding and decide whether it matters.",
    ]
    for index, finding in enumerate(findings, 1):
        lines.extend(["", f"{index}. {finding.category}", finding.message, f"Location: {finding.location}"])
        if finding.excerpt:
            lines.append(f'Excerpt: "{finding.excerpt}"')
    lines.extend(["", "This check does not judge story quality or continuity. Repetition can be intentional."])
    return "\n".join(lines)
