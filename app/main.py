"""Main entry point: initializes DB, loads settings, launches GUI with async loop."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    import qasync
    from PySide6.QtWidgets import QApplication

    from app.config.settings import load_settings
    from app.db.session import create_tables, init_engine
    from app.gui.main_window import MainWindow
    from app.services.bot_controller import BotController
    from app.utils.logging import setup_logging

    settings = load_settings()
    setup_logging(level=settings.log_level, log_file=settings.log_file)

    # Ensure data dirs exist
    Path("data/artifacts").mkdir(parents=True, exist_ok=True)
    Path("data/logs").mkdir(parents=True, exist_ok=True)
    Path("data/exports").mkdir(parents=True, exist_ok=True)

    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    # Init DB
    init_engine(settings)
    loop.run_until_complete(create_tables())

    # Create bot controller
    bot = BotController(settings)

    # Create and show GUI
    window = MainWindow(settings, bot)
    window.show()

    # Auto-start if configured
    if settings.auto_start:
        asyncio.ensure_future(bot.start())

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
