import pytest

def add(a, b):
    """两数之和"""
    return a + b

class TestAdd:
    def test_positive_numbers(self):
        assert add(1, 2) == 3

    def test_negative_numbers(self):
        assert add(-1, -1) == -2

    def test_mixed_numbers(self):
        assert add(-5, 3) == -2

    def test_zero(self):
        assert add(0, 5) == 5
        assert add(5, 0) == 5
        assert add(0, 0) == 0

    def test_floats(self):
        assert add(1.5, 2.5) == 4.0
