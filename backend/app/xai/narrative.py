"""Plain-language text for the report: what each factor means, and the summary paragraph.

The wording is deliberately neutral and impersonal ("the model estimated ...", never "you are bad
at ..."): the report describes the model's reasoning about answers in this app, not the person.
"""

DISCLAIMER = (
    "This report shows how a statistical model reasons about answers in this app. It is not a "
    "clinical, psychological or diagnostic assessment, and it says nothing about ability outside "
    "these exercises. The explanations describe the model, not causes in the learner."
)

# what each of the performance model's inputs means, in plain words
MEANINGS: dict[str, str] = {
    "mastery": "How well the app estimates this concept is known",
    "prereq_mean": "How well the concepts it builds on are known, on average",
    "prereq_min": "How well the least-known concept it builds on is known",
    "attempts": "How many questions on this concept have been answered",
    "recent_accuracy": "Share of recent answers on this concept that were right",
    "overall_accuracy": "Share of all answers so far that were right",
    "streak": "Run of right (+) or wrong (-) answers on this concept",
    "misconception": "Whether a known misconception on this concept is flagged",
    "item_difficulty": "How hard this particular question is (1 to 5)",
    "guess_rate": "Chance of getting it right by guessing (1 / number of options)",
    "days_since_practice": "Time since this concept was last practised",
    "self_efficacy": "Confidence, as reported in the questionnaire",
    "persistence": "Persistence, as reported in the questionnaire",
}

TRAIT_LABELS: dict[str, str] = {
    "abstraction_preference": "Rules first",
    "load_tolerance": "Longer explanations",
    "depth_preference": "Why it works",
    "persistence": "Persistence",
    "self_efficacy": "Confidence",
}

CLUSTER_LABELS: dict[str, str] = {
    "basics": "Basics",
    "arrays-strings": "Arrays & strings",
    "linked-structures": "Linked structures",
    "recursion": "Recursion",
    "sorting-searching": "Sorting & searching",
    "trees": "Trees",
    "graphs": "Graphs",
    "dp": "Dynamic programming",
}


def _join(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def summary_paragraph(
    *,
    concept: str | None,
    p_correct: float | None,
    top: list[tuple[str, str]],  # (factor label, "raised" | "lowered"), strongest first
    agreement: tuple[str, str, float] | None,  # (methods, verdict word, rho)
    recent_top: str | None,
    n_recent: int,
    counterfactual: str | None,
    counterfactual_direction: str | None = None,  # "above" | "below" 50%
) -> str:
    """The auto-generated paragraph at the top of the Explainability section."""
    if p_correct is None or concept is None:
        if n_recent == 0:
            return (
                "There is nothing to explain yet: the model needs at least one recommended "
                "question to make a prediction."
            )
        lead = f"The model has made predictions for {n_recent} answered questions."
    else:
        lead = (
            f"For the latest question, on {concept}, the model estimated a "
            f"{round(p_correct * 100)}% chance of a correct answer."
        )
    sentences = [lead]
    if top:
        factors = [f"{label.lower()} ({effect} it)" for label, effect in top]
        sentences.append(f"The strongest factors were {_join(factors)}.")
    if agreement is not None:
        methods, word, rho = agreement
        sentences.append(f"{methods} {word} on what mattered most (rank correlation {rho:.2f}).")
    if recent_top and n_recent > 1:
        sentences.append(
            f"Across the last {n_recent} questions, {recent_top.lower()} mattered most on average."
        )
    if counterfactual:
        side = f"{counterfactual_direction} 50%" if counterfactual_direction else "past 50%"
        sentences.append(
            f"A small, realistic change that would move the prediction {side}: {counterfactual}."
        )
    return " ".join(sentences)
