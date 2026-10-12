from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError, model_validator


class AnswerStatus(str, Enum):
    OK = "ok"
    PARTIAL = "partial"
    UNCERTAIN = "uncertain"
    UNREADABLE = "unreadable"
    INCOMPLETE_VIEW = "incomplete_view"
    NO_QUESTION = "no_question"
    MULTIPLE_QUESTIONS = "multiple_questions"
    UNSUPPORTED_TYPE = "unsupported_type"


class QuestionType(str, Enum):
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    GAP = "gap"
    NUMERIC = "numeric"
    DROPDOWN = "dropdown"
    MATCHING = "matching"
    ORDERING = "ordering"
    OPEN = "open"
    CODE = "code"
    CODE_OUTPUT = "code_output"
    UNKNOWN = "unknown"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QuizOption(StrictModel):
    position: int = Field(ge=1, strict=True)
    label: str | None
    text: str = Field(min_length=1, max_length=20000)


class MatchPair(StrictModel):
    left_position: int = Field(ge=1, strict=True)
    right_position: int = Field(ge=1, strict=True)


class AnswerPart(StrictModel):
    part_id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=500)
    question_type: QuestionType
    status: AnswerStatus
    options: list[QuizOption] = Field(max_length=64)
    targets: list[QuizOption] = Field(max_length=64)
    selected_positions: list[StrictInt]
    answer_text: str | None
    matches: list[MatchPair]
    ordered_positions: list[StrictInt]
    explanation: str | None
    reason: str | None
    warnings: list[str]

    @model_validator(mode="after")
    def validate_part(self) -> "AnswerPart":
        positions = [item.position for item in self.options]
        targets = [item.position for item in self.targets]
        if len(set(positions)) != len(positions) or len(set(targets)) != len(targets):
            raise ValueError("Powtórzone identyfikatory opcji.")
        if self.status != AnswerStatus.OK:
            if self.status == AnswerStatus.PARTIAL:
                raise ValueError("Status partial dotyczy całego zadania.")
            if self.selected_positions or self.answer_text is not None or self.matches or self.ordered_positions:
                raise ValueError("Niepewne pole zawiera aktywną odpowiedź.")
            if not self.reason or not self.reason.strip():
                raise ValueError("Brak przyczyny niepewności.")
            return self
        selected = self.selected_positions
        if len(set(selected)) != len(selected) or not set(selected) <= set(positions):
            raise ValueError("Wybór nie wskazuje unikalnych istniejących opcji.")
        kind = self.question_type
        if kind in (QuestionType.SINGLE_CHOICE, QuestionType.MULTIPLE_CHOICE) or (
            kind == QuestionType.DROPDOWN and self.options
        ) or (kind == QuestionType.TRUE_FALSE and self.options):
            if not selected or (kind != QuestionType.MULTIPLE_CHOICE and len(selected) != 1):
                raise ValueError("Niewłaściwa liczba wybranych opcji.")
            if len(positions) < 2 or self.answer_text is not None:
                raise ValueError("Wybór wymaga opcji; tekst pochodzi z wybranych identyfikatorów.")
            if self.matches or self.ordered_positions or self.targets:
                raise ValueError("Niespójne pola wyboru.")
        elif kind == QuestionType.MATCHING:
            if not positions or not targets or not self.matches:
                raise ValueError("Brak elementów dopasowania.")
            lefts = [pair.left_position for pair in self.matches]
            if len(set(lefts)) != len(lefts) or set(lefts) != set(positions):
                raise ValueError("Dopasowanie musi obejmować każdy lewy element raz.")
            if any(pair.right_position not in targets for pair in self.matches):
                raise ValueError("Nieistniejący prawy element dopasowania.")
            if selected or self.ordered_positions or self.answer_text is not None:
                raise ValueError("Niespójne pola dopasowania.")
        elif kind == QuestionType.ORDERING:
            if not positions or sorted(self.ordered_positions) != sorted(positions):
                raise ValueError("Kolejność musi zawierać wszystkie elementy dokładnie raz.")
            if selected or self.matches or self.targets or self.answer_text is not None:
                raise ValueError("Niespójne pola kolejności.")
        elif kind in (
            QuestionType.OPEN, QuestionType.CODE, QuestionType.CODE_OUTPUT,
            QuestionType.GAP, QuestionType.NUMERIC, QuestionType.DROPDOWN, QuestionType.TRUE_FALSE,
        ):
            if not self.answer_text or not self.answer_text.strip():
                raise ValueError("Brak treści odpowiedzi.")
            if self.options or self.targets or selected or self.matches or self.ordered_positions:
                raise ValueError("Niespójne pola odpowiedzi tekstowej.")
            if kind == QuestionType.TRUE_FALSE and self.answer_text not in ("Prawda", "Fałsz"):
                raise ValueError("Odpowiedź musi brzmieć Prawda albo Fałsz.")
        else:
            raise ValueError("Nieznany typ nie może zawierać aktywnej odpowiedzi.")
        return self


class QuizAnswer(StrictModel):
    status: AnswerStatus
    question_text: str | None
    parts: list[AnswerPart] = Field(max_length=32)
    reason: str | None
    warnings: list[str]

    @model_validator(mode="after")
    def validate_answer(self) -> "QuizAnswer":
        ids = [part.part_id for part in self.parts]
        if len(ids) != len(set(ids)):
            raise ValueError("Powtórzone identyfikatory pól.")
        if self.status in (AnswerStatus.OK, AnswerStatus.PARTIAL):
            if not self.parts or not self.question_text or not self.question_text.strip():
                raise ValueError("Brak pytania lub pól odpowiedzi.")
            valid = sum(part.status == AnswerStatus.OK for part in self.parts)
            if not valid:
                self.status = AnswerStatus.UNCERTAIN
                self.reason = "Żadne pole nie przeszło walidacji."
            elif valid < len(self.parts):
                self.status = AnswerStatus.PARTIAL
            else:
                self.status = AnswerStatus.OK
        elif any(part.status == AnswerStatus.OK for part in self.parts):
            raise ValueError("Odrzucone zadanie nie może zawierać aktywnych odpowiedzi.")
        elif not self.reason or not self.reason.strip():
            raise ValueError("Odrzucone zadanie musi zawierać przyczynę.")
        return self


def validate_answer_payload(payload: object) -> QuizAnswer:
    """Quarantine an invalid part without inventing a correction or hiding good parts."""
    if not isinstance(payload, dict) or not isinstance(payload.get("parts"), list):
        return QuizAnswer.model_validate(payload)
    sanitized = dict(payload)
    parts = []
    for index, raw in enumerate(payload["parts"]):
        try:
            part = AnswerPart.model_validate(raw)
        except ValidationError:
            label = raw.get("label") if isinstance(raw, dict) else None
            part = AnswerPart(
                part_id=f"invalid-{index}", label=label[:500] if isinstance(label, str) and label else f"Pole {index + 1}",
                question_type=QuestionType.UNKNOWN, status=AnswerStatus.UNCERTAIN,
                options=[], targets=[], selected_positions=[], answer_text=None,
                matches=[], ordered_positions=[], explanation=None,
                reason="Niespójne dane tego pola — odpowiedź została odrzucona.",
                warnings=[],
            )
        parts.append(part)
    sanitized["parts"] = parts
    return QuizAnswer.model_validate(sanitized)


QUIZ_ANSWER_JSON_SCHEMA = QuizAnswer.model_json_schema()
