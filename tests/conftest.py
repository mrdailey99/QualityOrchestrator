import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from engine.decision import DecisionEngine


@pytest.fixture
def engine():
    return DecisionEngine()
