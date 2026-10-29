'use client';

import React, { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import { Journey, Location, StopItem } from '@/types/journey';

interface MapProps {
  origin: Location | null;
  destination: Location | null;
  stops: StopItem[];
  selectedJourney: Journey | null;
  pickingMode: 'origin' | 'destination' | null;
  onSelectCoordinate: (loc: Location, type: 'origin' | 'destination') => void;
}

export default function Map({
  origin,
  destination,
  stops,
  selectedJourney,
  pickingMode,
  onSelectCoordinate,
}: MapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);

  const markersRef = useRef<maplibregl.Marker[]>([]);
  const originMarkerRef = useRef<maplibregl.Marker | null>(null);
  const destMarkerRef = useRef<maplibregl.Marker | null>(null);
  const routeLayersRef = useRef<string[]>([]);

  // 1. Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: 'https://tiles.openfreemap.org/styles/liberty',
      center: [77.62, 12.97], // Bengaluru center
      zoom: 11.5,
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-right');

    map.on('load', () => {
      setMapLoaded(true);
    });

    map.on('click', (e) => {
      if (!pickingMode) return;
      const newLoc: Location = {
        lat: Number(e.lngLat.lat.toFixed(5)),
        lon: Number(e.lngLat.lng.toFixed(5)),
        name: `Map Pin (${e.lngLat.lat.toFixed(4)}, ${e.lngLat.lng.toFixed(4)})`,
      };
      onSelectCoordinate(newLoc, pickingMode);
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
      setMapLoaded(false);
    };
  }, [pickingMode, onSelectCoordinate]);

  // 2. Render Transit Stops Markers (DOM markers, safe once map exists)
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    // Clear old stop markers
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    stops.forEach((stop) => {
      const el = document.createElement('div');
      el.className =
        'w-3 h-3 rounded-full border-2 border-white shadow-md cursor-pointer transition-transform hover:scale-150';
      el.style.backgroundColor = stop.mode === 'metro' ? '#a855f7' : '#3b82f6';
      el.title = stop.name;

      const popup = new maplibregl.Popup({ offset: 12 }).setHTML(`
        <div style="font-family: inherit;">
          <div style="font-weight: 700; font-size: 13px; color: #f8fafc; margin-bottom: 2px;">${stop.name}</div>
          <div style="font-size: 11px; color: #94a3b8; margin-bottom: 8px;">
            ${stop.mode.toUpperCase()} · ${stop.line || ''}
          </div>
          <div style="display: flex; gap: 6px;">
            <button id="pop-orig-${stop.id}" style="background-color: #10b981; color: white; padding: 4px 8px; border-radius: 6px; font-size: 10px; font-weight: 600; cursor: pointer; border: none;">
              Set Origin
            </button>
            <button id="pop-dest-${stop.id}" style="background-color: #f43f5e; color: white; padding: 4px 8px; border-radius: 6px; font-size: 10px; font-weight: 600; cursor: pointer; border: none;">
              Set Dest
            </button>
          </div>
        </div>
      `);

      popup.on('open', () => {
        const origBtn = document.getElementById(`pop-orig-${stop.id}`);
        const destBtn = document.getElementById(`pop-dest-${stop.id}`);
        if (origBtn) {
          origBtn.onclick = () => {
            onSelectCoordinate({ lat: stop.lat, lon: stop.lon, name: stop.name }, 'origin');
            popup.remove();
          };
        }
        if (destBtn) {
          destBtn.onclick = () => {
            onSelectCoordinate({ lat: stop.lat, lon: stop.lon, name: stop.name }, 'destination');
            popup.remove();
          };
        }
      });

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([stop.lon, stop.lat])
        .setPopup(popup)
        .addTo(map);

      markersRef.current.push(marker);
    });
  }, [stops, onSelectCoordinate]);

  // 3. Render Origin & Destination Pin Markers
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (origin) {
      if (!originMarkerRef.current) {
        const el = document.createElement('div');
        el.className =
          'w-7 h-7 rounded-full bg-emerald-500 border-2 border-white shadow-xl flex items-center justify-center font-bold text-xs text-white';
        el.innerText = 'A';
        originMarkerRef.current = new maplibregl.Marker({ element: el })
          .setLngLat([origin.lon, origin.lat])
          .addTo(map);
      } else {
        originMarkerRef.current.setLngLat([origin.lon, origin.lat]);
      }
    } else if (originMarkerRef.current) {
      originMarkerRef.current.remove();
      originMarkerRef.current = null;
    }

    if (destination) {
      if (!destMarkerRef.current) {
        const el = document.createElement('div');
        el.className =
          'w-7 h-7 rounded-full bg-rose-500 border-2 border-white shadow-xl flex items-center justify-center font-bold text-xs text-white';
        el.innerText = 'B';
        destMarkerRef.current = new maplibregl.Marker({ element: el })
          .setLngLat([destination.lon, destination.lat])
          .addTo(map);
      } else {
        destMarkerRef.current.setLngLat([destination.lon, destination.lat]);
      }
    } else if (destMarkerRef.current) {
      destMarkerRef.current.remove();
      destMarkerRef.current = null;
    }
  }, [origin, destination]);

  // 4. Render Selected Journey Geometry (Guarded against style loading)
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded || !map.isStyleLoaded()) return;

    const renderPolylines = () => {
      if (!map.isStyleLoaded()) return;

      // Clean up previous route layers & sources
      routeLayersRef.current.forEach((layerId) => {
        try {
          if (map.getLayer(layerId)) map.removeLayer(layerId);
          if (map.getSource(layerId)) map.removeSource(layerId);
        } catch (e) {
          // ignore cleanup errors
        }
      });
      routeLayersRef.current = [];

      if (!selectedJourney) return;

      const allCoords: [number, number][] = [];

      selectedJourney.legs.forEach((leg, index) => {
        if (!leg.polyline || leg.polyline.length < 2) return;

        const layerId = `route-leg-${index}-${Date.now()}`;
        routeLayersRef.current.push(layerId);

        let color = '#94a3b8'; // Walk grey
        if (leg.mode === 'metro') {
          color = leg.route_name.toLowerCase().includes('green') ? '#10b981' : '#a855f7';
        } else if (leg.mode === 'bus') {
          color = '#3b82f6';
        } else if (leg.mode === 'drive') {
          color = '#f59e0b';
        }

        try {
          map.addSource(layerId, {
            type: 'geojson',
            data: {
              type: 'Feature',
              properties: {},
              geometry: {
                type: 'LineString',
                coordinates: leg.polyline,
              },
            },
          });

          map.addLayer({
            id: layerId,
            type: 'line',
            source: layerId,
            layout: {
              'line-join': 'round',
              'line-cap': 'round',
            },
            paint: {
              'line-color': color,
              'line-width': leg.mode === 'walk' ? 4 : 6,
              'line-opacity': 0.9,
              ...(leg.mode === 'walk' ? { 'line-dasharray': [2, 2] } : {}),
            },
          });

          leg.polyline.forEach((coord) => allCoords.push(coord));
        } catch (err) {
          console.warn('Failed to add layer to map:', err);
        }
      });

      if (allCoords.length > 0) {
        try {
          const bounds = allCoords.reduce(
            (b, c) => b.extend(c),
            new maplibregl.LngLatBounds(allCoords[0], allCoords[0])
          );
          map.fitBounds(bounds, { padding: 60, maxZoom: 14, duration: 800 });
        } catch (e) {
          // ignore bounds calculation errors
        }
      }
    };

    renderPolylines();
  }, [selectedJourney, mapLoaded]);

  return (
    <div className="relative w-full h-full rounded-3xl overflow-hidden shadow-2xl border border-slate-800">
      <div ref={mapContainerRef} className="w-full h-full" />

      {/* Picking Mode Banner */}
      {pickingMode && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20 bg-indigo-600 text-white text-xs font-semibold px-4 py-2 rounded-full shadow-xl flex items-center space-x-2 animate-bounce">
          <span>📍 Click anywhere on the map to set {pickingMode.toUpperCase()}</span>
        </div>
      )}

      {/* Legend Badge */}
      <div className="absolute bottom-6 right-6 z-10 bg-slate-950/90 backdrop-blur-md border border-slate-800 rounded-2xl p-3.5 text-xs space-y-2 shadow-2xl pointer-events-auto hidden sm:block">
        <div className="font-semibold text-slate-200 border-b border-slate-800 pb-1.5 flex items-center justify-between space-x-3">
          <span>Bengaluru Transit</span>
          <span className="text-[10px] text-emerald-400 font-mono">LIVE GRAPH</span>
        </div>
        <div className="space-y-1.5">
          <div className="flex items-center space-x-2">
            <span className="w-3 h-3 rounded-full bg-purple-500 shadow-sm shadow-purple-500/50" />
            <span className="text-slate-300">Namma Metro (Purple Line)</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="w-3 h-3 rounded-full bg-emerald-500 shadow-sm shadow-emerald-500/50" />
            <span className="text-slate-300">Namma Metro (Green Line)</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="w-3 h-3 rounded-full bg-blue-500 shadow-sm shadow-blue-500/50" />
            <span className="text-slate-300">BMTC Buses (500-D, 335-E, 201)</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="w-3 h-3 rounded-full bg-amber-400 shadow-sm shadow-amber-400/50" />
            <span className="text-slate-300">Auto-Rickshaw / Cab</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="w-3 h-1 rounded bg-slate-400" />
            <span className="text-slate-400">Walking / Transfer Links</span>
          </div>
        </div>
      </div>
    </div>
  );
}
