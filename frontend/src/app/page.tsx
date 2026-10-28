'use client';

import React, { useState, useEffect } from 'react';
import { Journey, Location, RoutingObjective, TransportMode } from '@/types/journey';
import { planJourney, fetchHealth } from '@/lib/api';

export default function HomePage() {
  const [origin, setOrigin] = useState<Location>({
    lat: 12.9784,
    lon: 77.6408,
    name: 'Indiranagar Metro Station',
  });
  const [destination, setDestination] = useState<Location>({
    lat: 12.9698,
    lon: 77.7499,
    name: 'Whitefield (Kadugodi) Metro',
  });
  const [allowedModes, setAllowedModes] = useState<TransportMode[]>(['metro', 'bus', 'walk', 'drive']);
  const [objective, setObjective] = useState<RoutingObjective>('fastest');
  const [journeys, setJourneys] = useState<Journey[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [apiHealth, setApiHealth] = useState<any>(null);

  useEffect(() => {
    fetchHealth()
      .then(setApiHealth)
      .catch(() => setApiHealth({ status: 'offline' }));
  }, []);

  const handleSearch = async () => {
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
    } catch (err: any) {
      setError(err.message || 'Routing failed');
    } finally {
      setLoading(false);
    }
  };

  const toggleMode = (mode: TransportMode) => {
    setAllowedModes((prev) =>
      prev.includes(mode) ? prev.filter((m) => m !== mode) : [...prev, mode]
    );
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-950/70 backdrop-blur px-6 py-4 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-emerald-400 flex items-center justify-center font-black text-xl shadow-lg shadow-indigo-500/20">
            CF
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white flex items-center space-x-2">
              <span>CityFlow</span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold">
                Bengaluru
              </span>
            </h1>
            <p className="text-xs text-slate-400">Multimodal Transit & Intelligence Platform</p>
          </div>
        </div>
        <div className="flex items-center space-x-4 text-xs">
          <span className="inline-flex items-center px-3 py-1 rounded-full bg-slate-900 border border-slate-800 text-slate-300">
            <span
              className={`w-2 h-2 mr-2 rounded-full ${
                apiHealth?.status === 'healthy' ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
              }`}
            />
            {apiHealth?.status === 'healthy' ? 'Engine Ready (37+ Stops)' : 'Connecting to API'}
          </span>
          <a href="/api/v1/docs" target="_blank" className="text-slate-400 hover:text-white transition">
            API Docs
          </a>
        </div>
      </header>

      {/* Main Layout */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Control Panel */}
        <div className="lg:col-span-5 space-y-6">
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
              Journey Configuration
            </h2>

            {/* Origin & Destination */}
            <div className="space-y-3">
              <div>
                <label className="text-xs text-slate-400 font-medium">Origin</label>
                <input
                  type="text"
                  value={origin.name}
                  onChange={(e) => setOrigin({ ...origin, name: e.target.value })}
                  className="w-full mt-1 bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="text-xs text-slate-400 font-medium">Destination</label>
                <input
                  type="text"
                  value={destination.name}
                  onChange={(e) => setDestination({ ...destination, name: e.target.value })}
                  className="w-full mt-1 bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>

            {/* Mode Toggles */}
            <div className="space-y-1.5">
              <label className="text-xs text-slate-400 font-medium">Allowed Transport Modes</label>
              <div className="grid grid-cols-4 gap-2">
                {[
                  { mode: 'metro', label: '🚇 Metro' },
                  { mode: 'bus', label: '🚌 BMTC' },
                  { mode: 'walk', label: '🚶 Walk' },
                  { mode: 'drive', label: '🚗 Auto/Cab' },
                ].map((item) => (
                  <button
                    key={item.mode}
                    type="button"
                    onClick={() => toggleMode(item.mode as TransportMode)}
                    className={`py-2 px-1 text-xs font-medium rounded-xl border transition ${
                      allowedModes.includes(item.mode as TransportMode)
                        ? 'bg-indigo-600/20 border-indigo-500 text-indigo-300'
                        : 'bg-slate-800/40 border-slate-700 text-slate-500 hover:text-slate-300'
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Objective */}
            <div className="space-y-1">
              <label className="text-xs text-slate-400 font-medium">Optimization Goal</label>
              <select
                value={objective}
                onChange={(e) => setObjective(e.target.value as RoutingObjective)}
                className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
              >
                <option value="fastest">⚡ Fastest Arrival</option>
                <option value="lowest_cost">💰 Lowest Estimated Fare</option>
                <option value="least_walking">🚶 Least Walking</option>
                <option value="fewest_transfers">🔄 Fewest Transfers</option>
                <option value="balanced">⚖️ Balanced (Time, Cost & Effort)</option>
              </select>
            </div>

            <button
              onClick={handleSearch}
              disabled={loading}
              className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-3 px-4 rounded-xl text-sm transition shadow-lg shadow-indigo-600/30 disabled:opacity-50"
            >
              {loading ? 'Finding Best Routes...' : 'Search Journeys'}
            </button>
          </div>

          {/* Results Summary Cards */}
          <div className="space-y-3">
            {error && (
              <div className="p-4 rounded-xl bg-rose-950/60 border border-rose-800 text-xs text-rose-300">
                {error}
              </div>
            )}

            {journeys.map((journey, idx) => (
              <div
                key={journey.journey_id || idx}
                className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800 hover:border-slate-700 transition space-y-3 shadow-lg"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="text-lg font-bold text-white">
                      {Math.round(journey.total_duration_sec / 60)} min
                    </span>
                    {idx === 0 && (
                      <span className="bg-indigo-500/20 text-indigo-400 text-[10px] font-semibold px-2 py-0.5 rounded-full border border-indigo-500/30">
                        Top Recommendation
                      </span>
                    )}
                  </div>
                  <span className="text-sm font-semibold text-emerald-400">
                    ₹{journey.estimated_fare_inr.toFixed(0)}
                  </span>
                </div>

                <div className="text-xs text-slate-300 font-medium">{journey.summary}</div>

                <div className="flex items-center space-x-4 text-[11px] text-slate-400 border-y border-slate-800/80 py-2">
                  <span>🚶 {(journey.total_walking_distance_meters / 1000).toFixed(2)} km walk</span>
                  <span>🔄 {journey.total_transfers} transfers</span>
                  <span>⏳ {Math.round(journey.total_waiting_time_sec / 60)} min wait</span>
                </div>

                <div className="space-y-1.5 text-xs">
                  {journey.legs.map((leg) => (
                    <div key={leg.leg_index} className="flex items-center space-x-2 text-slate-300">
                      <span>{leg.mode === 'metro' ? '🚇' : leg.mode === 'bus' ? '🚌' : leg.mode === 'drive' ? '🚗' : '🚶'}</span>
                      <span className="font-medium text-slate-200">{leg.route_name}:</span>
                      <span className="text-slate-400 text-[11px]">
                        {leg.from_stop_name} → {leg.to_stop_name} ({Math.round(leg.duration_sec / 60)}m)
                      </span>
                    </div>
                  ))}
                </div>

                <div className="pt-2 text-[10px] text-slate-500 border-t border-slate-800/60">
                  <span className="font-semibold text-slate-400">Assumptions: </span>
                  {journey.assumptions.join(' ')}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Info & Live Map Panel */}
        <div className="lg:col-span-7 bg-slate-900/60 border border-slate-800 rounded-3xl p-6 flex flex-col justify-between">
          <div>
            <h3 className="text-base font-semibold text-white">Bengaluru Transit Network Overview</h3>
            <p className="text-xs text-slate-400 mt-1">
              Real-world scheduled geometry from BMRCL Purple & Green lines, BMTC trunk routes (500-D, 335-E, 201, 365), and pedestrian interchange corridors.
            </p>
          </div>

          <div className="my-8 p-6 rounded-2xl bg-slate-950/80 border border-slate-800 space-y-4">
            <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
              Verification & Acceptance Criteria (Stage 1 MVP)
            </h4>
            <div className="grid grid-cols-2 gap-3 text-xs text-slate-400">
              <div className="flex items-center space-x-2">
                <span className="text-emerald-400">✓</span>
                <span>Verified End-to-End Metro & Bus Routing</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="text-emerald-400">✓</span>
                <span>Pedestrian Ingress/Egress at 1.2 m/s</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="text-emerald-400">✓</span>
                <span>Real Station Geometries & Headways</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="text-emerald-400">✓</span>
                <span>Bengaluru Fare Structures (₹ INR)</span>
              </div>
            </div>
          </div>

          <div className="text-xs text-slate-500 flex items-center justify-between">
            <span>CityFlow 1.0.0-mvp</span>
            <span>FastAPI + MapLibre + Next.js</span>
          </div>
        </div>
      </main>
    </div>
  );
}
