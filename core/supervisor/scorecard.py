import time
from collections import deque

class Scorecard:
    def __init__(self):
        self.errors = deque()
        self.warnings = deque()
        self.window = 120  # seconds

    def record_error(self):
        now = time.time()
        self.errors.append(now)
        self._cleanup()

    def record_warning(self):
        now = time.time()
        self.warnings.append(now)
        self._cleanup()

    def _cleanup(self):
        cutoff = time.time() - self.window
        while self.errors and self.errors[0] < cutoff:
            self.errors.popleft()
        while self.warnings and self.warnings[0] < cutoff:
            self.warnings.popleft()

    def score(self):
        self._cleanup()
        error_count = len(self.errors)
        warning_count = len(self.warnings)
        if error_count > 20:
            return 0.1
        elif error_count > 10:
            return 0.3
        elif error_count > 5:
            return 0.5
        elif warning_count > 5:
            return 0.7
        else:
            return 1.0
