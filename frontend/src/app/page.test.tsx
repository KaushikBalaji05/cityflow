import React from 'react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import HomePage from './page';
import { planJourney } from '@/lib/api';
import { PlanResponse } from '@/types/journey';

vi.mock('next/dynamic', () => ({ default: () => () => null }));
vi.mock('@/lib/api', () => ({
  planJourney: vi.fn(), fetchHealth: vi.fn(async () => ({ status: 'offline' })),
  fetchStops: vi.fn(async () => []), fetchLiveCorridors: vi.fn(async () => []),
  triggerSimulationTick: vi.fn(), resetSimulationDelays: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(planJourney).mockReset();
  vi.mocked(planJourney).mockResolvedValue({ journeys: [] } as unknown as PlanResponse);
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('unavailable')));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('plans with the selected preset after an origin edit instead of stale endpoints', async () => {
  await act(async () => { render(<HomePage />); });
  fireEvent.change(screen.getByRole('combobox', { name: /^Origin$/ }), { target: { value: 'Other place' } });
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'Indiranagar ➔ Whitefield (Tech Hub)' }));
  });
  expect(vi.mocked(planJourney).mock.lastCall?.[0].origin).toEqual({
    lat: 12.9784, lon: 77.6408, name: 'Indiranagar Metro Station',
  });
  expect(screen.queryByText('Please select both Origin and Destination')).toBeNull();
});

it('ignores a pending route response after an endpoint is edited', async () => {
  let finish!: (response: PlanResponse) => void;
  vi.mocked(planJourney).mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
  await act(async () => { render(<HomePage />); });
  fireEvent.change(screen.getByRole('combobox', { name: /^Origin$/ }), { target: { value: 'Changed location' } });
  await act(async () => { finish({ journeys: [] } as unknown as PlanResponse); });
  // A stale response must not reintroduce a routing warning for the old endpoints.
  expect(screen.queryByText(/No transit journey found/)).toBeNull();
  expect(screen.getByRole('button', { name: /Compute Routes/ })).toBeTruthy();
});
