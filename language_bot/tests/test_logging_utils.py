import logging

from language_bot.core.logging_utils import configure_library_logging, get_logger


def test_configure_library_logging_sets_handlers():
    logger = configure_library_logging(level=logging.DEBUG)
    assert logger.name == "language_bot"
    assert logger.level == logging.DEBUG
    assert logger.handlers


def test_get_logger_returns_child():
    parent = configure_library_logging()
    child = get_logger("tests")
    assert child.name == "language_bot.tests"
    assert child.parent is parent
