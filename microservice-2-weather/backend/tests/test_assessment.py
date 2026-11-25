def test_assessment_after_sensor_reading(client, token):
    headers={'Authorization':f'Bearer {token}'}
    registered=client.post('/api/admin/sensors',headers=headers,json={'deviceId':'assess-sensor','name':'Assessment sensor','fieldId':'field-demo'})
    key=registered.json()['sensorKey']
    submitted=client.post('/api/sensor-data',headers={'X-Sensor-Key':key},json={'deviceId':'assess-sensor','fieldId':'field-demo','temperatureC':27.5,'humidityPct':58})
    assert submitted.status_code==201
    result=client.get('/api/environmental-data?fieldId=field-demo',headers=headers)
    assert result.status_code==200
    assert result.json()['conditionLabel']=='DATA_AVAILABLE'
    assert result.json()['inputs']['temperature_c']==27.5
