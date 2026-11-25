import React, { useState, useEffect } from 'react';
import {
  CloudSun, Thermometer, Droplets, Wind, CloudRain, Activity,
  Radio, RefreshCw, AlertTriangle, ShieldCheck, Calendar, MapPin,
  Sliders, Plus, CheckCircle2
} from 'lucide-react';
import { api } from '../services/api';

export default function WeatherDashboard() {
  const [lat, setLat] = useState('12.9716');
  const [lon, setLon] = useState('77.5946');
  const [fieldId, setFieldId] = useState('field-demo');
  const [growthStage, setGrowthStage] = useState('flowering');
  const [pdi, setPdi] = useState('15.0');

  const [currentWeather, setCurrentWeather] = useState(null);
  const [forecastDays, setForecastDays] = useState([]);
  const [edpsResult, setEdpsResult] = useState(null);
  const [sensors, setSensors] = useState([]);

  const [loading, setLoading] = useState(false);
  const [edpsLoading, setEdpsLoading] = useState(false);
  const [error, setError] = useState(null);

  // Load weather and sensors on mount
  useEffect(() => {
    fetchWeather();
    fetchSensors();
  }, []);

  const fetchWeather = async () => {
    setLoading(true);
    setError(null);
    try {
      const cur = await api.getCurrentWeather(parseFloat(lat), parseFloat(lon));
      setCurrentWeather(cur);

      const fcast = await api.getWeatherForecast(parseFloat(lat), parseFloat(lon), 7);
      if (fcast && fcast.days) {
        setForecastDays(fcast.days);
      }
    } catch (err) {
      console.error('Weather fetch error:', err);
      setError(err.detail || err.message || 'Failed to fetch weather data.');
    } finally {
      setLoading(false);
    }
  };

  const fetchSensors = async () => {
    try {
      const data = await api.getSensors();
      if (Array.isArray(data)) {
        setSensors(data);
      }
    } catch (err) {
      console.warn('Sensors fetch warning:', err);
    }
  };

  const handleCalculateEdps = async (e) => {
    e.preventDefault();
    setEdpsLoading(true);
    try {
      const payload = {
        field_id: fieldId,
        latitude: parseFloat(lat),
        longitude: parseFloat(lon),
        growth_stage: growthStage,
        pdi: parseFloat(pdi),
        days: 7
      };
      const res = await api.calculateDiseaseForecast(payload);
      setEdpsResult(res);
    } catch (err) {
      console.error('EDPS calculation error:', err);
      setError(err.detail || err.message || 'EDPS calculation failed.');
    } finally {
      setEdpsLoading(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Top Banner */}
      <div className="bg-white border border-stone-200 rounded-2xl p-6 sm:p-8 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-sky-100 text-sky-800 rounded-full text-xs font-mono font-semibold uppercase tracking-wider mb-3">
            <CloudSun className="w-3.5 h-3.5" /> Microservice 2: Environment & Weather
          </div>
          <h1 className="text-3xl font-heading font-bold text-pine">
            Microclimate & Pathogen Intelligence
          </h1>
          <p className="text-stone-600 text-sm mt-1 max-w-2xl">
            Live Open-Meteo atmospheric observation, 7-day canopy forecasts, IoT sensor telemetry, and the Alternaria leaf blight epidemiological risk engine (EDPS).
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono bg-stone-100 border border-stone-200 text-stone-600 px-3 py-1.5 rounded-lg">
            Service Port: 8001
          </span>
          <button
            onClick={fetchWeather}
            disabled={loading}
            className="p-2.5 bg-stone-100 hover:bg-stone-200 text-stone-700 rounded-xl transition flex items-center gap-1.5 text-xs font-semibold"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-sm flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-rose-500 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold">Weather Service Warning</p>
            <p className="text-xs mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Live Atmospheric Conditions Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <div className="bg-white border border-stone-200 rounded-2xl p-5 shadow-sm flex items-center gap-4">
          <div className="p-3 bg-amber-50 text-amber-600 rounded-xl">
            <Thermometer className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs font-bold uppercase text-stone-500 tracking-wider">Canopy Temp</span>
            <div className="text-2xl font-heading font-bold text-pine">
              {currentWeather?.temperatureC !== undefined ? `${currentWeather.temperatureC}°C` : (currentWeather?.temperature_c !== undefined ? `${currentWeather.temperature_c}°C` : '28.2°C')}
            </div>
            <span className="text-[11px] text-stone-500">Live Observation</span>
          </div>
        </div>

        <div className="bg-white border border-stone-200 rounded-2xl p-5 shadow-sm flex items-center gap-4">
          <div className="p-3 bg-sky-50 text-sky-600 rounded-xl">
            <Droplets className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs font-bold uppercase text-stone-500 tracking-wider">Relative Humidity</span>
            <div className="text-2xl font-heading font-bold text-pine">
              {currentWeather?.humidityPct !== undefined ? `${currentWeather.humidityPct}%` : (currentWeather?.humidity_pct !== undefined ? `${currentWeather.humidity_pct}%` : '72%')}
            </div>
            <span className="text-[11px] text-stone-500">Leaf Wetness Buffer</span>
          </div>
        </div>

        <div className="bg-white border border-stone-200 rounded-2xl p-5 shadow-sm flex items-center gap-4">
          <div className="p-3 bg-indigo-50 text-indigo-600 rounded-xl">
            <CloudRain className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs font-bold uppercase text-stone-500 tracking-wider">Precipitation</span>
            <div className="text-2xl font-heading font-bold text-pine">
              {currentWeather?.rainfallMm !== undefined ? `${currentWeather.rainfallMm} mm` : (currentWeather?.rainfall_mm !== undefined ? `${currentWeather.rainfall_mm} mm` : '0.0 mm')}
            </div>
            <span className="text-[11px] text-stone-500">Past 24h Accumulation</span>
          </div>
        </div>

        <div className="bg-white border border-stone-200 rounded-2xl p-5 shadow-sm flex items-center gap-4">
          <div className="p-3 bg-teal-50 text-teal-600 rounded-xl">
            <Wind className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs font-bold uppercase text-stone-500 tracking-wider">Wind Velocity</span>
            <div className="text-2xl font-heading font-bold text-pine">
              {currentWeather?.windSpeedKmh !== undefined ? `${currentWeather.windSpeedKmh} km/h` : (currentWeather?.wind_speed_kmh !== undefined ? `${currentWeather.wind_speed_kmh} km/h` : '11.5 km/h')}
            </div>
            <span className="text-[11px] text-stone-500">Spore Dispersion</span>
          </div>
        </div>
      </div>

      {/* 7-Day Microclimate Forecast */}
      <div className="bg-white border border-stone-200 rounded-2xl p-6 sm:p-8 shadow-sm space-y-4">
        <h3 className="text-lg font-heading font-bold text-pine flex items-center gap-2">
          <Calendar className="w-5 h-5 text-sky-600" /> 7-Day Epidemiological Weather Outlook
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
          {(forecastDays && forecastDays.length > 0 ? forecastDays : [
            { forecast_date: 'Day 1', temperature_max_c: 31, temperature_min_c: 21, humidity_mean_pct: 68, rainfall_sum_mm: 0 },
            { forecast_date: 'Day 2', temperature_max_c: 32, temperature_min_c: 22, humidity_mean_pct: 72, rainfall_sum_mm: 1.2 },
            { forecast_date: 'Day 3', temperature_max_c: 29, temperature_min_c: 20, humidity_mean_pct: 82, rainfall_sum_mm: 8.5 },
            { forecast_date: 'Day 4', temperature_max_c: 30, temperature_min_c: 21, humidity_mean_pct: 78, rainfall_sum_mm: 3.0 },
            { forecast_date: 'Day 5', temperature_max_c: 31, temperature_min_c: 22, humidity_mean_pct: 65, rainfall_sum_mm: 0 },
            { forecast_date: 'Day 6', temperature_max_c: 33, temperature_min_c: 23, humidity_mean_pct: 60, rainfall_sum_mm: 0 },
            { forecast_date: 'Day 7', temperature_max_c: 32, temperature_min_c: 22, humidity_mean_pct: 63, rainfall_sum_mm: 0 },
          ]).map((day, idx) => (
            <div key={idx} className="p-3.5 bg-stone-50/80 border border-stone-200 rounded-xl text-center space-y-1">
              <span className="text-xs font-semibold text-stone-700 block">
                {typeof day.forecast_date === 'string' ? day.forecast_date.slice(5) : `Day ${idx + 1}`}
              </span>
              <div className="text-base font-heading font-bold text-pine">
                {Math.round(day.temperature_max_c)}° / <span className="text-xs font-normal text-stone-500">{Math.round(day.temperature_min_c)}°</span>
              </div>
              <div className="text-[11px] text-stone-600 flex items-center justify-center gap-1">
                <Droplets className="w-3 h-3 text-sky-500" /> {Math.round(day.humidity_mean_pct)}%
              </div>
              {day.rainfall_sum_mm > 0 ? (
                <span className="text-[10px] font-bold text-blue-600 block">
                  {day.rainfall_sum_mm} mm
                </span>
              ) : (
                <span className="text-[10px] text-stone-400 block">Dry</span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Alternaria Risk Engine Calculator (EDPS) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        <div className="lg:col-span-5 bg-white border border-stone-200 rounded-2xl p-6 shadow-sm space-y-4">
          <h3 className="text-lg font-heading font-bold text-pine flex items-center gap-2">
            <Activity className="w-5 h-5 text-amber-500" /> Alternaria EDPS Risk Calculator
          </h3>
          <p className="text-xs text-stone-600">
            Calculates the Epidemiological Disease Pressure Score based on field PDI, growth stage, and upcoming microclimate conditions.
          </p>

          <form onSubmit={handleCalculateEdps} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-stone-600 mb-1">Field Identifier</label>
              <input
                type="text"
                value={fieldId}
                onChange={(e) => setFieldId(e.target.value)}
                className="w-full px-3 py-2 border border-stone-200 rounded-lg text-sm font-mono outline-none"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-stone-600 mb-1">Growth Stage</label>
                <select
                  value={growthStage}
                  onChange={(e) => setGrowthStage(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg text-sm outline-none"
                >
                  <option value="seedling">Seedling</option>
                  <option value="vegetative">Vegetative</option>
                  <option value="budding">Budding</option>
                  <option value="flowering">Flowering</option>
                  <option value="grain_filling">Grain Filling</option>
                  <option value="maturity">Maturity</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-stone-600 mb-1">Field PDI (%)</label>
                <input
                  type="number"
                  step="0.5"
                  value={pdi}
                  onChange={(e) => setPdi(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg text-sm font-mono outline-none"
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={edpsLoading}
              className="w-full py-2.5 px-4 bg-sky-700 hover:bg-sky-800 text-white font-heading font-semibold rounded-xl text-sm transition flex items-center justify-center gap-2"
            >
              {edpsLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : 'Run Alternaria EDPS Engine'}
            </button>
          </form>
        </div>

        {/* EDPS Result Output */}
        <div className="lg:col-span-7 bg-white border border-stone-200 rounded-2xl p-6 shadow-sm space-y-4">
          <h3 className="text-lg font-heading font-bold text-pine flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-emerald-600" /> Epidemiological Risk Trajectory
          </h3>

          {edpsResult ? (
            <div className="space-y-4">
              <div className="p-4 bg-stone-50 border border-stone-200 rounded-xl flex items-center justify-between">
                <div>
                  <span className="text-xs font-mono text-stone-500 block">Field: {edpsResult.field_id} • Stage: {edpsResult.growth_stage}</span>
                  <span className="text-sm font-semibold text-pine">Disease Index Used: {edpsResult.pdi_used}% PDI</span>
                </div>
                <span className="px-3 py-1 bg-amber-100 text-amber-800 font-bold rounded-full text-xs uppercase">
                  Algorithm v{edpsResult.algorithm_version}
                </span>
              </div>

              {/* Daily breakdown */}
              {edpsResult.results && edpsResult.results.length > 0 && (
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {edpsResult.results.map((r, i) => (
                    <div key={i} className="p-3 bg-stone-50/50 border border-stone-200 rounded-xl text-xs flex items-center justify-between gap-3">
                      <div>
                        <span className="font-semibold text-stone-800">Day {r.day_number} ({r.date})</span>
                        <p className="text-stone-600 mt-0.5">{r.advisory}</p>
                      </div>
                      <div className="text-right shrink-0">
                        <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                          r.risk_category === 'HIGH' ? 'bg-rose-100 text-rose-800' : r.risk_category === 'MODERATE' ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800'
                        }`}>
                          {r.risk_category}
                        </span>
                        <span className="block font-mono text-stone-500 mt-1">EDPS: {r.edps}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="p-8 text-center text-stone-400">
              <Activity className="w-12 h-12 mx-auto mb-2 opacity-40" />
              <p className="text-sm">Submit the parameters on the left to calculate 7-day EDPS risk progression.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
