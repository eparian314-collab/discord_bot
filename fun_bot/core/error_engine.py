import logging
from logging.handlers import RotatingFileHandler
import os
import sys
import traceback

class ErrorEngine:
    def __init__(self, log_file: str = "logs/funbot_errors.log"):
        self.logger = logging.getLogger("FunBotErrorEngine")
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
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
        self.logger.setLevel(logging.DEBUG)

    def log(self, message: str, level: str = "INFO", emoji: str = "✨"):
        msg = f"{emoji} {message}"
        if level == "DEBUG":
            self.logger.debug(msg)
        elif level == "WARNING":
            self.logger.warning(msg)
        elif level == "ERROR":
            self.logger.error(msg)
        else:
            self.logger.info(msg)
        print(msg)

    def log_exception(self, exc: Exception, context: str = ""):
        tb = traceback.format_exc()
        emoji = "💥" if isinstance(exc, Exception) else "⚠️"
        short_tb = "\n".join(tb.splitlines()[:3])
        msg = f"{emoji} [{context}] {type(exc).__name__}: {exc}\n{short_tb}"
        self.logger.error(msg)
        print(f"{emoji} [FunBot Error] {type(exc).__name__}: {exc} in {context}", file=sys.stderr)
        print(f"🚨 Traceback: {short_tb}")

    def catch_uncaught(self):
        def handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            self.log_exception(exc_value, context="Uncaught Exception")
            print("🛑 FunBot encountered an uncaught exception!")
        sys.excepthook = handle_exception

    def takeoff_sequence(self):
        self.log("FunBot is preparing for takeoff...", emoji="🚀")
        self.log("Checking systems...", level="DEBUG", emoji="🔎")
        self.log("All systems go!", emoji="✅")
        self.log("FunBot has launched and is ready to party!", emoji="🎉")
