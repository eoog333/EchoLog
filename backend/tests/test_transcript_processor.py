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
    assert processed.timeline_text == "• 오늘은 발표 준비를 했습니다. 자료를 다시 읽었습니다."
    assert len(processed.raw_utterances) == 2


def test_process_uses_duration_to_group_events_by_gap():
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

    assert len(processed.events) == 2
    assert processed.events[0].text == "아침에는 운동을 했습니다. 몸이 가벼워졌습니다."
    assert processed.events[1].text == "저녁에는 코드를 정리했습니다."
