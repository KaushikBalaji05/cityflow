import { CorridorMetric, PlanRequest, PlanResponse, StopItem } from '@/types/journey';

// Fallback stops in case backend is starting up
const FALLBACK_STOPS: StopItem[] = [
  { id: 'metro_whitefield', name: 'Whitefield (Kadugodi) Metro', mode: 'metro', line: 'Purple Line', lat: 12.9698, lon: 77.7499, transfer_hub: false },
  { id: 'metro_hopefarm', name: 'Hopefarm Channasandra Metro', mode: 'metro', line: 'Purple Line', lat: 12.9840, lon: 77.7516, transfer_hub: false },
  { id: 'metro_itpl', name: 'Pattandur Agrahara (ITPL) Metro', mode: 'metro', line: 'Purple Line', lat: 12.9877, lon: 77.7378, transfer_hub: false },
  { id: 'metro_kr_puram', name: 'KR Puram Metro Station', mode: 'metro', line: 'Purple Line', lat: 12.9982, lon: 77.6750, transfer_hub: true },
  { id: 'metro_indiranagar', name: 'Indiranagar Metro Station', mode: 'metro', line: 'Purple Line', lat: 12.9784, lon: 77.6408, transfer_hub: false },
  { id: 'metro_mg_road', name: 'MG Road Metro Station', mode: 'metro', line: 'Purple Line', lat: 12.9755, lon: 77.6066, transfer_hub: false },
  { id: 'metro_majestic', name: 'Nadaprabhu Kempegowda Majestic Metro', mode: 'metro', line: 'Interchange', lat: 12.9756, lon: 77.5728, transfer_hub: true },
  { id: 'metro_banashankari', name: 'Banashankari Metro Station', mode: 'metro', line: 'Green Line', lat: 12.9155, lon: 77.5736, transfer_hub: true },
  { id: 'bus_majestic_kbs', name: 'Kempegowda Bus Station (Majestic)', mode: 'bus', line: 'BMTC Hub', lat: 12.9772, lon: 77.5713, transfer_hub: true },
  { id: 'bus_central_silk_board', name: 'Central Silk Board Interchange', mode: 'bus', line: 'ORR Hub', lat: 12.9172, lon: 77.6227, transfer_hub: true },
  { id: 'bus_bellandur_ecospace', name: 'Bellandur Ecospace Bus Stop', mode: 'bus', line: 'ORR Hub', lat: 12.9260, lon: 77.6845, transfer_hub: false },
  { id: 'bus_hebbal_flyover', name: 'Hebbal Flyover Bus Station', mode: 'bus', line: 'ORR Hub', lat: 13.0358, lon: 77.5970, transfer_hub: true },
];

function getApiUrls(path: string): string[] {
  return [
    `http://127.0.0.1:8000${path}`,
    `http://localhost:8000${path}`,
    path, // Next.js rewrite proxy
  ];
}

async function fetchWithFallback<T>(path: string, options?: RequestInit): Promise<T> {
  const urls = getApiUrls(path);
  let lastError: Error | null = null;

  for (const url of urls) {
    try {
      const res = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...(options?.headers || {}),
        },
      });
      if (res.ok) {
        return (await res.json()) as T;
      }
    } catch (err: any) {
      lastError = err;
    }
  }

  throw lastError || new Error(`Failed to fetch from ${path}`);
}

export async function fetchHealth() {
  try {
    return await fetchWithFallback<any>('/api/v1/health');
  } catch (err) {
    return { status: 'offline', error: 'Backend unreachable on port 8000' };
  }
}

export async function fetchStops(mode?: string): Promise<StopItem[]> {
  try {
    const query = mode ? `?mode=${encodeURIComponent(mode)}` : '';
    return await fetchWithFallback<StopItem[]>(`/api/v1/stops${query}`);
  } catch (err) {
    console.warn('Backend unavailable, using cached fallback stops:', err);
    return mode ? FALLBACK_STOPS.filter((s) => s.mode === mode) : FALLBACK_STOPS;
  }
}

export async function searchStops(query: string): Promise<StopItem[]> {
  if (!query.trim()) return [];
  try {
    return await fetchWithFallback<StopItem[]>(`/api/v1/search?q=${encodeURIComponent(query)}`);
  } catch (err) {
    const q = query.toLowerCase();
    return FALLBACK_STOPS.filter((s) => s.name.toLowerCase().includes(q));
  }
}

export async function planJourney(request: PlanRequest): Promise<PlanResponse> {
  return await fetchWithFallback<PlanResponse>('/api/v1/plan', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function fetchLiveCorridors(): Promise<CorridorMetric[]> {
  try {
    return await fetchWithFallback<CorridorMetric[]>('/api/v1/live/corridors');
  } catch (err) {
    return [];
  }
}

export async function triggerSimulationTick(scenario: string = 'normal'): Promise<any> {
  return await fetchWithFallback<any>('/api/v1/live/simulate/tick', {
    method: 'POST',
    body: JSON.stringify({ ticks: 1, scenario }),
  });
}

export async function resetSimulationDelays(): Promise<any> {
  return await fetchWithFallback<any>('/api/v1/live/reset', {
    method: 'POST',
  });
}

