from data_ingestion.smoke_tests import build_smoke_bucket_name, check_dependency_imports


def test_build_smoke_bucket_name_sanitizes_input() -> None:
    bucket_name = build_smoke_bucket_name("Data_Ingestion!")

    assert bucket_name == "data-ingestion-smoke"


def test_check_dependency_imports_supports_stdlib_modules() -> None:
    imported = check_dependency_imports(["json", "sqlite3"])

    assert "json" in imported
    assert "sqlite3" in imported
