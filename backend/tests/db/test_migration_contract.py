from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.core.config import REPOSITORY_ROOT
from app.db.migrations import EXPECTED_DATABASE_REVISION


def test_alembic_has_one_expected_head() -> None:
    config = Config(str(REPOSITORY_ROOT / "backend" / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)

    assert scripts.get_heads() == [EXPECTED_DATABASE_REVISION]
    assert scripts.get_base() == EXPECTED_DATABASE_REVISION


def test_initial_migration_is_explicit_and_does_not_import_live_models() -> None:
    migration_path = (
        REPOSITORY_ROOT
        / "backend"
        / "alembic"
        / "versions"
        / "20260802_0001_initial_schema.py"
    )
    source = Path(migration_path).read_text(encoding="utf-8")

    assert "Base.metadata.create_all" not in source
    assert "import app.models" not in source
    assert source.count("op.create_table(") == 15
