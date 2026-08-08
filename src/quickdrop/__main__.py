import logging

from quickdrop.core.storage import app_data_dir
from quickdrop.ui.app import run


def main() -> None:
    logging.basicConfig(
        filename=app_data_dir() / "quickdrop.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.info("QuickDrop starting")
    run()


if __name__ == "__main__":
    main()
