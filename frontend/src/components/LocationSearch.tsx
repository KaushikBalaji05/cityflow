'use client';

import { useEffect, useId, useState } from 'react';
import { autocomplete, GeocodedPlace } from '@/lib/geocoding';
import { Location } from '@/types/journey';

export default function LocationSearch({ label, value, selected, onChange, onSelect }: {
  label: string; value: string; selected: Location | null;
  onChange: (text: string) => void; onSelect: (place: Location) => void;
}) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [results, setResults] = useState<GeocodedPlace[]>([]);
  const [active, setActive] = useState(-1);
  const [status, setStatus] = useState('');
  const [degraded, setDegraded] = useState(false);

  useEffect(() => {
    setResults([]); setActive(-1); setDegraded(false);
    if (!open || selected || value.trim().length < 3) {
      setStatus(value.trim().length < 3 ? 'Enter at least three characters' : '');
      return;
    }
    const controller = new AbortController();
    setStatus('Searching…');
    const timer = setTimeout(async () => {
      try {
        const data = await autocomplete(value, controller.signal);
        if (controller.signal.aborted) return;
        setResults(data.results); setDegraded(data.meta.degraded);
        setStatus(data.results.length ? '' : 'No locations found in the Bengaluru search region');
      } catch {
        if (!controller.signal.aborted) setStatus('Location search unavailable. Please try again.');
      }
    }, 300);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [value, open, selected]);

  const choose = (p: GeocodedPlace) => {
    onSelect({ lat: p.lat, lon: p.lon, name: p.name, attribution: p.attribution, provider: p.provider });
    setOpen(false);
  };
  return <div className="relative" onBlur={(event) => {
    if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
  }}>
    <div className="flex gap-2">
      <input id={id} aria-label={label} role="combobox" aria-autocomplete="list"
        aria-expanded={open && !selected} aria-controls={`${id}-list`}
        aria-activedescendant={open && active >= 0 ? `${id}-${active}` : undefined}
        autoComplete="off" value={value}
        placeholder="Search any Bengaluru location…"
        className="w-full bg-slate-800/90 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm"
        onFocus={() => setOpen(true)}
        onChange={e => { onChange(e.target.value); setOpen(true); }}
        onKeyDown={e => {
          if (e.key === 'Escape') { setOpen(false); setActive(-1); }
          if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault(); setOpen(true);
            setActive(i => results.length ? (i < 0 ? (e.key === 'ArrowDown' ? 0 : results.length - 1)
              : (i + (e.key === 'ArrowDown' ? 1 : -1) + results.length) % results.length) : -1);
          }
          if (e.key === 'Enter' && open && active >= 0 && results[active]) {
            e.preventDefault(); choose(results[active]);
          }
        }} />
      {value && <button type="button" aria-label={`Clear ${label}`} onClick={() => {
        onChange(''); setOpen(false); document.getElementById(id)?.focus();
      }}>×</button>}
    </div>
    {selected?.attribution && <div className="text-[10px] text-slate-400 mt-1">
      <span>{selected.attribution}</span>{' '}
      {selected.provider === 'geoapify' && <a href="https://www.geoapify.com/">Powered by Geoapify</a>}{' '}
      <a href="https://www.openstreetmap.org/copyright">OpenStreetMap · ODbL</a>
    </div>}
    {open && !selected && <div className="absolute left-0 right-0 top-full mt-1 bg-slate-900 border border-slate-700 rounded-xl shadow-xl z-40 max-h-72 overflow-y-auto">
      <div role="status" aria-live="polite" className="text-xs text-slate-400 px-3">{status}</div>
      <ul id={`${id}-list`} role="listbox" aria-label={`${label} suggestions`} aria-busy={status === 'Searching…'}>
        {results.map((p, i) => <li id={`${id}-${i}`} role="option" aria-selected={i === active}
          key={p.place_id} onMouseDown={e => e.preventDefault()} onClick={() => choose(p)}
          className={`p-3 cursor-pointer text-xs ${i === active ? 'bg-indigo-900' : 'hover:bg-slate-800'}`}>
          <div className="font-semibold">{p.name}</div><div className="text-slate-400">{p.display_address}</div>
          <div className="text-[10px] text-slate-500">{p.attribution}</div>
        </li>)}
      </ul>
      {degraded && <p className="text-xs px-3">One search provider is unavailable; results may be incomplete.</p>}
      {results.length > 0 && <div className="text-[10px] p-3 text-slate-400">
        {results.some(p => p.provider === 'geoapify') && <><a href="https://www.geoapify.com/">Powered by Geoapify</a> · </>}
        <a href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors · ODbL</a>
      </div>}
    </div>}
  </div>;
}
