from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text, inspect
from app import db


def test_upgrade_preserves_legacy_run_and_downgrade(tmp_path, monkeypatch):
    engine = create_engine('sqlite:///' + str(tmp_path / 'legacy.db'))
    monkeypatch.setattr(db, 'engine', engine)
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / 'alembic.ini'))
    cfg.set_main_option('script_location', str(root / 'alembic'))
    command.upgrade(cfg, '0001')
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO runs (id,scenario_id,algorithm_id,status,started_at,random_seed,environment,telemetry,metrics,error_message) VALUES (1,1,1,'completed','2026-01-01',7,'{}','[]','{}','')"))
        # Simulate the existing, unversioned MVP database.
        connection.execute(text('DROP TABLE alembic_version'))
    command.upgrade(cfg, 'head')
    with engine.connect() as connection:
        row = connection.execute(text('SELECT id, snapshot, report FROM runs')).one()
        assert row[0] == 1 and row[1] == '{}' and row[2] == '{}'
    command.downgrade(cfg, '0001')
    assert 'snapshot' not in {column['name'] for column in inspect(engine).get_columns('runs')}
    engine.dispose()
