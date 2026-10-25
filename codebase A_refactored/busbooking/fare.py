"""Pure fare and refund rules (no Flask, no SQL), so they can be tested on their own."""
SERVICE_FEE = 1.00   # RM per ticket

def calc_fare(fare, n):
    """Return (fare_total, fee_total, total) for n seats."""
    return round(fare * n, 2), round(SERVICE_FEE * n, 2), round((fare + SERVICE_FEE) * n, 2)

def refund_for(hours_before, fare_total):
    """Return (eligible, refund, message): >=24h 100% of fare, 2-24h 50%, <2h not allowed."""
    if hours_before < 2: return False, 0.0, "Cancellation closes 2 hours before departure."
    pct = 1.0 if hours_before >= 24 else 0.5
    return True, round(fare_total * pct, 2), f"{int(pct * 100)}% of the fare is refunded; the service fee is not."
