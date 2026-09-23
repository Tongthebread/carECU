import os
import tempfile
from pathlib import Path

# Never write to the developer's database, even during startup/migrations.
_test_directory = tempfile.TemporaryDirectory(prefix="driveeval-tests-")
os.environ["DRIVEEVAL_DATABASE_URL"] = os.getenv("DRIVEEVAL_TEST_DATABASE_URL", "sqlite:///" + str(Path(_test_directory.name) / "test.db"))

import pytest
from app.db import Base, engine, init_db


@pytest.fixture(autouse=True)
def clean_database():
    init_db()
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
