def fib(n: int) -> int:
    """Return the nth Fibonacci number (0-indexed).

    Args:
        n: The index of the Fibonacci number to compute.

    Returns:
        The nth Fibonacci number, where fib(0) = 0 and fib(1) = 1.
    """
    if n < 0:
        raise ValueError(f"n must be non-negative, got {n}")

    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
