import logging
from logging.handlers import RotatingFileHandler
import os
import sys
import traceback


class ErrorEngine:
    def __init__(self, log_file: str = "logs/langbot_errors.log"):
        self.logger = logging.getLogger("LangBotErrorEngine")
        # Ensure logs directory exists
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        # Avoid attaching duplicate file handlers if constructed multiple times
        abs_path = os.path.abspath(log_file)
        has_handler = any(
            isinstance(h, RotatingFileHandler)
            and getattr(h, "baseFilename", None) == abs_path
            for h in self.logger.handlers
        )
        if not has_handler:
            handler = RotatingFileHandler(abs_path, maxBytes=1_000_000, backupCount=5)
            formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.ERROR)

    def log_exception(self, exc: Exception, context: str = ""):
        tb = traceback.format_exc()
        self.logger.error(f"Exception in {context}: {exc}\n{tb}")
        print(f"[LangBot Error] {exc} in {context}", file=sys.stderr)

    def catch_uncaught(self):
        def handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            self.log_exception(exc_value, context="Uncaught Exception")
        sys.excepthook = handle_exception
