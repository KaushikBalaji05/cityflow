import random
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from app.streaming.kafka_producer import CityFlowKafkaProducer, event_producer
from app.streaming.schemas import (
    CongestionLevel,
    DelayCause,
    TrafficEvent,
    TransitDelayEvent,
)


class BengaluruMobilitySimulator:
    """
    Synthetic real-time event generator simulating realistic urban mobility conditions,
    traffic surges, and public transit delays across Bengaluru corridors.
    """

    def __init__(self, producer: Optional[CityFlowKafkaProducer] = None):
        self.producer = producer or event_producer

        # Corridor segment definitions
        self.segments = [
            {
                "segment_id": "orr_silk_board_bellandur",
                "corridor_name": "Outer Ring Road (Silk Board to Marathahalli)",
                "free_flow_kmh": 45.0,
                "length_meters": 5200.0,
                "routes": [("bmtc_500d_northbound", "BMTC Route 500-D (Hebbal to Silk Board)", "bus_central_silk_board", "bus")]
            },
            {
                "segment_id": "orr_bellandur_marathahalli",
                "corridor_name": "Outer Ring Road (Silk Board to Marathahalli)",
                "free_flow_kmh": 45.0,
                "length_meters": 4800.0,
                "routes": [("bmtc_500d_southbound", "BMTC Route 500-D (Silk Board to Hebbal)", "bus_bellandur_ecospace", "bus")]
            },
            {
                "segment_id": "wf_itpl_hopefarm",
                "corridor_name": "Whitefield ITPL Corridor",
                "free_flow_kmh": 35.0,
                "length_meters": 3100.0,
                "routes": [
                    ("bmtc_335e_eastbound", "BMTC Route 335-E (Majestic to Kadugodi)", "bus_itpl_main_gate", "bus"),
                    ("metro_purple_eastbound", "Namma Metro Purple Line (Eastbound)", "metro_itpl", "metro")
                ]
            },
            {
                "segment_id": "wf_itpl_krpuram",
                "corridor_name": "Whitefield ITPL Corridor",
                "free_flow_kmh": 40.0,
                "length_meters": 5600.0,
                "routes": [("bmtc_335e_westbound", "BMTC Route 335-E (Kadugodi to Majestic)", "bus_kr_puram_railway", "bus")]
            },
            {
                "segment_id": "hosur_silkboard_bommanahalli",
                "corridor_name": "Hosur Road / Silk Board Corridor",
                "free_flow_kmh": 40.0,
                "length_meters": 2800.0,
                "routes": [("bmtc_g4_southbound", "BMTC Route G-4 (Brigade Rd to Electronic City)", "bus_central_silk_board", "bus")]
            },
            {
                "segment_id": "hosur_madiwala_silkboard",
                "corridor_name": "Hosur Road / Silk Board Corridor",
                "free_flow_kmh": 35.0,
                "length_meters": 2200.0,
                "routes": [("bmtc_201_eastbound", "BMTC Route 201 (Banashankari to Indiranagar)", "bus_central_silk_board", "bus")]
            },
            {
                "segment_id": "omr_indiranagar_svroad",
                "corridor_name": "Old Madras Road (Indiranagar to KR Puram)",
                "free_flow_kmh": 40.0,
                "length_meters": 2500.0,
                "routes": [
                    ("bmtc_335e_eastbound", "BMTC Route 335-E (Majestic to Kadugodi)", "bus_indiranagar_100ft", "bus"),
                    ("metro_purple_eastbound", "Namma Metro Purple Line (Eastbound)", "metro_indiranagar", "metro")
                ]
            },
            {
                "segment_id": "airport_hebbal_yelahanka",
                "corridor_name": "Hebbal Flyover / Airport Corridor",
                "free_flow_kmh": 60.0,
                "length_meters": 8500.0,
                "routes": [("bmtc_kia9_northbound", "BMTC Vayu Vajra KIA-9 (Majestic to Airport)", "bus_hebbal_flyover", "bus")]
            },
            {
                "segment_id": "cbd_majestic_corp",
                "corridor_name": "Central CBD (Majestic - MG Road)",
                "free_flow_kmh": 30.0,
                "length_meters": 2100.0,
                "routes": [("bmtc_365_southbound", "BMTC Route 365 (Majestic to Jayadeva)", "bus_majestic_kbs", "bus")]
            }
        ]

    def generate_events(
        self, scenario: Optional[str] = None
    ) -> Tuple[List[TrafficEvent], List[TransitDelayEvent]]:
        """
        Generates simulated traffic events and corresponding public transit delays.
        """
        scenario = (scenario or "normal").lower()
        now = datetime.now(timezone.utc)
        traffic_events: List[TrafficEvent] = []
        delay_events: List[TransitDelayEvent] = []

        for seg in self.segments:
            seg_id = seg["segment_id"]
            corridor = seg["corridor_name"]
            free_flow = seg["free_flow_kmh"]
            length = seg["length_meters"]

            # Compute simulated speed and congestion multiplier based on scenario
            if scenario == "silk_board_gridlock" and "silk_board" in seg_id:
                speed = random.uniform(5.0, 9.0)
                multiplier = free_flow / speed
                c_level = CongestionLevel.SEVERE
                cause = DelayCause.TRAFFIC_HOLD
                transit_delay = random.randint(900, 1500)  # 15-25 min delay
            elif scenario == "monsoon_rain" and ("orr" in seg_id or "hebbal" in seg_id):
                speed = random.uniform(10.0, 16.0)
                multiplier = free_flow / speed
                c_level = CongestionLevel.SEVERE
                cause = DelayCause.WEATHER_RAIN
                transit_delay = random.randint(600, 1200)
            elif scenario == "peak_evening":
                if "orr" in seg_id or "wf" in seg_id or "silkboard" in seg_id:
                    speed = random.uniform(12.0, 20.0)
                    multiplier = free_flow / speed
                    c_level = CongestionLevel.HIGH if speed > 15 else CongestionLevel.SEVERE
                    cause = DelayCause.TRAFFIC_HOLD
                    transit_delay = random.randint(300, 750)
                else:
                    speed = random.uniform(free_flow * 0.6, free_flow * 0.8)
                    multiplier = free_flow / speed
                    c_level = CongestionLevel.MODERATE
                    cause = DelayCause.TRAFFIC_HOLD
                    transit_delay = random.randint(60, 240)
            else:  # normal / off-peak
                speed = random.uniform(free_flow * 0.85, free_flow * 1.0)
                multiplier = max(1.0, free_flow / speed)
                c_level = CongestionLevel.LOW if multiplier < 1.25 else CongestionLevel.MODERATE
                cause = DelayCause.TRAFFIC_HOLD
                transit_delay = random.randint(0, 90)

            t_event = TrafficEvent(
                segment_id=seg_id,
                corridor_name=corridor,
                speed_kmh=round(speed, 1),
                free_flow_speed_kmh=free_flow,
                congestion_level=c_level,
                congestion_multiplier=round(multiplier, 2),
                length_meters=length,
                observed_at=now,
                source="bengaluru_mobility_simulator",
            )
            traffic_events.append(t_event)

            # Correlated public transit delays
            for route_id, route_name, stop_id, mode in seg.get("routes", []):
                # Metro is largely grade-separated; delays are minimal unless signal hold
                if mode == "metro":
                    d_sec = random.randint(0, 60) if scenario != "normal" else 0
                    m_cause = DelayCause.SIGNAL_FAILURE if d_sec > 0 else DelayCause.TRAFFIC_HOLD
                else:
                    d_sec = transit_delay
                    m_cause = cause

                d_event = TransitDelayEvent(
                    route_id=route_id,
                    route_name=route_name,
                    mode=mode,
                    stop_id=stop_id,
                    stop_name=stop_id.replace("_", " ").title(),
                    delay_seconds=d_sec,
                    cause=m_cause,
                    observed_at=now,
                )
                delay_events.append(d_event)

        return traffic_events, delay_events

    def tick(self, scenario: Optional[str] = None) -> Tuple[int, int]:
        """
        Executes one tick of simulation, generating and publishing events to Kafka / LiveState.
        Returns: (traffic_events_count, transit_delays_count)
        """
        traffic_events, delay_events = self.generate_events(scenario)

        for te in traffic_events:
            self.producer.publish_traffic_event(te)

        for de in delay_events:
            self.producer.publish_transit_delay(de)

        return len(traffic_events), len(delay_events)


# Global simulator instance
simulator = BengaluruMobilitySimulator()
