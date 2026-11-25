const API_BASE = '/api';

function getAuthHeaders() {
  const token = localStorage.getItem('leafline_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request(endpoint, options = {}) {
  const headers = {
    ...getAuthHeaders(),
    ...(options.headers || {}),
  };

  // If body is not FormData, set Content-Type JSON
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(options.body);
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const rawText = await response.text();
    let errorDetail = rawText || response.statusText || 'An unexpected error occurred';
    try {
      const data = JSON.parse(rawText);
      if (data && data.detail) {
        if (Array.isArray(data.detail)) {
          errorDetail = data.detail
            .map((item) => (typeof item === 'object' && item?.msg ? item.msg : String(item)))
            .join('; ');
        } else if (typeof data.detail === 'string') {
          errorDetail = data.detail;
        } else {
          errorDetail = JSON.stringify(data.detail);
        }
      } else if (data && data.message) {
        errorDetail = data.message;
      } else if (data) {
        errorDetail = JSON.stringify(data);
      }
    } catch {
      // Body was not JSON; rawText is preserved as errorDetail
    }
    const error = new Error(`HTTP ${response.status}: ${errorDetail}`);
    error.status = response.status;
    error.detail = errorDetail;
    throw error;
  }

  return response.json();
}

export const api = {
  // System Health
  getSystemHealth: () => request('/health'),

  // Auth
  login: (email, password) =>
    request('/plant/auth/login', {
      method: 'POST',
      body: { email, password },
    }),
  forgotPassword: (email) =>
    request('/plant/auth/forgot-password', {
      method: 'POST',
      body: { email },
    }),
  resetPassword: (token, newPassword) =>
    request('/plant/auth/reset-password', {
      method: 'POST',
      body: { token, new_password: newPassword },
    }),
  changePassword: (currentPassword, newPassword) =>
    request('/plant/auth/change-password', {
      method: 'POST',
      body: { current_password: currentPassword, new_password: newPassword },
    }),
  getMe: () => request('/plant/auth/me'),
  updateProfile: (payload) =>
    request('/plant/auth/profile', {
      method: 'PUT',
      body: payload,
    }),

  // Service 1: Plant Health Scans
  createScan: (formData) =>
    request('/plant/scans', {
      method: 'POST',
      body: formData,
    }),
  getMyScans: (plantLabel) => {
    const q = plantLabel ? `?plant_label=${encodeURIComponent(plantLabel)}` : '';
    return request(`/plant/scans/mine${q}`);
  },
  getScanDetails: (scanId) => request(`/plant/scans/${scanId}`),
  getModelsList: () => request('/plant/scans/models'),
  getPlatformSettings: () => request('/plant/scans/settings'),

  // Service 2: Environment & Weather
  getCurrentWeather: (lat = 12.9716, lon = 77.5946) =>
    request(`/weather/weather/current?latitude=${lat}&longitude=${lon}`),
  getWeatherForecast: (lat = 12.9716, lon = 77.5946, days = 7) =>
    request(`/weather/weather/forecast?latitude=${lat}&longitude=${lon}&days=${days}`),
  calculateDiseaseForecast: (payload) =>
    request('/weather/disease-forecast/calculate', {
      method: 'POST',
      body: payload,
    }),
  getGrowthStages: () => request('/weather/disease-forecast/growth-stages'),
  getSensors: () => request('/weather/sensors'),
  registerSensor: (payload) =>
    request('/weather/sensors/register', {
      method: 'POST',
      body: payload,
    }),
  submitSensorReading: (payload) =>
    request('/weather/sensor-data', {
      method: 'POST',
      body: payload,
    }),

  // Service 3: Soil & Nutrient
  getSoilHealth: (fieldId = 'field-demo') =>
    request(`/soil/soil-health?field_id=${encodeURIComponent(fieldId)}`),
  submitSoilSample: (payload) =>
    request('/soil/soil-measurements', {
      method: 'POST',
      body: payload,
    }),
  getSoilHistory: (fieldId = 'field-demo') =>
    request(`/soil/soil-history?field_id=${encodeURIComponent(fieldId)}`),

  // Mode B: Combined Crop Health Assessment
  submitCombinedAssessment: (formData) =>
    request('/combined/assess', {
      method: 'POST',
      body: formData,
    }),

  // Service 1: Admin
  admin: {
    getDashboardMetrics: () => request('/plant/admin/dashboard'),
    getSystemStatus: () => request('/plant/admin/status'),
    getReviewQueue: (status) => {
      const q = status ? `?status=${encodeURIComponent(status)}` : '';
      return request(`/plant/admin/review-queue${q}`);
    },
    actOnReviewItem: (reviewId, action, notes) =>
      request(`/plant/admin/review-queue/${reviewId}/action`, {
        method: 'POST',
        body: { action, notes },
      }),
    getSubmissions: (page = 1, limit = 20) =>
      request(`/plant/admin/submissions?page=${page}&limit=${limit}`),
    getPesticides: () => request('/plant/admin/pesticides'),
    createPesticide: (data) =>
      request('/plant/admin/pesticides', {
        method: 'POST',
        body: data,
      }),
    updatePesticide: (groupId, data) =>
      request(`/plant/admin/pesticides/${groupId}`, {
        method: 'PUT',
        body: data,
      }),
    deactivatePesticide: (groupId) =>
      request(`/plant/admin/pesticides/${groupId}`, {
        method: 'DELETE',
      }),
    getModels: () => request('/plant/admin/models'),
    setDefaultModel: (modelId) =>
      request(`/plant/admin/models/${modelId}/set-default`, {
        method: 'POST',
      }),
    getSettings: () => request('/plant/admin/settings'),
    updateSetting: (key, value) =>
      request(`/plant/admin/settings/${key}`, {
        method: 'PUT',
        body: { value },
      }),
    getUsers: () => request('/plant/admin/users'),
    createUser: (userData) =>
      request('/plant/admin/users', {
        method: 'POST',
        body: userData,
      }),
    updateUser: (userId, userData) =>
      request(`/plant/admin/users/${userId}`, {
        method: 'PUT',
        body: userData,
      }),
    deleteUser: (userId) =>
      request(`/plant/admin/users/${userId}`, {
        method: 'DELETE',
      }),
    getAuditLogs: (page = 1, limit = 50, action, email) => {
      let q = `?page=${page}&limit=${limit}`;
      if (action) q += `&action=${encodeURIComponent(action)}`;
      if (email) q += `&email=${encodeURIComponent(email)}`;
      return request(`/plant/admin/audit-logs${q}`);
    },
  },
};
