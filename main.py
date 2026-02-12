import sys
import os
import logging

from PyQt6.QtWidgets import QApplication

from GhCommons import get_db_path, get_data_dir, APP_TITLE, COMPANY_NAME
from GhModels import initialize_db
from GhEval import GhEvalMainWindow


def setup_logging():
    """Configure application logging."""
    log_dir = get_data_dir()
    log_file = os.path.join(log_dir, "gheval.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting GHEval")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setOrganizationName(COMPANY_NAME)

    db_path = get_db_path()
    logger.info(f"Database: {db_path}")
    initialize_db(db_path)

    window = GhEvalMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
