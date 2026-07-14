from app.services import transcript_processor


def test_process_removes_duplicate_utterances_but_keeps_other_text():
    rtzr_result = {
        "results": {
            "utterances": [
                {
                    "start_at": 0,
                    "duration": 1000,
                    "msg": "오늘은 발표 준비를 했습니다.",
                },
                {
                    "start_at": 1200,
                    "duration": 1000,
                    "msg": "오늘은 발표 준비를 했습니다.",
                },
                {
                    "start_at": 2600,
                    "duration": 1200,
                    "msg": "자료를 다시 읽었습니다.",
                },
            ]
        }
    }

    processed = transcript_processor.process(rtzr_result)

    assert processed.full_text == "오늘은 발표 준비를 했습니다. 자료를 다시 읽었습니다."
    assert processed.timeline_text == "• 오늘은 발표 준비를 했습니다.\n• 자료를 다시 읽었습니다."
    assert len(processed.raw_utterances) == 2
    assert processed.duplicate_count == 1


def test_process_keeps_rtzr_paragraph_units_without_silence_grouping():
    rtzr_result = {
        "results": {
            "utterances": [
                {"start_at": 0, "duration": 1000, "msg": "아침에는 운동을 했습니다."},
                {"start_at": 3000, "duration": 1000, "msg": "몸이 가벼워졌습니다."},
                {"start_at": 15000, "duration": 1000, "msg": "저녁에는 코드를 정리했습니다."},
            ]
        }
    }

    processed = transcript_processor.process(rtzr_result)

    assert len(processed.events) == 3
    assert [event.text for event in processed.events] == [
        "아침에는 운동을 했습니다.",
        "몸이 가벼워졌습니다.",
        "저녁에는 코드를 정리했습니다.",
    ]


def test_process_keeps_repeated_text_when_it_belongs_to_a_later_event():
    rtzr_result = {
        "results": {
            "utterances": [
                {"start_at": 0, "duration": 1000, "msg": "회의를 했습니다."},
                {"start_at": 15000, "duration": 1000, "msg": "회의를 했습니다."},
            ]
        }
    }

    processed = transcript_processor.process(rtzr_result)

    assert len(processed.raw_utterances) == 2
    assert len(processed.events) == 2
    assert processed.timeline_text == "• 회의를 했습니다.\n• 회의를 했습니다."


def test_process_keeps_repeated_text_after_an_intervening_utterance():
    rtzr_result = {
        "results": {
            "utterances": [
                {"start_at": 0, "duration": 1000, "msg": "회의를 했습니다."},
                {"start_at": 2000, "duration": 1000, "msg": "업무를 정리했습니다."},
                {"start_at": 4000, "duration": 1000, "msg": "회의를 했습니다."},
            ]
        }
    }

    processed = transcript_processor.process(rtzr_result)

    assert [u.msg for u in processed.raw_utterances] == [
        "회의를 했습니다.",
        "업무를 정리했습니다.",
        "회의를 했습니다.",
    ]


def test_build_timeline_uses_time_expressions_and_keeps_actual_order():
    rtzr_result = {
        "results": {
            "utterances": [
                {"start_at": 0, "duration": 1000, "msg": "아침에 운동을 했습니다."},
                {"start_at": 2000, "duration": 1000, "msg": "몸이 가벼웠습니다."},
                {"start_at": 4000, "duration": 1000, "msg": "발표 자료도 정리했습니다."},
                {
                    "start_at": 80000,
                    "duration": 1000,
                    "msg": "저녁에는 친구를 만났습니다.",
                    "words": [
                        {"start_at": 81500, "duration": 500, "text": "저녁에는"},
                        {"start_at": 82000, "duration": 500, "text": "친구를"},
                    ],
                },
                {"start_at": 82000, "duration": 1000, "msg": "함께 식사를 했습니다."},
            ]
        }
    }

    timeline = transcript_processor.build_timeline(
        transcript_processor.process(rtzr_result)
    )

    assert [(section.label, section.text) for section in timeline] == [
        (
            "00:00",
            "아침에 운동을 했습니다. 몸이 가벼웠습니다. 발표 자료도 정리했습니다.",
        ),
        ("01:21", "저녁에는 친구를 만났습니다. 함께 식사를 했습니다."),
    ]
    assert [section.start_at for section in timeline] == [0.0, 81.5]


def test_build_timeline_does_not_split_when_time_word_is_mid_sentence():
    rtzr_result = {
        "results": {
            "utterances": [
                {
                    "start_at": 0,
                    "duration": 4000,
                    "msg": (
                        "점심에는 근로를 갔고 근로 중에도 계속 이 작업을 했습니다. "
                        "에코로그를 기획했고 집에 가서 저녁을 먹고 쉬었습니다."
                    ),
                }
            ]
        }
    }

    timeline = transcript_processor.build_timeline(
        transcript_processor.process(rtzr_result)
    )

    assert [(section.label, section.text) for section in timeline] == [
        (
            "00:00",
            (
                "점심에는 근로를 갔고 근로 중에도 계속 이 작업을 했습니다. "
                "에코로그를 기획했고 집에 가서 저녁을 먹고 쉬었습니다."
            ),
        )
    ]
