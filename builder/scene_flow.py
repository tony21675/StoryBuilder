from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Callable, Sequence

from builder.workspace import LLAMA as DEFAULT_LLAMA


SCENE_FLOW_SYSTEM_PROMPT = """You are a careful developmental editor reviewing transitions between adjacent scenes in a novel.

Your job is to evaluate whether the end of the earlier accepted scene flows naturally into the opening of the next accepted scene. You are reviewing, not rewriting.

Protect the author's established canon:
- Use only facts explicitly supported by the supplied scene excerpts.
- Do not invent motives, identities, locations, events, evidence, backstory, or explanations.
- An intentional mystery or unanswered question is not a continuity error merely because it is unresolved.
- Do not assume missing information is an error when the story may be withholding it deliberately.
- Respect physical position, character knowledge, emotional state, time, location, and the exact ending of the earlier scene.
- Pay attention to repeated exposition, abrupt emotional changes, contradictory details, missing transition beats, and openings that restart rather than continue.
- If the transition works, say so. Do not manufacture criticism.
- Prefer the smallest useful adjustment. Do not recommend rewriting a whole scene when one sentence or a brief beat would solve the issue.
- Do not rewrite either scene. Suggest only targeted edits and explain why they would help.

For each scene transition, return this exact Markdown structure:
### Scene A → Scene B
**Assessment:** FLOWS WELL / OPTIONAL POLISH / POSSIBLE DISCONTINUITY
**What I noticed:** Brief, specific explanation grounded in the excerpts.
**Suggested adjustment:** A targeted suggestion. If no change is needed, write "None; keep the transition as written."

Be conservative. Distinguish a definite contradiction from a possible pacing or style preference. Output only the review for this one transition.
"""


def build_transition_prompt(
    previous_label: str,
    previous_text: str,
    next_label: str,
    next_text: str,
    context_chars: int = 4500,
) -> str:
    """Build a focused, canon-protecting prompt from adjacent scene excerpts."""
    previous_text = (previous_text or "").strip()
    next_text = (next_text or "").strip()
    if not previous_text or not next_text:
        raise ValueError("Both accepted scenes must contain prose before their transition can be reviewed.")

    previous_excerpt = previous_text[-max(500, int(context_chars)):]
    next_excerpt = next_text[:max(500, int(context_chars))]
    return (
        "Review the transition from the end of the first accepted scene to the beginning "
        "of the next accepted scene. These are excerpts from adjacent scenes in the same novel.\n\n"
        f"EARLIER SCENE ({previous_label}), ending excerpt:\n"
        f"{previous_excerpt}\n\n"
        f"NEXT SCENE ({next_label}), opening excerpt:\n"
        f"{next_excerpt}\n\n"
        "Check whether the opening respects what is true at the end of the earlier scene. "
        "Report only issues supported by these excerpts, and mark a transition as flowing well "
        "when no meaningful problem is present. Do not fill intentional gaps with invented events."
    )


def _run_transition_review(model: Path, prompt: str) -> str:
    if not DEFAULT_LLAMA.is_file():
        raise FileNotFoundError(f"llama-cli not found: {DEFAULT_LLAMA}")
    model = Path(model).expanduser().resolve()
    if not model.is_file():
        raise FileNotFoundError(f"Model not found: {model}")

    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = str(DEFAULT_LLAMA.parent) + (
        ":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else ""
    )
    device = os.environ.get("STORY_LLM_DEVICE", "").strip()
    args = [str(DEFAULT_LLAMA), "-m", str(model)]
    if device:
        args.extend(["--device", device, "-ngl", "all"])
    else:
        args.extend(["-ngl", "0", "--device", "none"])
    args.extend([
        "-c", "8192",
        "--reasoning", "off",
        "--temp", "0.10",
        "--top-k", "20",
        "--top-p", "0.80",
        "--repeat-last-n", "256",
        "--repeat-penalty", "1.08",
        "--n-predict", "700",
        "--system-prompt", SCENE_FLOW_SYSTEM_PROMPT,
        "--prompt", prompt,
        "--color", "off",
        "--no-display-prompt",
        "--simple-io",
        "--single-turn",
    ])

    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        output, _ = proc.communicate(timeout=600)
    except subprocess.TimeoutExpired as exc:
        proc.kill()
        output, _ = proc.communicate()
        raise TimeoutError("Scene-flow review timed out.") from exc

    if proc.returncode not in (0, None):
        raise RuntimeError("Scene-flow review failed.\n" + (output or "")[-2500:])

    answer = (output or "").replace("\r", "").strip()
    answer = re.sub(
        r"\n?\[ Prompt: .*? \| Generation: .*? \]\s*$",
        "",
        answer,
        flags=re.DOTALL,
    ).strip()
    if not answer:
        raise RuntimeError("The model returned an empty scene-flow review.")
    return answer


def review_chapter_flow(
    model: Path,
    scene_paths: Sequence[Path],
    progress: Callable[[int, int, str], None] | None = None,
) -> str:
    """Review each adjacent pair of accepted scenes without writing to the manuscript."""
    paths = list(scene_paths)
    scenes: list[tuple[str, str]] = []
    for path in paths:
        text = Path(path).read_text(encoding="utf-8").strip()
        if text:
            scenes.append((Path(path).name, text))

    if len(scenes) < 2:
        raise ValueError("At least two non-empty accepted scenes are needed to review scene flow.")

    reviews: list[str] = []
    total = len(scenes) - 1
    for index in range(total):
        previous_label, previous_text = scenes[index]
        next_label, next_text = scenes[index + 1]
        if progress:
            progress(index + 1, total, f"Reviewing {previous_label} → {next_label}...")
        prompt = build_transition_prompt(
            previous_label,
            previous_text,
            next_label,
            next_text,
        )
        report = _run_transition_review(model, prompt)
        reviews.append(f"## Transition {index + 1} of {total}\n\n{report}")

    return (
        "# Scene Flow Review\n\n"
        "This is a review of adjacent accepted scenes. No manuscript files were changed. "
        "Suggestions are optional and should be checked against your intentions.\n\n"
        + "\n\n---\n\n".join(reviews)
        + "\n"
    )
