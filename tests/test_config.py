from pathlib import Path

from cross_asset_market_intelligence.config import load_settings


def test_load_settings_resolves_project_relative_paths() -> None:
    root = Path(__file__).resolve().parents[1]
    settings = load_settings(root)

    assert settings.database_path == root / "data" / "market_intelligence.duckdb"
    assert settings.log_level == "INFO"
