import json
import math
import os

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def calc_times(stop_ids, stops_map):
    times = []
    for i in range(len(stop_ids) - 1):
        s1 = stops_map[stop_ids[i]]
        s2 = stops_map[stop_ids[i+1]]
        dist = haversine(s1['lat'], s1['lon'], s2['lat'], s2['lon']) * 1.15
        t = max(90, int(dist / 5.55 + 40))
        times.append(t)
    return times

def main():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    json_path = os.path.join(root_dir, "data", "bengaluru", "network.json")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    stops_dict = {s["id"]: s for s in data["stops"]}

    new_stops = [
        # Route 335-E (Old Airport Road & Whitefield)
        {"id": "bus_mayo_hall", "name": "Mayo Hall / Brigade Road Bus Stop", "mode": "bus", "line": "Old Airport Road Trunk", "lat": 12.9738, "lon": 77.6080, "transfer_hub": False},
        {"id": "bus_kodihalli", "name": "Kodihalli (Manipal Hospital) Bus Stop", "mode": "bus", "line": "Old Airport Road Trunk", "lat": 12.9592, "lon": 77.6480, "transfer_hub": False},
        {"id": "bus_murugeshpalya", "name": "Murugeshpalya Bus Stop", "mode": "bus", "line": "Old Airport Road Trunk", "lat": 12.9585, "lon": 77.6575, "transfer_hub": False},
        {"id": "bus_rajeshwari_theater", "name": "Rajeshwari Theater (NAL) Bus Stop", "mode": "bus", "line": "Old Airport Road Trunk", "lat": 12.9576, "lon": 77.6645, "transfer_hub": False},
        {"id": "bus_hal_main_gate", "name": "HAL Main Gate Bus Stop", "mode": "bus", "line": "Old Airport Road Trunk", "lat": 12.9568, "lon": 77.6770, "transfer_hub": False},
        {"id": "bus_vimanapura", "name": "Vimanapura (ISRO) Bus Stop", "mode": "bus", "line": "Old Airport Road Trunk", "lat": 12.9560, "lon": 77.6885, "transfer_hub": False},
        {"id": "bus_kundalahalli_gate", "name": "Kundalahalli Gate Bus Stop", "mode": "bus", "line": "Whitefield Road Trunk", "lat": 12.9648, "lon": 77.7145, "transfer_hub": False},
        {"id": "bus_graphite_india", "name": "Graphite India Bus Stop", "mode": "bus", "line": "Whitefield Road Trunk", "lat": 12.9752, "lon": 77.7230, "transfer_hub": False},
        {"id": "bus_itpl_main_gate", "name": "Pattandur Agrahara (ITPL) Bus Stop", "mode": "bus", "line": "Whitefield Road Trunk", "lat": 12.9875, "lon": 77.7375, "transfer_hub": True},
        {"id": "bus_hopefarm", "name": "Hopefarm Channasandra Bus Stop", "mode": "bus", "line": "Whitefield Road Trunk", "lat": 12.9840, "lon": 77.7516, "transfer_hub": True},
        # Route 500-D (Outer Ring Road)
        {"id": "bus_manyata_tech_park", "name": "Manyata Tech Park (Nagawara) Bus Stop", "mode": "bus", "line": "Outer Ring Road Trunk", "lat": 13.0450, "lon": 77.6200, "transfer_hub": False},
        {"id": "bus_kalyan_nagar", "name": "Kalyan Nagar (Babusapalya) Bus Stop", "mode": "bus", "line": "Outer Ring Road Trunk", "lat": 13.0200, "lon": 77.6450, "transfer_hub": False},
        {"id": "bus_mahadevapura", "name": "Mahadevapura (Doddanekundi) Bus Stop", "mode": "bus", "line": "Outer Ring Road Trunk", "lat": 12.9860, "lon": 77.6950, "transfer_hub": False},
        {"id": "bus_kadubeesanahalli", "name": "Kadubeesanahalli Bus Stop", "mode": "bus", "line": "Outer Ring Road Trunk", "lat": 12.9385, "lon": 77.6940, "transfer_hub": False},
        {"id": "bus_iblur_junction", "name": "Iblur Junction Bus Stop", "mode": "bus", "line": "Outer Ring Road Trunk", "lat": 12.9205, "lon": 77.6680, "transfer_hub": False},
        {"id": "bus_agara_junction", "name": "Agara Junction Bus Stop", "mode": "bus", "line": "Outer Ring Road Trunk", "lat": 12.9190, "lon": 77.6515, "transfer_hub": False},
        # Route 201 (Radial Feeder)
        {"id": "bus_domlur_flyover", "name": "Domlur Flyover / Doopanahalli Bus Stop", "mode": "bus", "line": "Radial Feeder", "lat": 12.9640, "lon": 77.6400, "transfer_hub": False},
        {"id": "bus_koramangala_water_tank", "name": "Koramangala Sony World / Water Tank Bus Stop", "mode": "bus", "line": "Radial Feeder", "lat": 12.9340, "lon": 77.6280, "transfer_hub": False},
        {"id": "bus_st_johns_hospital", "name": "St. Johns Hospital Bus Stop", "mode": "bus", "line": "Radial Feeder", "lat": 12.9280, "lon": 77.6190, "transfer_hub": False},
    ]

    for s in new_stops:
        if s["id"] not in stops_dict:
            data["stops"].append(s)
            stops_dict[s["id"]] = s

    # Update 335-E
    r335e_east_stops = [
        "bus_majestic_kbs", "bus_corporation", "bus_richmond_circle", "bus_mayo_hall",
        "bus_domlur_ttmc", "bus_kodihalli", "bus_murugeshpalya", "bus_rajeshwari_theater",
        "bus_hal_main_gate", "bus_vimanapura", "bus_marathahalli_bridge", "bus_kundalahalli_gate",
        "bus_graphite_india", "bus_itpl_main_gate", "bus_hopefarm", "bus_whitefield_ttmc"
    ]
    r335e_west_stops = list(reversed(r335e_east_stops))

    # Update 500-D
    r500d_south_stops = [
        "bus_hebbal_flyover", "bus_manyata_tech_park", "bus_kalyan_nagar", "bus_tin_factory",
        "bus_kr_puram_railway", "bus_mahadevapura", "bus_marathahalli_bridge", "bus_kadubeesanahalli",
        "bus_bellandur_ecospace", "bus_iblur_junction", "bus_agara_junction", "bus_hsr_layout_bd6",
        "bus_central_silk_board"
    ]
    r500d_north_stops = list(reversed(r500d_south_stops))

    # Update 201
    r201_east_stops = [
        "bus_banashankari_ttmc", "bus_jayadeva_hospital", "bus_btm_layout_water_tank",
        "bus_central_silk_board", "bus_st_johns_hospital", "bus_koramangala_water_tank",
        "bus_domlur_ttmc", "bus_domlur_flyover", "bus_indiranagar_100ft"
    ]
    r201_west_stops = list(reversed(r201_east_stops))

    for r in data["transit_routes"]:
        if r["id"] == "bmtc_335e_eastbound":
            r["stops"] = r335e_east_stops
            r["segment_travel_times"] = calc_times(r335e_east_stops, stops_dict)
        elif r["id"] == "bmtc_335e_westbound":
            r["stops"] = r335e_west_stops
            r["segment_travel_times"] = calc_times(r335e_west_stops, stops_dict)
        elif r["id"] == "bmtc_500d_southbound":
            r["stops"] = r500d_south_stops
            r["segment_travel_times"] = calc_times(r500d_south_stops, stops_dict)
        elif r["id"] == "bmtc_500d_northbound":
            r["stops"] = r500d_north_stops
            r["segment_travel_times"] = calc_times(r500d_north_stops, stops_dict)
        elif r["id"] == "bmtc_201_eastbound":
            r["stops"] = r201_east_stops
            r["segment_travel_times"] = calc_times(r201_east_stops, stops_dict)
        elif r["id"] == "bmtc_201_westbound":
            r["stops"] = r201_west_stops
            r["segment_travel_times"] = calc_times(r201_west_stops, stops_dict)

    existing_transfers = {(te["from_stop"], te["to_stop"]) for te in data.get("transfer_edges", [])}
    new_transfers = [
        {"from_stop": "metro_itpl", "to_stop": "bus_itpl_main_gate", "distance_meters": 60, "walking_duration_sec": 50},
        {"from_stop": "bus_itpl_main_gate", "to_stop": "metro_itpl", "distance_meters": 60, "walking_duration_sec": 50},
        {"from_stop": "metro_hopefarm", "to_stop": "bus_hopefarm", "distance_meters": 60, "walking_duration_sec": 50},
        {"from_stop": "bus_hopefarm", "to_stop": "metro_hopefarm", "distance_meters": 60, "walking_duration_sec": 50},
        {"from_stop": "metro_mg_road", "to_stop": "bus_mayo_hall", "distance_meters": 350, "walking_duration_sec": 292},
        {"from_stop": "bus_mayo_hall", "to_stop": "metro_mg_road", "distance_meters": 350, "walking_duration_sec": 292},
    ]

    for nt in new_transfers:
        if (nt["from_stop"], nt["to_stop"]) not in existing_transfers:
            data["transfer_edges"].append(nt)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print("Network successfully enriched!")
    print(f"Total stops: {len(data['stops'])}")
    print(f"Total routes: {len(data['transit_routes'])}")
    print(f"Total transfer edges: {len(data['transfer_edges'])}")

if __name__ == "__main__":
    main()
