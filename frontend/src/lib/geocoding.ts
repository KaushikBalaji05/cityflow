export interface GeocodedPlace {
  place_id: string; name: string; display_address: string;
  lat: number; lon: number; category: string; confidence: number | null;
  provider: string; attribution: string;
}

export async function autocomplete(query: string, signal: AbortSignal): Promise<{
  results: GeocodedPlace[]; meta: { degraded: boolean };
}> {
  const response = await fetch(`/api/v1/geocode/autocomplete?q=${encodeURIComponent(query)}&limit=6`, { signal });
  if (!response.ok) throw new Error('Location search unavailable');
  const data = await response.json();
  const seen = new Set<string>();
  data.results = data.results.filter((p: GeocodedPlace) => {
    if (seen.has(p.place_id)) return false;
    seen.add(p.place_id); return true;
  });
  return data;
}
