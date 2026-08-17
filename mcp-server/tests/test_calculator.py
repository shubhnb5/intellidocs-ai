import pytest

from tools.calculator import calculate


def test_calculate_handles_order_of_operations():
    assert calculate("12 * (4 + 3) / 2") == 42.0


def test_calculate_handles_unary_minus():
    assert calculate("-5 + 10") == 5.0


def test_calculate_handles_power_and_modulo():
    assert calculate("2 ** 10") == 1024.0
    assert calculate("10 % 3") == 1.0


def test_calculate_rejects_non_arithmetic_syntax():
    # This is the security-relevant case: calculate() must never execute
    # arbitrary code, only evaluate arithmetic.
    with pytest.raises(ValueError):
        calculate("__import__('os').system('echo pwned')")


def test_calculate_rejects_garbage_input():
    with pytest.raises(ValueError):
        calculate("not an expression")


def test_calculate_raises_on_division_by_zero():
    with pytest.raises(ValueError):
        calculate("1 / 0")
