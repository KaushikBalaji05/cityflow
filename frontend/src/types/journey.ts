export type TransportMode = 'walk' | 'bus' | 'metro' | 'drive';

export type RoutingObjective =
  | 'fastest'
  | 'lowest_cost'
  | 'least_walking'
  | 'fewest_transfers'
  | 'balanced';

export interface Location {
  lat: number;
  lon: number;
  name?: string;
}

export interface RouteLeg {
  leg_index: number;
  mode: TransportMode;
  route_name: string;
  agency?: string;
  from_stop_id?: string;
  from_stop_name: string;
  from_lat: number;
  from_lon: number;
  to_stop_id?: string;
  to_stop_name: string;
  to_lat: number;
  to_lon: number;
  departure_time_offset_sec: number;
  arrival_time_offset_sec: number;
  duration_sec: number;
  distance_meters: number;
  waiting_time_sec: number;
  estimated_fare_inr: number;
  intermediate_stops: string[];
  polyline: [number, number][]; // [lon, lat]
  assumptions: string[];
}

export interface Journey {
  journey_id: string;
  objective: RoutingObjective;
  summary: string;
  total_duration_sec: number;
  total_walking_duration_sec: number;
  total_walking_distance_meters: number;
  total_waiting_time_sec: number;
  total_transfers: number;
  estimated_fare_inr: number;
  modes_used: TransportMode[];
  legs: RouteLeg[];
  is_live_adjusted: boolean;
  freshness_timestamp?: string;
  assumptions: string[];
}

export interface PlanRequest {
  origin: Location;
  destination: Location;
  departure_time_iso?: string;
  allowed_modes: TransportMode[];
  objective: RoutingObjective;
}

export interface PlanResponse {
  origin: Location;
  destination: Location;
  query_timestamp: string;
  journeys: Journey[];
  routing_metadata: Record<string, any>;
}

export interface StopItem {
  id: string;
  name: string;
  mode: string;
  line?: string;
  lat: number;
  lon: number;
  transfer_hub: boolean;
}
