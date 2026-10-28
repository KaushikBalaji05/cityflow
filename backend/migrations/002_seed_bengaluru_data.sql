-- =====================================================================
-- CityFlow Database Migration 002: Seed Bengaluru Transport Network
-- Target: PostgreSQL 16 + PostGIS 3.4
-- =====================================================================

-- 1. Insert Core Metro & Bus Stops
INSERT INTO transit_stops (id, name, mode, line_name, location, is_transfer_hub) VALUES
('metro_whitefield', 'Whitefield (Kadugodi) Metro Station', 'metro', 'Purple Line', ST_SetSRID(ST_MakePoint(77.7499, 12.9698), 4326), FALSE),
('metro_hopefarm', 'Hopefarm Channasandra Metro', 'metro', 'Purple Line', ST_SetSRID(ST_MakePoint(77.7516, 12.9840), 4326), FALSE),
('metro_itpl', 'Pattandur Agrahara (ITPL) Metro', 'metro', 'Purple Line', ST_SetSRID(ST_MakePoint(77.7378, 12.9877), 4326), FALSE),
('metro_kr_puram', 'KR Puram Metro Station', 'metro', 'Purple Line', ST_SetSRID(ST_MakePoint(77.6750, 12.9982), 4326), TRUE),
('metro_baiyappanahalli', 'Baiyappanahalli Metro Station', 'metro', 'Purple Line', ST_SetSRID(ST_MakePoint(77.6525, 12.9907), 4326), FALSE),
('metro_indiranagar', 'Indiranagar Metro Station', 'metro', 'Purple Line', ST_SetSRID(ST_MakePoint(77.6408, 12.9784), 4326), FALSE),
('metro_halasuru', 'Halasuru Metro Station', 'metro', 'Purple Line', ST_SetSRID(ST_MakePoint(77.6256, 12.9740), 4326), FALSE),
('metro_mg_road', 'MG Road Metro Station', 'metro', 'Purple Line', ST_SetSRID(ST_MakePoint(77.6066, 12.9755), 4326), FALSE),
('metro_cubbon_park', 'Cubbon Park Metro Station', 'metro', 'Purple Line', ST_SetSRID(ST_MakePoint(77.5973, 12.9806), 4326), FALSE),
('metro_vidhana_soudha', 'Vidhana Soudha Metro Station', 'metro', 'Purple Line', ST_SetSRID(ST_MakePoint(77.5912, 12.9797), 4326), FALSE),
('metro_majestic', 'Nadaprabhu Kempegowda Majestic Metro', 'metro', 'Interchange', ST_SetSRID(ST_MakePoint(77.5728, 12.9756), 4326), TRUE),
('metro_city_railway', 'Krantivira Sangolli Rayanna Railway Metro', 'metro', 'Purple Line', ST_SetSRID(ST_MakePoint(77.5667, 12.9781), 4326), FALSE),
('metro_vijayanagar', 'Vijayanagar Metro Station', 'metro', 'Purple Line', ST_SetSRID(ST_MakePoint(77.5376, 12.9696), 4326), FALSE),
('metro_yeshwanthpur', 'Yeshwanthpur Metro Station', 'metro', 'Green Line', ST_SetSRID(ST_MakePoint(77.5500, 13.0232), 4326), FALSE),
('metro_sandal_soap', 'Sandal Soap Factory Metro', 'metro', 'Green Line', ST_SetSRID(ST_MakePoint(77.5539, 13.0145), 4326), FALSE),
('metro_rajajinagar', 'Rajajinagar Metro Station', 'metro', 'Green Line', ST_SetSRID(ST_MakePoint(77.5557, 12.9986), 4326), FALSE),
('metro_sampige_road', 'Mantri Square Sampige Road Metro', 'metro', 'Green Line', ST_SetSRID(ST_MakePoint(77.5710, 12.9908), 4326), FALSE),
('metro_chickpete', 'Chickpete Metro Station', 'metro', 'Green Line', ST_SetSRID(ST_MakePoint(77.5746, 12.9664), 4326), FALSE),
('metro_kr_market', 'KR Market Metro Station', 'metro', 'Green Line', ST_SetSRID(ST_MakePoint(77.5748, 12.9604), 4326), FALSE),
('metro_national_college', 'National College Metro Station', 'metro', 'Green Line', ST_SetSRID(ST_MakePoint(77.5731, 12.9504), 4326), FALSE),
('metro_lalbagh', 'Lalbagh Metro Station', 'metro', 'Green Line', ST_SetSRID(ST_MakePoint(77.5800, 12.9460), 4326), FALSE),
('metro_jayanagar', 'Jayanagar Metro Station', 'metro', 'Green Line', ST_SetSRID(ST_MakePoint(77.5801, 12.9304), 4326), FALSE),
('metro_banashankari', 'Banashankari Metro Station', 'metro', 'Green Line', ST_SetSRID(ST_MakePoint(77.5736, 12.9155), 4326), TRUE),
('metro_jp_nagar', 'JP Nagar Metro Station', 'metro', 'Green Line', ST_SetSRID(ST_MakePoint(77.5735, 12.9073), 4326), FALSE),
('metro_silk_institute', 'Silk Institute Metro Station', 'metro', 'Green Line', ST_SetSRID(ST_MakePoint(77.5458, 12.8625), 4326), FALSE),
('bus_majestic_kbs', 'Kempegowda Bus Station (Majestic KBS)', 'bus', 'BMTC Hub', ST_SetSRID(ST_MakePoint(77.5713, 12.9772), 4326), TRUE),
('bus_corporation', 'Corporation Circle BMTC', 'bus', 'Trunk Bus', ST_SetSRID(ST_MakePoint(77.5898, 12.9678), 4326), FALSE),
('bus_richmond_circle', 'Richmond Circle Bus Stop', 'bus', 'Trunk Bus', ST_SetSRID(ST_MakePoint(77.5986, 12.9698), 4326), FALSE),
('bus_domlur_ttmc', 'Domlur TTMC Bus Station', 'bus', 'Radial Hub', ST_SetSRID(ST_MakePoint(77.6387, 12.9610), 4326), TRUE),
('bus_indiranagar_100ft', 'Indiranagar 100ft Road Bus Stop', 'bus', 'Trunk Bus', ST_SetSRID(ST_MakePoint(77.6415, 12.9745), 4326), FALSE),
('bus_marathahalli_bridge', 'Marathahalli Bridge Bus Stop', 'bus', 'ORR Hub', ST_SetSRID(ST_MakePoint(77.7011, 12.9562), 4326), TRUE),
('bus_bellandur_ecospace', 'Bellandur Ecospace Bus Stop', 'bus', 'ORR Hub', ST_SetSRID(ST_MakePoint(77.6845, 12.9260), 4326), FALSE),
('bus_hsr_layout_bd6', 'HSR Layout BDA Complex Bus Stop', 'bus', 'Trunk Bus', ST_SetSRID(ST_MakePoint(77.6388, 12.9115), 4326), FALSE),
('bus_central_silk_board', 'Central Silk Board Bus Interchange', 'bus', 'ORR Hub', ST_SetSRID(ST_MakePoint(77.6227, 12.9172), 4326), TRUE),
('bus_btm_layout_water_tank', 'BTM Layout Water Tank Bus Stop', 'bus', 'Trunk Bus', ST_SetSRID(ST_MakePoint(77.6101, 12.9166), 4326), FALSE),
('bus_jayadeva_hospital', 'Jayadeva Hospital Bus Stop', 'bus', 'Radial Bus', ST_SetSRID(ST_MakePoint(77.5979, 12.9181), 4326), FALSE),
('bus_banashankari_ttmc', 'Banashankari TTMC Bus Station', 'bus', 'TTMC Hub', ST_SetSRID(ST_MakePoint(77.5739, 12.9158), 4326), TRUE),
('bus_hebbal_flyover', 'Hebbal Flyover Bus Station', 'bus', 'ORR Hub', ST_SetSRID(ST_MakePoint(77.5970, 13.0358), 4326), TRUE),
('bus_kr_puram_railway', 'KR Puram Railway Station Bus Stop', 'bus', 'Trunk Bus', ST_SetSRID(ST_MakePoint(77.6765, 12.9995), 4326), FALSE),
('bus_tin_factory', 'Tin Factory (Kasturinagar) Bus Stop', 'bus', 'Trunk Bus', ST_SetSRID(ST_MakePoint(77.6660, 12.9930), 4326), FALSE),
('bus_whitefield_ttmc', 'Whitefield TTMC Bus Station', 'bus', 'Trunk Bus', ST_SetSRID(ST_MakePoint(77.7505, 12.9695), 4326), FALSE)
ON CONFLICT (id) DO NOTHING;

