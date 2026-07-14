from app.services import reflection_generator, transcript_processor


def test_generate_stays_in_timeline_mode_when_future_llm_key_is_set():
    processed = transcript_processor.process({
        "results": {
            "utterances": [
                {"start_at": 0, "duration": 1000, "msg": "오늘은 운동을 했습니다."},
            ]
        }
    })

    result = reflection_generator.generate(processed, llm_api_key="future-key")

    assert result == {
        "reflection": "• 오늘은 운동을 했습니다.",
        "mode": "timeline",
    }
