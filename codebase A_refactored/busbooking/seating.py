"""Seat layout (2+2) helpers."""
def seat_labels(n): return [f"{i // 4 + 1}{'ABCD'[i % 4]}" for i in range(n)]
def seat_rows(n): l = seat_labels(n); return [l[i:i + 4] for i in range(0, n, 4)]