-- 2. Insert Routes
INSERT INTO transit_routes (id, short_name, long_name, mode, agency, fare_tier, headway_seconds) VALUES
('metro_purple_eastbound', 'Purple-E', 'Namma Metro Purple Line (Eastbound)', 'metro', 'BMRCL', 'metro_standard', 300),
('metro_purple_westbound', 'Purple-W', 'Namma Metro Purple Line (Westbound)', 'metro', 'BMRCL', 'metro_standard', 300),
('metro_green_southbound', 'Green-S', 'Namma Metro Green Line (Southbound)', 'metro', 'BMRCL', 'metro_standard', 360),
('metro_green_northbound', 'Green-N', 'Namma Metro Green Line (Northbound)', 'metro', 'BMRCL', 'metro_standard', 360),
('bmtc_500d_southbound', '500-D-S', 'BMTC Route 500-D (Hebbal to Silk Board)', 'bus', 'BMTC', 'bmtc_ordinary', 420),
('bmtc_500d_northbound', '500-D-N', 'BMTC Route 500-D (Silk Board to Hebbal)', 'bus', 'BMTC', 'bmtc_ordinary', 420),
('bmtc_335e_eastbound', '335-E-E', 'BMTC Route 335-E (Majestic to Whitefield)', 'bus', 'BMTC', 'bmtc_vajra', 600),
('bmtc_201_eastbound', '201-E', 'BMTC Route 201 (Banashankari to Indiranagar)', 'bus', 'BMTC', 'bmtc_ordinary', 720)
ON CONFLICT (id) DO NOTHING;

