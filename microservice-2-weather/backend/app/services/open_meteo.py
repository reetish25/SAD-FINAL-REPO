from datetime import datetime, timezone
from typing import Any
import httpx
from app.config import WEATHER_PROVIDER_TIMEOUT_SECONDS
URL='https://api.open-meteo.com/v1/forecast'
class WeatherProviderError(Exception): pass
async def _get(params:dict[str,Any])->dict[str,Any]:
    try:
        async with httpx.AsyncClient(timeout=WEATHER_PROVIDER_TIMEOUT_SECONDS) as client:
            response=await client.get(URL,params=params); response.raise_for_status(); data=response.json()
    except (httpx.HTTPError,ValueError) as exc: raise WeatherProviderError('Open-Meteo request failed') from exc
    if not isinstance(data,dict) or data.get('error'): raise WeatherProviderError('Invalid provider response')
    return data
def _time(value):
    dt=datetime.fromisoformat((value or '').replace('Z','+00:00')) if value else datetime.now(timezone.utc)
    if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(tzinfo=None)
async def fetch_current(lat,lon):
    p=await _get({'latitude':lat,'longitude':lon,'current':'temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m','temperature_unit':'celsius','wind_speed_unit':'kmh','precipitation_unit':'mm','timezone':'UTC'})
    c=p.get('current') or {}
    if not c: raise WeatherProviderError('Current conditions missing')
    return {'latitude':p.get('latitude',lat),'longitude':p.get('longitude',lon),'temperature_c':c.get('temperature_2m'),'humidity_pct':c.get('relative_humidity_2m'),'rainfall_mm':c.get('precipitation'),'wind_speed_kmh':c.get('wind_speed_10m'),'observed_at':_time(c.get('time')),'source':'open-meteo'}
async def fetch_forecast(lat,lon,days):
    p=await _get({'latitude':lat,'longitude':lon,'daily':'temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,relative_humidity_2m_mean','forecast_days':days,'temperature_unit':'celsius','wind_speed_unit':'kmh','precipitation_unit':'mm','timezone':'UTC'})
    d=p.get('daily') or {}; dates=d.get('time') or []
    if not dates: raise WeatherProviderError('Daily forecast missing')
    def at(k,i):
        a=d.get(k) or []; return a[i] if i<len(a) else None
    return [{'forecast_date':datetime.fromisoformat(day).date(),'temperature_max_c':at('temperature_2m_max',i),'temperature_min_c':at('temperature_2m_min',i),'rainfall_sum_mm':at('precipitation_sum',i),'rain_probability_max_pct':at('precipitation_probability_max',i),'wind_speed_max_kmh':at('wind_speed_10m_max',i),'humidity_mean_pct':at('relative_humidity_2m_mean',i)} for i,day in enumerate(dates)]
