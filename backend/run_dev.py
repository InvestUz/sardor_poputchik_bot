"""Local development: applies migrations and starts the server with auto-reload.

    python run_dev.py            (reads backend/.env)
"""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.chdir(HERE)
sys.path.insert(0, str(HERE))
(HERE / "data").mkdir(exist_ok=True)

if __name__ == "__main__":
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(HERE / "alembic.ini")), "head")

    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.environ.get("PORT", 8000)), reload=True, reload_dirs=[str(HERE / "app")])
