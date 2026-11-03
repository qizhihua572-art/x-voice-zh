import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "x-voice-zh", "scripts")
EXAMPLES = os.path.join(ROOT, "examples")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()
