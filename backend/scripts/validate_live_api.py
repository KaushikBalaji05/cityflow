"""Read-only HTTP/routing QA against a running CityFlow API; never mocks providers."""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import httpx


def run(base_url, output, routing_backend='unknown'):
    checks = []
    with httpx.Client(base_url=base_url.rstrip('/'), timeout=15) as client:
        def request(name, method, path, **kwargs):
            start = time.perf_counter()
            try:
                response = client.request(method, path, **kwargs)
                data = response.json()
                result = {'check': name, 'status_code': response.status_code,
                          'elapsed_ms': round((time.perf_counter()-start)*1000, 1)}
            except (httpx.HTTPError, ValueError) as exc:
                result = {'check': name, 'status': 'unavailable', 'error_type': type(exc).__name__}
                response, data = None, None
            checks.append(result)
            return result, response, data

        result, response, data = request('health', 'GET', '/api/v1/health')
        result['passed'] = response is not None and response.status_code == 200
        if data:
            result['transit_graph'] = data.get('transit_graph')
        for name, params in [('short_query', {'q': 'ab'}), ('punctuation_query', {'q': '...'}),
                             ('whitespace_query', {'q': '   '}), ('invalid_limit', {'q': 'Kodihalli', 'limit': 11})]:
            result, response, _ = request(name, 'GET', '/api/v1/geocode/autocomplete', params=params)
            result['passed'] = response is not None and response.status_code == 422
        result, response, data = request('real_autocomplete', 'GET', '/api/v1/geocode/autocomplete', params={'q': 'PES University, RR Campus'})
        if response is not None:
            result['provider_status'] = 'available' if response.status_code == 200 else 'unavailable'
            result['response'] = data

        origin = {'lat': 12.9581, 'lon': 77.6572, 'name': 'Murugeshpalya regression origin'}
        dest = {'lat': 12.9698, 'lon': 77.7499, 'name': 'Whitefield fixture'}
        result, response, data = request('murugeshpalya_bus_journey', 'POST', '/api/v1/plan', json={
            'origin': origin, 'destination': dest, 'allowed_modes': ['walk', 'bus'], 'objective': 'fastest'})
        if data and response.status_code == 200:
            journeys = [j for j in data['journeys'] if 'bus' in j['modes_used']]
            first = journeys[0]['legs'][0] if journeys else {}
            result.update(passed=bool(journeys) and first.get('to_stop_name') == 'Murugeshpalya Bus Stop'
                          and abs(first.get('distance_meters', 0)-66) < 2,
                          access_walk_m=first.get('distance_meters'), boarding_stop=first.get('to_stop_name'),
                          egress_walk_m=journeys[0]['legs'][-1]['distance_meters'] if journeys else None)
        result, response, data = request('outside_transit_coverage', 'POST', '/api/v1/plan', json={
            'origin': {'lat': 13.2473, 'lon': 77.7137}, 'destination': {'lat': 12.711, 'lon': 77.695},
            'allowed_modes': ['bus', 'metro']})
        result['passed'] = response is not None and response.status_code == 200 and data.get('journeys') == []
        result['routing_metadata'] = data.get('routing_metadata') if isinstance(data, dict) else None
    report = {'executed_at_utc': datetime.now(timezone.utc).isoformat(),
              'base_url': base_url, 'provider_responses_mocked': False,
              'routing_backend': routing_backend,
              'checks': checks}
    Path(output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps([{k:v for k,v in c.items() if k != 'response'} for c in checks], indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--output', default='../data/geocoding/qa/live-api-results.json')
    parser.add_argument('--routing-backend', choices=['unknown', 'json', 'postgis'], default='unknown',
                        help='Record the known server launch configuration; HTTP health alone does not prove PostGIS')
    args = parser.parse_args()
    run(args.base_url, args.output, args.routing_backend)
