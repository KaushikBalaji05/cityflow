'use client';

import React, { useState, useEffect, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { Journey, Location, RoutingObjective, StopItem, TransportMode } from '@/types/journey';
import { planJourney, fetchHealth, fetchStops } from '@/lib/api';

// Dynamically import Map component to avoid SSR window issues
const Map = dynamic(() => import('@/components/Map'), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full bg-slate-900 border border-slate-800 rounded-3xl flex items-center justify-center text-slate-500 text-sm animate-pulse">
      Loading Bengaluru Transit Map...
    </div>
  ),
});

const PRESETS = [
  {
    name: 'Indiranagar ➔ Whitefield (Tech Hub)',
    origin: { lat: 12.9784, lon: 77.6408, name: 'Indiranagar Metro Station' },
    dest: { lat: 12.9698, lon: 77.7499, name: 'Whitefield (Kadugodi) Metro' },
  },
  {
    name: 'Majestic KBS ➔ Central Silk Board',
    origin: { lat: 12.9772, lon: 77.5713, name: 'Kempegowda Bus Station (Majestic)' },
    dest: { lat: 12.9172, lon: 77.6227, name: 'Central Silk Board Interchange' },
  },
  {
    name: 'Hebbal Flyover ➔ Bellandur EcoSpace',
    origin: { lat: 13.0358, lon: 77.5970, name: 'Hebbal Flyover Bus Station' },
    dest: { lat: 12.9260, lon: 77.6845, name: 'Bellandur Ecospace' },
  },
  {
    name: 'Banashankari ➔ MG Road (Metro Transfer)',
    origin: { lat: 12.9155, lon: 77.5736, name: 'Banashankari Metro Station' },
    dest: { lat: 12.9755, lon: 77.6066, name: 'MG Road Metro Station' },
  },
];

