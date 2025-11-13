import logging
import sys
import traceback

class ErrorEngine:
    def __init__(self, log_file: str = "funbot_errors.log"):
        self.logger = logging.getLogger("FunBotErrorEngine")
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.ERROR)

    def log_exception(self, exc: Exception, context: str = ""):
        tb = traceback.format_exc()
        self.logger.error(f"Exception in {context}: {exc}\n{tb}")
        print(f"[FunBot Error] {exc} in {context}", file=sys.stderr)

    def catch_uncaught(self):
        def handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            self.log_exception(exc_value, context="Uncaught Exception")
        sys.excepthook = handle_exception
