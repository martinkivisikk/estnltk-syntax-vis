import pytest
from helpers import make


@pytest.fixture
def simple():
    return make(
        "Mari elab Tallinnas .", [2, 0, 2, 2], ["nsubj", "root", "obl", "punct"]
    )
