import React, { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import LocationSearch from './LocationSearch';
import { Location } from '@/types/journey';

const result = { place_id: 'test:1', name: 'Kodihalli', display_address: 'Kodihalli, Bengaluru',
  lat: 12.96, lon: 77.65, provider: 'geoapify', attribution: 'Geoapify and OSM' };

function Harness() {
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<Location | null>(null);
  return <><LocationSearch label="Origin" value={query} selected={selected}
    onChange={q => { setQuery(q); setSelected(null); }}
    onSelect={p => { setSelected(p); setQuery(p.name || ''); }} />
    <output>{selected ? `${selected.lat},${selected.lon}` : 'unselected'}</output></>;
}

describe('LocationSearch', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ results: [result, result], meta: {} }) }));
  });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });
  const tick = async (ms: number) => { await act(async () => { await vi.advanceTimersByTimeAsync(ms); }); };

  it('requires three characters and debounces requests for 300ms', async () => {
    render(<Harness />);
    const input = screen.getByRole('combobox'); fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'Ko' } }); await tick(500);
    expect(fetch).not.toHaveBeenCalled();
    fireEvent.change(input, { target: { value: 'Kodi' } }); await tick(299);
    expect(fetch).not.toHaveBeenCalled(); await tick(1);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(screen.getAllByRole('option')).toHaveLength(1);
  });

  it('aborts stale requests and ignores late responses', async () => {
    let resolveOld!: (value: Response | PromiseLike<Response>) => void;
    vi.mocked(fetch).mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve; }));
    render(<Harness />); const input = screen.getByRole('combobox'); fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'Old' } }); await tick(300);
    const signal = vi.mocked(fetch).mock.calls[0][1]?.signal;
    fireEvent.change(input, { target: { value: 'Kodihalli' } });
    expect(signal?.aborted).toBe(true); await tick(300);
    await act(async () => { resolveOld({ ok: true, json: async () => ({ results: [{ ...result, name: 'Stale' }], meta: {} }) } as Response); });
    expect(screen.queryByText('Stale')).toBeNull(); expect(screen.getByText('Kodihalli')).toBeTruthy();
  });

  it('supports keyboard selection, clears coordinates on edit, and clears selection', async () => {
    render(<Harness />); const input = screen.getByRole('combobox'); fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'Kodi' } }); await tick(300);
    fireEvent.keyDown(input, { key: 'ArrowDown' }); fireEvent.keyDown(input, { key: 'Enter' });
    expect(screen.getByText('12.96,77.65')).toBeTruthy();
    fireEvent.change(input, { target: { value: 'Other' } });
    expect(screen.getByText('unselected')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Clear Origin' }));
    expect((input as HTMLInputElement).value).toBe('');
  });

  it('shows no-results and error states', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({ ok: true, json: async () => ({ results: [], meta: {} }) } as Response);
    render(<Harness />); const input = screen.getByRole('combobox'); fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'Missing' } }); await tick(300);
    expect(screen.getByText(/No locations found/)).toBeTruthy();
    vi.mocked(fetch).mockRejectedValueOnce(new Error('offline'));
    fireEvent.change(input, { target: { value: 'Offline' } }); await tick(300);
    expect(screen.getByText(/Location search unavailable/)).toBeTruthy();
  });
});
