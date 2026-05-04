from .pipeline import summarize_batch


def main() -> None:
    records = [{"id": 1}, {"id": 2}, {"id": 3}]
    summary = summarize_batch(records)
    print(f"Processed {summary['record_count']} records.")


if __name__ == "__main__":
    main()