export default function HomePage() {
  const [origin, setOrigin] = useState<Location>(PRESETS[0].origin);
  const [destination, setDestination] = useState<Location>(PRESETS[0].dest);
  const [originQuery, setOriginQuery] = useState(PRESETS[0].origin.name || '');
  const [destQuery, setDestQuery] = useState(PRESETS[0].dest.name || '');

  const [allowedModes, setAllowedModes] = useState<TransportMode[]>(['metro', 'bus', 'walk', 'drive']);
  const [objective, setObjective] = useState<RoutingObjective>('fastest');
  const [journeys, setJourneys] = useState<Journey[]>([]);
  const [selectedJourneyIndex, setSelectedJourneyIndex] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [stops, setStops] = useState<StopItem[]>([]);
  const [apiHealth, setApiHealth] = useState<any>(null);
  const [pickingMode, setPickingMode] = useState<'origin' | 'destination' | null>(null);

  // Suggestions state
  const [showOriginSuggestions, setShowOriginSuggestions] = useState(false);
  const [showDestSuggestions, setShowDestSuggestions] = useState(false);

  // Load health & stops on mount
  useEffect(() => {
    fetchHealth()
      .then(setApiHealth)
      .catch(() => setApiHealth({ status: 'offline' }));

    fetchStops()
      .then(setStops)
      .catch((err) => console.error('Failed to load stops:', err));
  }, []);

  // Compute suggestions
  const originSuggestions = useMemo(() => {
    if (!originQuery.trim()) return stops.slice(0, 6);
    const q = originQuery.toLowerCase();
    return stops.filter((s) => s.name.toLowerCase().includes(q) || (s.line && s.line.toLowerCase().includes(q))).slice(0, 6);
  }, [originQuery, stops]);

  const destSuggestions = useMemo(() => {
    if (!destQuery.trim()) return stops.slice(0, 6);
    const q = destQuery.toLowerCase();
    return stops.filter((s) => s.name.toLowerCase().includes(q) || (s.line && s.line.toLowerCase().includes(q))).slice(0, 6);
  }, [destQuery, stops]);

  // Initial search
  useEffect(() => {
    handleSearch();
  }, [objective]);

  const handleSearch = async () => {
    if (!origin || !destination) {
      setError('Please select both Origin and Destination');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await planJourney({
        origin,
        destination,
        allowed_modes: allowedModes,
        objective,
      });
      setJourneys(res.journeys);
      setSelectedJourneyIndex(0);
    } catch (err: any) {
      setError(err.message || 'Routing computation failed');
    } finally {
      setLoading(false);
    }
  };

  const toggleMode = (mode: TransportMode) => {
    setAllowedModes((prev) => {
      const next = prev.includes(mode) ? prev.filter((m) => m !== mode) : [...prev, mode];
      return next.length > 0 ? next : [mode]; // Keep at least one mode
    });
  };

  const handleCoordinateSelected = (loc: Location, type: 'origin' | 'destination') => {
    if (type === 'origin') {
      setOrigin(loc);
      setOriginQuery(loc.name || `(${loc.lat}, ${loc.lon})`);
      setPickingMode(null);
    } else {
      setDestination(loc);
      setDestQuery(loc.name || `(${loc.lat}, ${loc.lon})`);
      setPickingMode(null);
    }
  };

  const applyPreset = (preset: typeof PRESETS[0]) => {
    setOrigin(preset.origin);
    setOriginQuery(preset.origin.name);
    setDestination(preset.dest);
    setDestQuery(preset.dest.name);
    setShowOriginSuggestions(false);
    setShowDestSuggestions(false);
    // trigger auto search
    setTimeout(handleSearch, 100);
  };

  const activeJourney = journeys[selectedJourneyIndex] || null;

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-slate-950 text-slate-100">
      {/* Top Navbar */}
      <header className="h-16 border-b border-slate-800 bg-slate-900/80 backdrop-blur-md px-6 flex items-center justify-between z-30 shrink-0">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-emerald-400 flex items-center justify-center font-black text-xl shadow-lg shadow-indigo-500/25 text-white">
            CF
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-lg font-bold tracking-tight text-white">CityFlow</span>
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 uppercase tracking-wider">
                Bengaluru Transit
              </span>
            </div>
            <p className="text-xs text-slate-400">Multimodal Journey Planner & Mobility Intelligence</p>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-slate-800/80 border border-slate-700/80 text-slate-300">
            <span
              className={`w-2 h-2 mr-2 rounded-full ${
                apiHealth?.status === 'healthy' ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
              }`}
            />
            {apiHealth?.status === 'healthy'
              ? `Graph Ready (${apiHealth.transit_graph.total_stops} Stops)`
              : 'Connecting Backend...'}
          </span>
          <a
            href="http://localhost:8000/api/v1/docs"
            target="_blank"
            rel="noreferrer"
            className="text-xs font-medium text-slate-400 hover:text-white transition px-3 py-1.5 rounded-lg hover:bg-slate-800"
          >
            API Docs
          </a>
          <a
            href="https://github.com/KaushikBalaji05/cityflow"
            target="_blank"
            rel="noreferrer"
            className="text-xs font-medium text-slate-400 hover:text-white transition px-3 py-1.5 rounded-lg hover:bg-slate-800"
          >
            GitHub
          </a>
        </div>
      </header>

      {/* Main Workspace: Left Controls (Scrollable) | Right Map (Fixed) */}
      <div className="flex-1 flex flex-col lg:flex-row overflow-hidden relative">
        {/* Left Side: Journey Planner Panel */}
        <aside className="w-full lg:w-[480px] bg-slate-950 border-r border-slate-800 flex flex-col h-[55vh] lg:h-full overflow-y-auto p-5 space-y-5 z-20 shrink-0">
          {/* Quick Presets Carousel */}
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-2">
              Popular Bengaluru Commutes
            </div>
            <div className="flex space-x-2 overflow-x-auto pb-1 text-xs">
              {PRESETS.map((p, idx) => (
                <button
                  key={idx}
                  onClick={() => applyPreset(p)}
                  className="px-3 py-1.5 bg-slate-900 border border-slate-800 hover:border-indigo-500/50 rounded-xl whitespace-nowrap text-slate-300 hover:text-white transition text-[11px] font-medium"
                >
                  {p.name}
                </button>
              ))}
            </div>
          </div>

          {/* Form Card */}
          <div className="bg-slate-900/90 border border-slate-800/90 rounded-3xl p-5 shadow-xl space-y-4">
            {/* Origin Input */}
            <div className="relative space-y-1">
              <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
                <span className="flex items-center space-x-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 inline-block shadow-sm shadow-emerald-400/50" />
                  <span>Origin Location</span>
                </span>
                <button
                  type="button"
                  onClick={() => setPickingMode(pickingMode === 'origin' ? null : 'origin')}
                  className={`text-[11px] px-2 py-0.5 rounded-md border transition ${
                    pickingMode === 'origin'
                      ? 'bg-emerald-500/20 border-emerald-500 text-emerald-300'
                      : 'border-slate-700 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  📍 Pick on Map
                </button>
              </label>

              <input
                type="text"
                value={originQuery}
                onChange={(e) => {
                  setOriginQuery(e.target.value);
                  setShowOriginSuggestions(true);
                }}
                onFocus={() => setShowOriginSuggestions(true)}
                placeholder="Search Metro station or bus stop..."
                className="w-full bg-slate-800/90 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition shadow-inner"
              />

              {showOriginSuggestions && (
                <div className="absolute left-0 right-0 top-full mt-1.5 bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl z-40 max-h-52 overflow-y-auto divide-y divide-slate-800">
                  {originSuggestions.map((s) => (
                    <div
                      key={s.id}
                      onClick={() => {
                        setOrigin({ lat: s.lat, lon: s.lon, name: s.name });
                        setOriginQuery(s.name);
                        setShowOriginSuggestions(false);
                      }}
                      className="px-3.5 py-2.5 hover:bg-slate-800 cursor-pointer flex items-center justify-between text-xs transition"
                    >
                      <div>
                        <div className="font-semibold text-slate-200">{s.name}</div>
                        <div className="text-[10px] text-slate-400">{s.mode.toUpperCase()} · {s.line || 'Corridor'}</div>
                      </div>
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 border border-slate-700 text-slate-400">Select</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Destination Input */}
            <div className="relative space-y-1">
              <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
                <span className="flex items-center space-x-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-rose-400 inline-block shadow-sm shadow-rose-400/50" />
                  <span>Destination Location</span>
                </span>
                <button
                  type="button"
                  onClick={() => setPickingMode(pickingMode === 'destination' ? null : 'destination')}
                  className={`text-[11px] px-2 py-0.5 rounded-md border transition ${
                    pickingMode === 'destination'
                      ? 'bg-rose-500/20 border-rose-500 text-rose-300'
                      : 'border-slate-700 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  📍 Pick on Map
                </button>
              </label>

              <input
                type="text"
                value={destQuery}
                onChange={(e) => {
                  setDestQuery(e.target.value);
                  setShowDestSuggestions(true);
                }}
                onFocus={() => setShowDestSuggestions(true)}
                placeholder="Search Metro station or bus stop..."
                className="w-full bg-slate-800/90 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition shadow-inner"
              />

              {showDestSuggestions && (
                <div className="absolute left-0 right-0 top-full mt-1.5 bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl z-40 max-h-52 overflow-y-auto divide-y divide-slate-800">
                  {destSuggestions.map((s) => (
                    <div
                      key={s.id}
                      onClick={() => {
                        setDestination({ lat: s.lat, lon: s.lon, name: s.name });
                        setDestQuery(s.name);
                        setShowDestSuggestions(false);
                      }}
                      className="px-3.5 py-2.5 hover:bg-slate-800 cursor-pointer flex items-center justify-between text-xs transition"
                    >
                      <div>
                        <div className="font-semibold text-slate-200">{s.name}</div>
                        <div className="text-[10px] text-slate-400">{s.mode.toUpperCase()} · {s.line || 'Corridor'}</div>
                      </div>
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 border border-slate-700 text-slate-400">Select</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Transport Modes Pills */}
            <div className="space-y-1.5 pt-1">
              <label className="text-xs font-semibold text-slate-400">Active Modes</label>
              <div className="grid grid-cols-4 gap-2">
                {[
                  { mode: 'metro', label: '🚇 Metro', bg: 'border-purple-500/50 bg-purple-500/15 text-purple-300' },
                  { mode: 'bus', label: '🚌 BMTC', bg: 'border-blue-500/50 bg-blue-500/15 text-blue-300' },
                  { mode: 'walk', label: '🚶 Walk', bg: 'border-slate-500/50 bg-slate-500/15 text-slate-200' },
                  { mode: 'drive', label: '🚗 Cab/Auto', bg: 'border-amber-500/50 bg-amber-500/15 text-amber-300' },
                ].map((item) => {
                  const isActive = allowedModes.includes(item.mode as TransportMode);
                  return (
                    <button
                      key={item.mode}
                      type="button"
                      onClick={() => toggleMode(item.mode as TransportMode)}
                      className={`py-2 px-1 text-xs font-semibold rounded-xl border transition shadow-sm ${
                        isActive
                          ? item.bg
                          : 'bg-slate-800/40 border-slate-800 text-slate-500 hover:text-slate-300'
                      }`}
                    >
                      {item.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Objective Selector */}
            <div className="space-y-1.5 pt-1">
              <label className="text-xs font-semibold text-slate-400">Optimization Goal</label>
              <div className="grid grid-cols-3 gap-1.5 text-[11px]">
                {[
                  { id: 'fastest', label: '⚡ Fastest' },
                  { id: 'lowest_cost', label: '💰 Lowest Fare' },
                  { id: 'least_walking', label: '🚶 Min Walk' },
                  { id: 'fewest_transfers', label: '🔄 0-1 Transfer' },
                  { id: 'balanced', label: '⚖️ Balanced' },
                ].map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setObjective(item.id as RoutingObjective)}
                    className={`py-1.5 px-2 rounded-lg font-medium border text-center transition ${
                      objective === item.id
                        ? 'bg-indigo-600 border-indigo-500 text-white shadow-md shadow-indigo-600/30'
                        : 'bg-slate-800/60 border-slate-700/60 text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Submit Button */}
            <button
              onClick={handleSearch}
              disabled={loading}
              className="w-full bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white font-bold py-3 px-4 rounded-2xl text-sm transition shadow-lg shadow-indigo-600/30 disabled:opacity-50 flex items-center justify-center space-x-2"
            >
              {loading ? (
                <span>Finding Best Multimodal Journeys...</span>
              ) : (
                <span>Compute Routes ({journeys.length} Options)</span>
              )}
            </button>
          </div>

          {/* Journey Results Header */}
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs text-slate-400 font-semibold px-1">
              <span>CANDIDATE JOURNEYS</span>
              <span>{journeys.length} Feasible Paths</span>
            </div>

            {error && (
              <div className="p-4 rounded-2xl bg-rose-950/70 border border-rose-800 text-xs text-rose-300">
                {error}
              </div>
            )}

            {/* Journey Cards */}
            {journeys.map((journey, idx) => {
              const isSelected = selectedJourneyIndex === idx;
              const durMin = Math.round(journey.total_duration_sec / 60);
              const walkKm = (journey.total_walking_distance_meters / 1000).toFixed(2);
              const fare = journey.estimated_fare_inr;

              return (
                <div
                  key={journey.journey_id || idx}
                  onClick={() => setSelectedJourneyIndex(idx)}
                  className={`p-4 rounded-3xl border transition cursor-pointer space-y-3 shadow-xl ${
                    isSelected
                      ? 'bg-slate-900 border-indigo-500 ring-1 ring-indigo-500/50 shadow-indigo-500/10'
                      : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span className="text-xl font-black text-white">{durMin} min</span>
                      {idx === 0 && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                          Recommended
                        </span>
                      )}
                    </div>
                    <span className="text-base font-bold text-emerald-400">₹{fare.toFixed(0)}</span>
                  </div>

                  <div className="text-xs font-semibold text-slate-200">{journey.summary}</div>

                  {/* Badges metrics */}
                  <div className="flex items-center space-x-3 text-[11px] text-slate-400 border-y border-slate-800/80 py-2">
                    <div className="flex items-center space-x-1">
                      <span>🚶</span>
                      <span>{walkKm} km</span>
                    </div>
                    <div className="flex items-center space-x-1">
                      <span>🔄</span>
                      <span>{journey.total_transfers} transfers</span>
                    </div>
                    <div className="flex items-center space-x-1">
                      <span>⏳</span>
                      <span>{Math.round(journey.total_waiting_time_sec / 60)}m wait</span>
                    </div>
                  </div>

                  {/* Step by step legs */}
                  <div className="space-y-2 pt-1 text-xs">
                    {journey.legs.map((leg, lIdx) => (
                      <div key={lIdx} className="flex items-start space-x-2.5">
                        <span className="mt-0.5 text-sm">
                          {leg.mode === 'metro' ? '🚇' : leg.mode === 'bus' ? '🚌' : leg.mode === 'drive' ? '🚗' : '🚶'}
                        </span>
                        <div className="flex-1">
                          <div className="font-semibold text-slate-200">{leg.route_name}</div>
                          <div className="text-[11px] text-slate-400">
                            {leg.from_stop_name} → {leg.to_stop_name}
                          </div>
                          <div className="text-[10px] text-slate-500 flex items-center space-x-2 mt-0.5">
                            <span>{Math.round(leg.duration_sec / 60)} min</span>
                            {leg.waiting_time_sec > 0 && (
                              <span>· {Math.round(leg.waiting_time_sec / 60)}m wait</span>
                            )}
                            {leg.estimated_fare_inr > 0 && (
                              <span>· ₹{leg.estimated_fare_inr}</span>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Assumptions */}
                  <div className="text-[10px] text-slate-500 pt-2 border-t border-slate-800/60 leading-relaxed">
                    <span className="font-semibold text-slate-400">Assumptions: </span>
                    {journey.assumptions.join(' ')}
                  </div>
                </div>
              );
            })}
          </div>
        </aside>

        {/* Right Side: Interactive Map */}
        <main className="flex-1 h-[45vh] lg:h-full p-4 lg:p-6 bg-slate-950 flex flex-col">
          <Map
            origin={origin}
            destination={destination}
            stops={stops}
            selectedJourney={activeJourney}
            pickingMode={pickingMode}
            onSelectCoordinate={handleCoordinateSelected}
          />
        </main>
      </div>
    </div>
  );
}
