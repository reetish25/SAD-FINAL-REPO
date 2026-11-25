import React, { useState, useEffect } from 'react';
import { useAuth, AuthProvider } from './context/AuthContext';
import { api } from './services/api';
import Navbar from './components/Navbar';
import StatusStrip from './components/StatusStrip';
import AdminSidebar from './components/AdminSidebar';
import ForceChangePasswordModal from './components/ForceChangePasswordModal';

// Pages
import Login from './pages/Login';
import HubOverview from './pages/HubOverview';
import UserPipeline from './pages/UserPipeline';
import WeatherDashboard from './pages/WeatherDashboard';
import SoilDashboard from './pages/SoilDashboard';
import CombinedDashboard from './pages/CombinedDashboard';
import UserHistory from './pages/UserHistory';
import UserProfile from './pages/UserProfile';

// Admin Pages
import AdminDashboard from './pages/admin/AdminDashboard';
import ReviewQueue from './pages/admin/ReviewQueue';
import Submissions from './pages/admin/Submissions';
import PesticideTable from './pages/admin/PesticideTable';
import ModelRegistry from './pages/admin/ModelRegistry';
import SystemSettings from './pages/admin/SystemSettings';
import UserManagement from './pages/admin/UserManagement';
import AuditLogs from './pages/admin/AuditLogs';

function MainApp() {
  const { user, isAuthenticated, loading, isAdmin } = useAuth();
  const [activeView, setActiveView] = useState('hub');
  const [adminTab, setAdminTab] = useState('dashboard');

  // Admin system status & pending review queue count
  const [systemStatus, setSystemStatus] = useState(null);

  useEffect(() => {
    if (isAdmin) {
      async function pollStatus() {
        try {
          const status = await api.admin.getSystemStatus();
          setSystemStatus(status);
        } catch (err) {
          console.warn('Could not fetch admin status:', err);
        }
      }
      pollStatus();
      const interval = setInterval(pollStatus, 15000); // 15s heartbeat
      return () => clearInterval(interval);
    }
  }, [isAdmin]);

  // Set default view on login
  useEffect(() => {
    if (isAuthenticated) {
      if (isAdmin && activeView === 'hub') {
        // Admin stays on hub or admin-dashboard
      }
    }
  }, [isAuthenticated, isAdmin]);

  if (loading) {
    return (
      <div className="min-h-screen bg-paper flex items-center justify-center font-mono text-sm text-pine">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-4 border-pine border-t-transparent rounded-full animate-spin"></div>
          <span className="font-heading font-semibold">Initializing Leafline Agronomics Platform...</span>
        </div>
      </div>
    );
  }

  // Unauthenticated screen: strictly Login only
  if (!isAuthenticated) {
    return <Login />;
  }

  const isAdminView = activeView.startsWith('admin-');

  return (
    <div className="min-h-screen bg-paper flex flex-col font-body selection:bg-pine selection:text-paper">
      {/* Forced Password Change Modal for provisioned accounts */}
      <ForceChangePasswordModal />

      {/* Navigation Header */}
      <Navbar activeView={activeView} setActiveView={setActiveView} />

      {/* Admin Experience: Top Status Strip + Sidebar Dashboard Shell */}
      {isAdmin && isAdminView ? (
        <div className="flex-1 flex flex-col">
          {/* Real-time System Status Strip */}
          <StatusStrip systemStatus={systemStatus} />

          <div className="flex-1 flex flex-col lg:flex-row max-w-7xl w-full mx-auto">
            {/* Sidebar Navigation Shell */}
            <AdminSidebar
              activeTab={adminTab}
              setActiveTab={setAdminTab}
              pendingReviewsCount={systemStatus?.pending_reviews || 0}
            />

            {/* Admin Content Area */}
            <main className="flex-1 p-6 sm:p-8 overflow-y-auto">
              {adminTab === 'dashboard' && (
                <AdminDashboard onNavigateToQueue={() => setAdminTab('review-queue')} />
              )}
              {adminTab === 'review-queue' && <ReviewQueue />}
              {adminTab === 'submissions' && <Submissions />}
              {adminTab === 'pesticides' && <PesticideTable />}
              {adminTab === 'models' && <ModelRegistry />}
              {adminTab === 'settings' && <SystemSettings />}
              {adminTab === 'users' && <UserManagement />}
              {adminTab === 'audit-logs' && <AuditLogs />}
            </main>
          </div>
        </div>
      ) : (
        /* Operational Experience: Hub, 3 Microservices & Combined Mode B */
        <main className="flex-1">
          {activeView === 'hub' && <HubOverview setActiveView={setActiveView} />}
          {activeView === 'pipeline' && <UserPipeline />}
          {activeView === 'weather' && <WeatherDashboard />}
          {activeView === 'soil' && <SoilDashboard />}
          {activeView === 'combined' && <CombinedDashboard />}
          {activeView === 'history' && <UserHistory />}
          {activeView === 'profile' && <UserProfile />}
        </main>
      )}

      {/* Footer */}
      <footer className="bg-pine-dark text-paper/70 py-6 border-t border-pine text-xs text-center no-print">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>Leafline AI-Powered Sunflower Health Monitoring Platform</span>
          <div className="flex items-center gap-4 text-paper/50 font-mono text-[11px]">
            <span>Plant Health :8000</span>
            <span>Weather :8001</span>
            <span>Soil :8091</span>
            <span>Gateway :8080</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <MainApp />
    </AuthProvider>
  );
}
