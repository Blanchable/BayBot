"""Initialize or migrate the database schema."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config.settings import load_settings
from app.db.session import create_tables, init_engine


async def main():
    settings = load_settings()
    init_engine(settings)
    await create_tables()
    print("Database schema created/updated successfully.")


if __name__ == "__main__":
    asyncio.run(main())
