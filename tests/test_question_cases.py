import pytest
from fixtures.fp_cases import CASES
from helpers import FakeFactory, frame, part, option, answer_payload
from quiz_assistant.ai.provider import OpenAIProvider
from quiz_assistant.ai.schemas import validate_answer_payload
from quiz_assistant.models import ApiConfig
from quiz_assistant.ui.result_text import result_text, part_text


@pytest.mark.parametrize("case_id,kind,question,expected", CASES, ids=[c[0] for c in CASES])
def test_functional_category_case_through_fake_api(case_id, kind, question, expected):
    payload = answer_payload(part(kind, expected))
    payload["question_text"] = question
    factory = FakeFactory(payload=payload)
    provider = OpenAIProvider(factory)
    provider.configure("offline-placeholder", ApiConfig())
    result = provider.analyze(frame())
    assert result.answer.parts[0].answer_text == expected
    rendered = result_text(int(case_id), result, (frame(),))
    assert expected in rendered and question in rendered
    assert len(factory.client.payloads) == 1


def test_at_least_forty_distinct_cases():
    assert len(CASES) >= 40
    assert len({c[0] for c in CASES}) == len(CASES)


def test_supplied_screenshot_equivalents():
    # Manually transcribed expectations, not image/OCR/model tests.
    code = validate_answer_payload(answer_payload(part(
        "single_choice", None, options=[option(1, "4334"), option(2, "4994"), option(3, "8338"), option(4, "8998")],
        selected_positions=[2])))
    assert part_text(code.parts[0]) == "B · 4994"
    roots = validate_answer_payload(answer_payload(part(
        "single_choice", None, options=[option(1, "w"), option(2, "x"), option(3, "y"), option(4, "z")],
        selected_positions=[3])))
    assert part_text(roots.parts[0]) == "C · y"
    balls = validate_answer_payload(answer_payload(
        part("dropdown", "nieparzystymi", label="Pozostałe kule"),
        part("dropdown", "30", part_id="p2", label="Suma wylosowanych liczb")))
    assert [p.answer_text for p in balls.parts] == ["nieparzystymi", "30"]
    sums = validate_answer_payload(answer_payload(
        part("dropdown", "5050", label="Suma od 1 do 100"),
        part("single_choice", None, part_id="p2", options=[option(1, "S = 1/2 n² + 1"), option(2, "S = 1/2 n² + 1/2 n")],
             selected_positions=[2])))
    assert sums.status.value == "ok"
    assert "5050" in part_text(sums.parts[0])
    assert part_text(sums.parts[1]).startswith("B")
