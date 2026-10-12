from datetime import datetime

from quiz_assistant.ai.schemas import AnswerStatus, QuestionType


def part_text(part) -> str:
    if part.status is not AnswerStatus.OK:
        return "Brak rozstrzygnięcia: " + (part.reason or part.status.value)
    options = {o.position: (o.label + " · " if o.label else "") + o.text for o in part.options}
    targets = {o.position: o.text for o in part.targets}
    if part.selected_positions:
        text = "\n".join(options[i] for i in part.selected_positions)
    elif part.matches:
        text = "\n".join(f"{options[p.left_position]} → {targets[p.right_position]}" for p in part.matches)
    elif part.ordered_positions:
        text = "\n".join(f"{i}. {options[p]}" for i, p in enumerate(part.ordered_positions, 1))
    else:
        text = part.answer_text or ""
    if part.question_type is QuestionType.DROPDOWN and not part.options:
        text += "\nOpcje niewidoczne — wyliczona wartość, nie wskazanie pozycji listy."
    return text


def capture_times(frames) -> str:
    return ", ".join(datetime.fromtimestamp(f.captured_wall_time).strftime("%H:%M:%S") for f in frames)


def result_text(generation, result, frames) -> str:
    answer = result.answer
    lines = [
        f"Generacja #{generation} · {result.model} · zrzuty: {capture_times(frames)}",
        "Wynik dotyczy zapisanych ujęć, nie aktualnego ekranu. Model może się mylić.",
        answer.question_text or "Nie rozpoznano pytania.",
    ]
    if answer.reason:
        lines.append(answer.reason)
    for i, part in enumerate(answer.parts, 1):
        lines.extend(["", f"{i}. {part.label}", part_text(part)])
        if part.explanation:
            lines.append("Uzasadnienie: " + part.explanation)
        lines.extend("Uwaga: " + warning for warning in part.warnings)
    lines.extend("Uwaga: " + warning for warning in answer.warnings)
    if result.usage:
        lines.append(
            f"\nTokeny: {result.usage.input_tokens} + {result.usage.output_tokens}"
            f" · koszt szacowany: USD {result.usage.estimated_cost_usd:.5f}"
        )
    else:
        lines.append("\nBrak usage — koszt niepewny.")
    return "\n".join(lines)
