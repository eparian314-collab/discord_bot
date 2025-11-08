import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def iter_py_files(base: Path):
    stack = [base]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except (OSError, PermissionError):
            # Skip directories we cannot access (e.g. platform-specific venv folders)
            continue

        for entry in entries:
            if entry.name.startswith('.'):
                continue
            if entry.is_dir():
                if entry.name == "tests":
                    continue
                stack.append(entry)
                continue
            if entry.suffix == ".py":
                yield entry


LITERAL_TOPICS = {
    'translation.requested',
    'translation.completed',
    'translation.failed',
    'engine.error',
    'storage.ready',
    'shutdown.initiated',
}


def test_no_literal_event_topics_present():
    # Build regex safely: match 'topic' or "topic" where topic is any of LITERAL_TOPICS
    topics_union = "|".join(map(re.escape, LITERAL_TOPICS))
    pattern = re.compile(rf"[\'\"](?:{topics_union})[\'\"]")
    offenders = []
    for path in iter_py_files(ROOT):
        text = path.read_text(encoding='utf-8')
        for m in pattern.finditer(text):
            # allow literals inside core/event_topics.py and docs in comments
            if path.as_posix().endswith('core/event_topics.py'):
                continue
            # ignore comments
            line = text[:m.start()].splitlines()[-1]
            if line.strip().startswith('#'):
                continue
            offenders.append((path, m.group(0)))
    assert not offenders, f"Found literal event topics in code: {offenders}"