-- 3. Insert Transfer Edges
INSERT INTO transfer_edges (id, from_stop_id, to_stop_id, walking_distance_meters, walking_duration_sec, is_same_station) VALUES
('transfer_majestic_m2b', 'metro_majestic', 'bus_majestic_kbs', 220, 183, FALSE),
('transfer_majestic_b2m', 'bus_majestic_kbs', 'metro_majestic', 220, 183, FALSE),
('transfer_indiranagar_m2b', 'metro_indiranagar', 'bus_indiranagar_100ft', 450, 375, FALSE),
('transfer_indiranagar_b2m', 'bus_indiranagar_100ft', 'metro_indiranagar', 450, 375, FALSE),
('transfer_kr_puram_m2b', 'metro_kr_puram', 'bus_kr_puram_railway', 180, 150, FALSE),
('transfer_kr_puram_b2m', 'bus_kr_puram_railway', 'metro_kr_puram', 180, 150, FALSE),
('transfer_banashankari_m2b', 'metro_banashankari', 'bus_banashankari_ttmc', 90, 75, TRUE),
('transfer_banashankari_b2m', 'bus_banashankari_ttmc', 'metro_banashankari', 90, 75, TRUE),
('transfer_whitefield_m2b', 'metro_whitefield', 'bus_whitefield_ttmc', 80, 67, TRUE),
('transfer_whitefield_b2m', 'bus_whitefield_ttmc', 'metro_whitefield', 80, 67, TRUE)
ON CONFLICT (id) DO NOTHING;
