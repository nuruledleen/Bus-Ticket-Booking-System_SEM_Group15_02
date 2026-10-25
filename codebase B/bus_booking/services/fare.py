"""The single place where fares are calculated (all amounts in sen)."""


def calculate_total_fare(fare_sen, seat_count, service_fee_sen):
    base = fare_sen * seat_count
    fee = service_fee_sen * seat_count
    return {"seat_count": seat_count, "base_sen": base, "service_fee_sen": fee, "total_sen": base + fee}
