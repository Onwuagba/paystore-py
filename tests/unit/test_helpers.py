"""Tests for utility helpers."""

import re

from paystore.utils.helpers import generate_reference


def test_generate_reference_uses_default_prefix():
    reference = generate_reference()
    assert re.fullmatch(r"TXN_[A-Z0-9]{16}", reference)


def test_generate_reference_uses_custom_prefix():
    reference = generate_reference(prefix="SUB")
    assert reference.startswith("SUB_")


def test_generate_reference_is_unique():
    references = {generate_reference() for _ in range(100)}
    assert len(references) == 100
