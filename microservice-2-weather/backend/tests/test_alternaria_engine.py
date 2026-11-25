from app.services.alternaria_engine import calculate_day

def test_calculate_complete_day():
    result = calculate_day(tmax=30, tmin=20, humidity=75, rainfall=3, pdi=10, growth_stage='flowering')
    assert result['status'] == 'COMPLETE'
    assert result['temperature_mean_c'] == 25
    assert result['risk_category'] in {'LOW', 'MODERATE', 'HIGH', 'VERY HIGH'}
    assert 0 <= result['edps'] <= 100

def test_missing_input_is_incomplete():
    result = calculate_day(tmax=30, tmin=None, humidity=75, rainfall=3, pdi=10, growth_stage='flowering')
    assert result['status'] == 'INCOMPLETE_DATA'
