"""Core helpers for ingestion batches."""


def summarize_batch(records: list[dict]) -> dict[str, int]:
    """Return a tiny summary for an input batch."""
    return {"record_count": len(records)}
