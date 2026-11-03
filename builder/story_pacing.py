"""Light-touch, reusable guidance for choosing a story's opening pace."""


def build_story_opening_pacing_prompt() -> str:
    """Return flexible opening guidance without prescribing a scene count."""
    return """STORY OPENING AND PACING (flexible guidance)
Choose an opening pace that fits this specific story, its premise, genre, tone, and the author's direction. Early in a story, give readers enough opportunity to understand the central characters, their world, and the relationships or circumstances that make their lives matter before the central conflict takes over, when that groundwork will benefit the story. For an ensemble, this may take several scenes and can unfold through different character groupings; it need not be completed in one introductory scene.
Judge how much groundwork is needed from the story already written, not a fixed scene count, percentage, or formula. Do not assume the central crisis, danger, mystery, or inciting incident belongs in Scene 1 or the immediately following scene simply because the story has begun. At the same time, do not force ordinary scenes, invent filler, or artificially delay an urgent conflict when immediate action fits this story or the author explicitly asks for it. Once the central conflict is underway, carry it forward naturally rather than restarting an opening phase."""
