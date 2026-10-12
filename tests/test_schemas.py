import pytest
from pydantic import ValidationError
from quiz_assistant.ai.schemas import QuizAnswer, AnswerPart, QUIZ_ANSWER_JSON_SCHEMA, validate_answer_payload
from quiz_assistant.ui.result_text import part_text
from helpers import part, option, answer_payload


@pytest.mark.parametrize("kind", ["single_choice", "multiple_choice", "dropdown", "true_false"])
def test_choices_are_references_not_rewritten_text(kind):
    data = part(kind, None, options=[option(1, "a !== A"), option(2, "a === A")], selected_positions=[1])
    value = AnswerPart.model_validate(data)
    assert "a !== A" in part_text(value)
    data["selected_positions"] = [3]
    with pytest.raises(ValidationError):
        AnswerPart.model_validate(data)


def test_multiple_choice():
    value = AnswerPart.model_validate(part("multiple_choice", None, options=[option(1, "A"), option(2, "B")], selected_positions=[1, 2]))
    assert value.selected_positions == [1, 2]


@pytest.mark.parametrize("kind,text", [
    ("true_false", "Fałsz"), ("gap", "flatMap"), ("numeric", "5050"),
    ("dropdown", "parzystymi"), ("open", "Łączność i element neutralny."),
    ("code", "const X = 'Ab';\n  X !== 'ab';"), ("code_output", "false\n0\nundefined"),
])
def test_text_variants_preserve_exact_content(kind, text):
    value = AnswerPart.model_validate(part(kind, text))
    assert value.answer_text == text
    assert text in part_text(value)


def test_hidden_dropdown_never_invents_label():
    value = AnswerPart.model_validate(part("dropdown", "5050"))
    assert "Opcje niewidoczne" in part_text(value)
    assert value.selected_positions == []


def test_matching_and_ordering():
    opts = [option(1, "Maybe"), option(2, "Either")]
    targets = [option(1, "Błąd lub sukces"), option(2, "Opcjonalność")]
    value = AnswerPart.model_validate(part("matching", None, options=opts, targets=targets, matches=[
        {"left_position": 1, "right_position": 2}, {"left_position": 2, "right_position": 1}]))
    assert "Maybe → Opcjonalność" in part_text(value)
    ordered = AnswerPart.model_validate(part("ordering", None, options=opts, ordered_positions=[2, 1]))
    assert part_text(ordered).startswith("1. B · Either")


@pytest.mark.parametrize("change", [
    dict(selected_positions=[1, 1]), dict(selected_positions=[True]), dict(selected_positions=["1"]),
    dict(selected_positions=[2, 1]), dict(answer_text="rewritten"), dict(status="uncertain"),
])
def test_invalid_choice_rejected(change):
    value = part("single_choice", None, options=[option(1, "A"), option(2, "B")], selected_positions=[1])
    value.update(change)
    with pytest.raises(ValidationError):
        AnswerPart.model_validate(value)


def test_mixed_partial_quarantines_one_bad_field():
    data = answer_payload(part("numeric", "5050"), part("single_choice", "invalid", part_id="p2"))
    result = validate_answer_payload(data)
    assert result.status.value == "partial"
    assert result.parts[0].answer_text == "5050"
    assert result.parts[1].answer_text is None
    assert result.parts[1].reason


def test_mixed_questions_have_no_active_answers():
    data = dict(status="multiple_questions", question_text=None, parts=[], reason="Ujęcia dotyczą zadań 2 i 3.", warnings=[])
    assert QuizAnswer.model_validate(data).parts == []
    data["parts"] = [part()]
    with pytest.raises(ValidationError):
        QuizAnswer.model_validate(data)


@pytest.mark.parametrize("text", ["Const x = 'A';", "x != null", "x !== null", "!(a && b)", "0", "false", "NaN", "undefined", "<b>not HTML</b>"])
def test_case_operators_negation_and_literals_never_normalized(text):
    assert AnswerPart.model_validate(part("code_output", text)).answer_text == text


def test_strict_schema_all_objects_forbid_extras_and_require_every_field():
    def inspect(schema):
        if isinstance(schema, dict):
            if schema.get("type") == "object":
                assert schema["additionalProperties"] is False
                assert set(schema["required"]) == set(schema["properties"])
            for value in schema.values():
                inspect(value)
        elif isinstance(schema, list):
            for value in schema:
                inspect(value)
    inspect(QUIZ_ANSWER_JSON_SCHEMA)
