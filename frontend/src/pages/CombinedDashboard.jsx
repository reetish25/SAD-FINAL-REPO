import React, { useState } from 'react';
import {
  Sparkles, AlertTriangle, CheckCircle2, ShieldCheck, Activity,
  CloudSun, Sprout, Leaf, ArrowRight, RefreshCw, Info, Download,
  Layers, Thermometer, Droplets, Wind, ShieldAlert, Cpu
} from 'lucide-react';
import { api } from '../services/api';

export default function CombinedDashboard() {
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [fieldId, setFieldId] = useState('field-demo');
  const [plantLabel, setPlantLabel] = useState('Plot A - Main Sunflower Block');
  const [cropStage, setCropStage] = useState('flowering');
  const [lat, setLat] = useState('12.9716');
  const [lon, setLon] = useState('77.5946');
  const [pdi, setPdi] = useState('15.0');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [activeTab, setActiveTab] = useState('synthesis');

  const handleImageChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setImageFile(file);
      const reader = new FileReader();
      reader.onloadend = () => setImagePreview(reader.result);
      reader.readAsDataURL(file);
    }
  };

  const handleRunAssessment = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      if (imageFile) {
        formData.append('image', imageFile);
      }
      formData.append('field_id', fieldId);
      formData.append('plant_label', plantLabel);
      formData.append('crop_stage', cropStage);
      formData.append('latitude', lat);
      formData.append('longitude', lon);
      formData.append('pdi', pdi);

      const data = await api.submitCombinedAssessment(formData);
      setResult(data);
    } catch (err) {
      console.error('Combined assessment failed:', err);
      setError(err.detail || err.message || 'Combined assessment request failed.');
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'OPTIMAL_HEALTH':
        return <span className="px-3 py-1 bg-emerald-100 text-emerald-800 rounded-full text-xs font-semibold uppercase tracking-wider flex items-center gap-1.5"><ShieldCheck className="w-3.5 h-3.5 text-emerald-600" /> Optimal Health</span>;
      case 'MODERATE_VIGOR':
        return <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-xs font-semibold uppercase tracking-wider flex items-center gap-1.5"><Activity className="w-3.5 h-3.5 text-blue-600" /> Moderate Vigor</span>;
      case 'ELEVATED_RISK':
        return <span className="px-3 py-1 bg-amber-100 text-amber-800 rounded-full text-xs font-semibold uppercase tracking-wider flex items-center gap-1.5"><AlertTriangle className="w-3.5 h-3.5 text-amber-600" /> Elevated Risk</span>;
      default:
        return <span className="px-3 py-1 bg-rose-100 text-rose-800 rounded-full text-xs font-semibold uppercase tracking-wider flex items-center gap-1.5"><ShieldAlert className="w-3.5 h-3.5 text-rose-600" /> Critical Action Required</span>;
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header Banner */}
      <div className="bg-white border border-stone-200 rounded-2xl p-6 sm:p-8 shadow-sm relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-gradient-to-bl from-sunflower-light/20 via-pine-light/10 to-transparent rounded-full pointer-events-none -mr-20 -mt-20"></div>
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 relative z-10">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 bg-pine/10 text-pine rounded-full text-xs font-mono font-semibold uppercase tracking-wider mb-3">
              <Layers className="w-3.5 h-3.5" /> Mode B Cross-Service Orchestration
            </div>
            <h1 className="text-3xl font-heading font-bold text-pine">
              Combined Sunflower Crop-Health Assessment
            </h1>
            <p className="text-stone-600 text-sm mt-1 max-w-2xl">
              Simultaneously interrogates Plant Health (Foliar CNN), Environment & Weather (Microclimate & EDPS), and Soil & Nutrient (Rhizosphere Chemistry) to synthesize a unified diagnosis.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs font-mono bg-stone-100 border border-stone-200 text-stone-600 px-3 py-1.5 rounded-lg">
              Gateway Port: 8080
            </span>
          </div>
        </div>
      </div>

      {/* Main Grid: Input Form & Results */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Input Form (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          <form onSubmit={handleRunAssessment} className="bg-white border border-stone-200 rounded-2xl p-6 shadow-sm space-y-5">
            <h2 className="text-lg font-heading font-bold text-pine flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-amber-500" /> Assessment Parameters
            </h2>

            {/* Leaf Image Upload */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-stone-600 mb-2">
                Sunflower Foliage Photo (Optional)
              </label>
              <div className="border-2 border-dashed border-stone-200 hover:border-pine rounded-xl p-4 text-center cursor-pointer relative bg-stone-50/50 transition">
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={handleImageChange}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                />
                {imagePreview ? (
                  <div className="relative">
                    <img src={imagePreview} alt="Leaf Preview" className="h-44 mx-auto rounded-lg object-cover" />
                    <span className="text-xs text-pine font-medium mt-2 block">Click to change photo</span>
                  </div>
                ) : (
                  <div className="py-6">
                    <Leaf className="w-10 h-10 text-stone-400 mx-auto mb-2" />
                    <p className="text-sm font-medium text-stone-700">Drop leaf photo here or click to browse</p>
                    <p className="text-xs text-stone-500 mt-1">Triggers MobileNetV2 / EfficientNetB0 foliar inference</p>
                  </div>
                )}
              </div>
            </div>

            {/* Field ID & Label */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-stone-600 mb-1">Field ID</label>
                <input
                  type="text"
                  value={fieldId}
                  onChange={(e) => setFieldId(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg text-sm font-mono focus:ring-2 focus:ring-pine/20 focus:border-pine outline-none"
                  placeholder="field-demo"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-stone-600 mb-1">Crop Stage</label>
                <select
                  value={cropStage}
                  onChange={(e) => setCropStage(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg text-sm focus:ring-2 focus:ring-pine/20 focus:border-pine outline-none"
                >
                  <option value="seedling">Seedling</option>
                  <option value="vegetative">Vegetative</option>
                  <option value="budding">Budding / Star</option>
                  <option value="flowering">Flowering</option>
                  <option value="grain_filling">Grain Filling</option>
                  <option value="maturity">Maturity</option>
                </select>
              </div>
            </div>

            {/* Sector / Label */}
            <div>
              <label className="block text-xs font-semibold text-stone-600 mb-1">Sector / Plot Name</label>
              <input
                type="text"
                value={plantLabel}
                onChange={(e) => setPlantLabel(e.target.value)}
                className="w-full px-3 py-2 border border-stone-200 rounded-lg text-sm focus:ring-2 focus:ring-pine/20 focus:border-pine outline-none"
                placeholder="e.g. North Sector Block 4"
              />
            </div>

            {/* Coordinates */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-stone-600 mb-1">Latitude</label>
                <input
                  type="number"
                  step="0.0001"
                  value={lat}
                  onChange={(e) => setLat(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg text-sm font-mono focus:ring-2 focus:ring-pine/20 focus:border-pine outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-stone-600 mb-1">Longitude</label>
                <input
                  type="number"
                  step="0.0001"
                  value={lon}
                  onChange={(e) => setLon(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg text-sm font-mono focus:ring-2 focus:ring-pine/20 focus:border-pine outline-none"
                />
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3.5 px-4 bg-pine text-white hover:bg-pine-dark font-heading font-semibold rounded-xl shadow-md transition flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" /> Orchestrating 3 Microservices...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 text-sunflower" /> Run Multi-Service Assessment
                </>
              )}
            </button>
          </form>

          {/* Microservice Architecture Summary Card */}
          <div className="bg-stone-50 border border-stone-200 rounded-xl p-4 text-xs space-y-2 text-stone-600">
            <div className="font-semibold text-pine flex items-center gap-1.5">
              <Cpu className="w-4 h-4" /> Orchestration Routing Pipeline:
            </div>
            <p>1. <strong>Plant Health</strong> (:8000) - Runs PyTorch classification & CAM lesion segmentation.</p>
            <p>2. <strong>Weather Service</strong> (:8001) - Ingests Open-Meteo & computes EDPS disease risk.</p>
            <p>3. <strong>Soil Service</strong> (:8091) - Queries rhizosphere NPK & soil health balance.</p>
            <p>4. <strong>API Gateway</strong> (:8080) - Synthesizes results and handles partial outages.</p>
          </div>
        </div>

        {/* Right Column: Consolidated Results (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          {error && (
            <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-sm flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-rose-500 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Assessment Request Failed</p>
                <p className="text-xs mt-0.5">{error}</p>
              </div>
            </div>
          )}

          {!result && !loading && (
            <div className="bg-white border border-stone-200 rounded-2xl p-12 text-center text-stone-500">
              <Layers className="w-16 h-16 text-stone-300 mx-auto mb-4" />
              <h3 className="text-lg font-heading font-semibold text-stone-700">Ready for Multi-Service Synthesis</h3>
              <p className="text-sm text-stone-500 max-w-md mx-auto mt-1">
                Upload a leaf photo and submit parameters on the left to initiate Mode B cross-microservice evaluation.
              </p>
            </div>
          )}

          {result && (
            <div className="bg-white border border-stone-200 rounded-2xl p-6 sm:p-8 shadow-sm space-y-6">
              {/* Top Score & Verdict Bar */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-6 border-b border-stone-100 gap-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    {getStatusBadge(result.overall_status)}
                    {result.partial_result && (
                      <span className="px-2.5 py-0.5 bg-amber-100 text-amber-800 rounded-full text-xs font-mono">
                        Partial Result
                      </span>
                    )}
                  </div>
                  <h3 className="text-2xl font-heading font-bold text-pine">
                    {result.plant_label}
                  </h3>
                  <p className="text-xs font-mono text-stone-500 mt-0.5">
                    Assessment ID: {result.assessment_id} • Field: {result.field_id}
                  </p>
                </div>

                {/* Big Score Dial */}
                <div className="flex items-center gap-3 bg-stone-50 border border-stone-200 px-5 py-3 rounded-2xl">
                  <div className="text-right">
                    <span className="block text-[10px] uppercase font-bold text-stone-500 tracking-wider">
                      Health Index (SHI)
                    </span>
                    <span className="text-3xl font-heading font-extrabold text-pine">
                      {result.composite_health_index}%
                    </span>
                  </div>
                </div>
              </div>

              {/* Partial Result Warnings Alert */}
              {result.warnings && result.warnings.length > 0 && (
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-xs text-amber-900 space-y-1">
                  <div className="font-semibold flex items-center gap-1.5 text-amber-800">
                    <AlertTriangle className="w-4 h-4 text-amber-600" /> Graceful Degradation Notice:
                  </div>
                  {result.warnings.map((w, idx) => (
                    <p key={idx}>• {w}</p>
                  ))}
                </div>
              )}

              {/* Summary Verdict */}
              <div className="p-4 bg-stone-50 rounded-xl border border-stone-200 text-sm text-stone-800">
                <span className="font-semibold text-pine">Agronomic Verdict: </span>
                {result.summary_verdict}
              </div>

              {/* Domain Component Scores */}
              <div className="grid grid-cols-3 gap-3">
                <div className="bg-stone-50 border border-stone-200 rounded-xl p-3 text-center">
                  <span className="text-[10px] font-bold uppercase text-stone-500 block">Canopy Foliage</span>
                  <span className="text-lg font-heading font-bold text-pine">
                    {result.component_scores?.canopy_foliar_score !== null ? `${result.component_scores.canopy_foliar_score}%` : 'N/A'}
                  </span>
                </div>
                <div className="bg-stone-50 border border-stone-200 rounded-xl p-3 text-center">
                  <span className="text-[10px] font-bold uppercase text-stone-500 block">Microclimate</span>
                  <span className="text-lg font-heading font-bold text-pine">
                    {result.component_scores?.climate_resilience_score !== null ? `${result.component_scores.climate_resilience_score}%` : 'N/A'}
                  </span>
                </div>
                <div className="bg-stone-50 border border-stone-200 rounded-xl p-3 text-center">
                  <span className="text-[10px] font-bold uppercase text-stone-500 block">Rhizosphere Soil</span>
                  <span className="text-lg font-heading font-bold text-pine">
                    {result.component_scores?.soil_rhizosphere_score !== null ? `${result.component_scores.soil_rhizosphere_score}%` : 'N/A'}
                  </span>
                </div>
              </div>

              {/* Service Provenance Strip */}
              <div className="border border-stone-200 rounded-xl p-4 space-y-3 bg-stone-50/50">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-stone-600 flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" /> Microservice Data Provenance
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                  {/* Plant Health Badge */}
                  <div className="p-2.5 bg-white border border-stone-200 rounded-lg">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-stone-800">Plant Health</span>
                      <span className={`w-2 h-2 rounded-full ${result.services?.plant_health?.status === 'SUCCESS' ? 'bg-emerald-500' : 'bg-amber-500'}`}></span>
                    </div>
                    <span className="text-[11px] text-stone-500 block mt-0.5">
                      Latency: {result.services?.plant_health?.latency_ms || 0} ms
                    </span>
                    <span className="text-[11px] font-mono text-pine block">
                      {result.services?.plant_health?.data?.predicted_class || 'Online'}
                    </span>
                  </div>

                  {/* Weather Badge */}
                  <div className="p-2.5 bg-white border border-stone-200 rounded-lg">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-stone-800">Weather & Env</span>
                      <span className={`w-2 h-2 rounded-full ${result.services?.environment_weather?.status === 'SUCCESS' ? 'bg-emerald-500' : 'bg-amber-500'}`}></span>
                    </div>
                    <span className="text-[11px] text-stone-500 block mt-0.5">
                      Latency: {result.services?.environment_weather?.latency_ms || 0} ms
                    </span>
                    <span className="text-[11px] font-mono text-pine block">
                      {result.services?.environment_weather?.data?.temperature_c ? `${result.services.environment_weather.data.temperature_c}°C / ${result.services.environment_weather.data.humidity_pct}% RH` : 'Online'}
                    </span>
                  </div>

                  {/* Soil Badge */}
                  <div className="p-2.5 bg-white border border-stone-200 rounded-lg">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-stone-800">Soil & Nutrient</span>
                      <span className={`w-2 h-2 rounded-full ${result.services?.soil_nutrient?.status === 'SUCCESS' ? 'bg-emerald-500' : 'bg-amber-500'}`}></span>
                    </div>
                    <span className="text-[11px] text-stone-500 block mt-0.5">
                      Latency: {result.services?.soil_nutrient?.latency_ms || 0} ms
                    </span>
                    <span className="text-[11px] font-mono text-pine block">
                      {result.services?.soil_nutrient?.data?.health_status || 'Sample Pending'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Integrated Agronomic Recommendations */}
              <div className="space-y-3">
                <h4 className="text-sm font-heading font-bold text-pine flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" /> Integrated Agronomic Action Plan
                </h4>
                {result.integrated_recommendations && result.integrated_recommendations.length > 0 ? (
                  <div className="space-y-2">
                    {result.integrated_recommendations.map((rec, i) => (
                      <div
                        key={i}
                        className={`p-3.5 rounded-xl border text-xs flex items-start gap-3 ${
                          rec.urgency === 'Urgent'
                            ? 'bg-rose-50 border-rose-200 text-rose-900'
                            : rec.urgency === 'High'
                            ? 'bg-amber-50 border-amber-200 text-amber-900'
                            : 'bg-white border-stone-200 text-stone-800'
                        }`}
                      >
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider shrink-0 ${
                          rec.urgency === 'Urgent' ? 'bg-rose-200 text-rose-800' : rec.urgency === 'High' ? 'bg-amber-200 text-amber-800' : 'bg-stone-200 text-stone-700'
                        }`}>
                          {rec.source}
                        </span>
                        <div className="flex-1">
                          <p className="font-semibold">{rec.category}</p>
                          <p className="mt-0.5">{rec.action}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-stone-500">No corrective actions currently required for this plot.</p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
