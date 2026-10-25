from services.fare import calculate_total_fare


def test_fare_breakdown():
    result = calculate_total_fare(fare_sen=4500, seat_count=3, service_fee_sen=100)
    assert result == {"seat_count": 3, "base_sen": 13500, "service_fee_sen": 300, "total_sen": 13800}
