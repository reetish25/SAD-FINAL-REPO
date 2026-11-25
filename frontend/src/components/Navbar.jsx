import React from 'react';
import { useAuth } from '../context/AuthContext';
import {
  Leaf, Shield, User, LogOut, LayoutDashboard, History,
  ScanLine, CloudSun, Sprout, Layers, Home
} from 'lucide-react';

export default function Navbar({ activeView, setActiveView }) {
  const { user, isAdmin, logout } = useAuth();

  return (
    <header className="bg-pine text-paper shadow-md border-b border-pine-dark sticky top-0 z-40 no-print">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Platform Name */}
          <div
            className="flex items-center space-x-3 cursor-pointer group"
            onClick={() => setActiveView('hub')}
          >
            <div className="w-10 h-10 rounded-xl bg-moss flex items-center justify-center shadow-inner text-paper group-hover:scale-105 transition-transform duration-150">
              <Leaf className="w-6 h-6 transform -rotate-12" />
            </div>
            <div>
              <span className="font-heading font-extrabold text-2xl tracking-tight text-paper">
                Leafline
              </span>
              <span className="hidden sm:inline-block ml-2 text-[10px] font-mono tracking-wider uppercase px-2 py-0.5 rounded-full bg-pine-dark text-moss-light border border-moss/30 font-semibold">
                Sunflower Platform
              </span>
            </div>
          </div>

          {/* Navigation Links for 3 Independent Services + Mode B Combined */}
          <nav className="hidden md:flex items-center space-x-1">
            {/* Hub Overview */}
            <button
              onClick={() => setActiveView('hub')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-heading font-semibold transition-all duration-150 ${
                activeView === 'hub'
                  ? 'bg-moss text-paper shadow-sm'
                  : 'text-paper/80 hover:text-paper hover:bg-pine-light'
              }`}
            >
              <Home className="w-3.5 h-3.5" />
              <span>Hub</span>
            </button>

            {/* Service 1: Plant Health */}
            <button
              onClick={() => setActiveView('pipeline')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-heading font-semibold transition-all duration-150 ${
                activeView === 'pipeline'
                  ? 'bg-moss text-paper shadow-sm'
                  : 'text-paper/80 hover:text-paper hover:bg-pine-light'
              }`}
            >
              <ScanLine className="w-3.5 h-3.5" />
              <span>Plant Health</span>
            </button>

            {/* Service 2: Weather & Environment */}
            <button
              onClick={() => setActiveView('weather')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-heading font-semibold transition-all duration-150 ${
                activeView === 'weather'
                  ? 'bg-moss text-paper shadow-sm'
                  : 'text-paper/80 hover:text-paper hover:bg-pine-light'
              }`}
            >
              <CloudSun className="w-3.5 h-3.5" />
              <span>Weather</span>
            </button>

            {/* Service 3: Soil & Nutrient */}
            <button
              onClick={() => setActiveView('soil')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-heading font-semibold transition-all duration-150 ${
                activeView === 'soil'
                  ? 'bg-moss text-paper shadow-sm'
                  : 'text-paper/80 hover:text-paper hover:bg-pine-light'
              }`}
            >
              <Sprout className="w-3.5 h-3.5" />
              <span>Soil</span>
            </button>

            {/* Mode B: Combined Assessment */}
            <button
              onClick={() => setActiveView('combined')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-heading font-bold transition-all duration-150 ${
                activeView === 'combined'
                  ? 'bg-sunflower text-pine-dark shadow-sm'
                  : 'text-sunflower hover:bg-pine-light border border-sunflower/30'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Combined Mode B</span>
            </button>

            {/* Scan History View */}
            <button
              onClick={() => setActiveView('history')}
              className={`flex items-center space-x-1.5 px-2.5 py-1.5 rounded-xl text-xs font-heading font-semibold transition-all duration-150 ${
                activeView === 'history'
                  ? 'bg-moss text-paper shadow-sm'
                  : 'text-paper/80 hover:text-paper hover:bg-pine-light'
              }`}
            >
              <History className="w-3.5 h-3.5" />
              <span>History</span>
            </button>
          </nav>

          {/* Right Area: Admin Switcher, Profile, Logout */}
          <div className="flex items-center space-x-2">
            {/* Admin Switcher */}
            {isAdmin && (
              <button
                onClick={() => setActiveView(activeView.startsWith('admin-') ? 'hub' : 'admin-dashboard')}
                className={`flex items-center space-x-1 px-2.5 py-1.5 rounded-xl text-xs font-heading font-bold border transition-all duration-150 ${
                  activeView.startsWith('admin-')
                    ? 'bg-amber text-ink border-amber-light shadow-sm'
                    : 'border-amber/50 text-amber-light hover:bg-amber/15'
                }`}
              >
                <LayoutDashboard className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">{activeView.startsWith('admin-') ? 'Grower View' : 'Admin'}</span>
              </button>
            )}

            {/* Profile */}
            <button
              onClick={() => setActiveView('profile')}
              className={`p-1.5 rounded-xl text-xs transition ${
                activeView === 'profile'
                  ? 'bg-pine-dark text-paper border border-moss/40'
                  : 'text-paper/80 hover:text-paper hover:bg-pine-light'
              }`}
              title="Profile Settings"
            >
              <User className="w-4 h-4" />
            </button>

            {/* Role Badge */}
            <span className={`text-[10px] px-2.5 py-0.5 rounded-full font-mono uppercase font-bold tracking-wider ${
              isAdmin ? 'bg-deeprust text-paper' : 'bg-moss-dark text-paper'
            }`}>
              {user?.role || 'User'}
            </span>

            {/* Logout */}
            <button
              onClick={logout}
              className="p-1.5 text-paper/70 hover:text-rust-light hover:bg-pine-light rounded-xl transition"
              title="Sign Out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Subnav for 3 services */}
      <div className="md:hidden flex items-center justify-around py-2 px-2 bg-pine-dark border-t border-pine text-xs font-semibold overflow-x-auto">
        <button onClick={() => setActiveView('hub')} className={activeView === 'hub' ? 'text-sunflower' : 'text-paper/70'}>Hub</button>
        <button onClick={() => setActiveView('pipeline')} className={activeView === 'pipeline' ? 'text-sunflower' : 'text-paper/70'}>Plant</button>
        <button onClick={() => setActiveView('weather')} className={activeView === 'weather' ? 'text-sunflower' : 'text-paper/70'}>Weather</button>
        <button onClick={() => setActiveView('soil')} className={activeView === 'soil' ? 'text-sunflower' : 'text-paper/70'}>Soil</button>
        <button onClick={() => setActiveView('combined')} className={activeView === 'combined' ? 'text-sunflower' : 'text-paper/70'}>Combined</button>
        <button onClick={() => setActiveView('history')} className={activeView === 'history' ? 'text-sunflower' : 'text-paper/70'}>History</button>
      </div>
    </header>
  );
}
