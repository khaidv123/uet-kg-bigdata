from data_ingestion import summarize_batch


def test_summarize_batch_counts_records() -> None:
    summary = summarize_batch([{"id": 1}, {"id": 2}])

    assert summary == {"record_count": 2}
