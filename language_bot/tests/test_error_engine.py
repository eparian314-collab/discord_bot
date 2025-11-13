import sys

from language_bot.core.error_engine import ErrorEngine


def _reset_logger(engine: ErrorEngine):
    for handler in list(engine.logger.handlers):
        handler.close()
        engine.logger.removeHandler(handler)


def test_log_exception_persists_and_prints(tmp_path, capsys):
    log_file = tmp_path / "errors.log"
    engine = ErrorEngine(log_file=str(log_file))

    try:
        engine.log_exception(ValueError("boom"), context="unit-test")
    finally:
        _reset_logger(engine)

    captured = capsys.readouterr()
    assert "unit-test" in captured.err
    assert log_file.read_text().strip()


def test_catch_uncaught_installs_hook(monkeypatch, tmp_path):
    log_file = tmp_path / "errors.log"
    engine = ErrorEngine(log_file=str(log_file))
    calls = []

    def fake_log(exc, context=""):
        calls.append((exc, context))

    engine.log_exception = fake_log  # type: ignore[attr-defined]

    original = sys.excepthook
    engine.catch_uncaught()
    try:
        sys.excepthook(RuntimeError, RuntimeError("failure"), None)
    finally:
        sys.excepthook = original
        _reset_logger(engine)

    assert calls and calls[0][1] == "Uncaught Exception"
