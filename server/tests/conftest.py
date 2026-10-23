import os
import tempfile

# the mandatory settings must exist before `app` is imported: _ENVIRONMENT raises otherwise
os.environ.setdefault("SESSION_KEY", "test")
# a file-backed sqlite: `:memory:` would give the test client's thread an empty database
_DB = tempfile.NamedTemporaryFile(prefix="pywebtools-test-", suffix=".db", delete=False)
os.environ.setdefault("DATABASE", _DB.name)

from app.models.tools import create_db_and_tables  # noqa: E402

create_db_and_tables()


import pytest  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine  # noqa: E402


@pytest.fixture
def session_with_models():
    """An empty in-memory catalog: yields (session, make) where make(name, public=True, user_id=1) -> model id."""
    import app.metadata  # noqa: F401  (registers the metadata tables)
    from app.models.tools import Tool

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    session = Session(engine)

    def make(name, public=True, user_id=1):
        tool = Tool(name=name, code="", public=public, user_id=user_id)
        session.add(tool)
        session.commit()
        return tool.id

    yield session, make
    session.close()
