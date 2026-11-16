import json
import logging
from typing import Any, Dict, Optional

from app.core.config import settings
from app.streaming.live_state import live_state
from app.streaming.schemas import TrafficEvent, TransitDelayEvent

logger = logging.getLogger("cityflow.streaming.kafka")


class CityFlowKafkaProducer:
    """
    Kafka event producer for Bengaluru urban mobility events.
    Supports Kafka cluster connections with graceful in-memory fallback.
    """

    def __init__(
        self,
        bootstrap_servers: Optional[str] = None,
        client_id: Optional[str] = None,
        auto_connect: bool = True,
    ):
        self.bootstrap_servers = bootstrap_servers or settings.KAFKA_BOOTSTRAP_SERVERS
        self.client_id = client_id or settings.KAFKA_CLIENT_ID
        self.traffic_topic = settings.KAFKA_TRAFFIC_TOPIC
        self.delay_topic = settings.KAFKA_TRANSIT_DELAY_TOPIC

        self._producer = None
        self._connected = False
        self._published_traffic_count = 0
        self._published_delay_count = 0

        if auto_connect:
            self.connect()

    def connect(self) -> bool:
        """
        Attempts to initialize real Kafka producer; falls back to in-memory state if unavailable.
        """
        try:
            # Attempt to import kafka-python or kafka
            from kafka import KafkaProducer  # type: ignore

            self._producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers.split(","),
                client_id=self.client_id,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                request_timeout_ms=3000,
                max_block_ms=3000,
                retries=2,
            )
            self._connected = True
            logger.info("Connected to Kafka broker at %s", self.bootstrap_servers)
            return True
        except Exception as e:
            logger.warning(
                "Kafka broker unavailable (%s). Running in resilient in-memory streaming fallback mode.",
                e,
            )
            self._producer = None
            self._connected = False
            return False

    def is_connected(self) -> bool:
        return self._connected and (self._producer is not None)

    def publish_traffic_event(self, event: TrafficEvent) -> bool:
        """
        Publishes traffic event to Kafka topic and updates the live mobility cache.
        """
        # Always update local live state cache
        live_state.record_traffic_event(event)
        self._published_traffic_count += 1

        payload = event.model_dump(mode="json")
        key = event.segment_id

        if self.is_connected():
            try:
                self._producer.send(self.traffic_topic, key=key, value=payload)
                return True
            except Exception as e:
                logger.error("Failed to send traffic event to Kafka topic %s: %s", self.traffic_topic, e)
                return False

        # In fallback mode, returns true since event was successfully processed in memory
        return True

    def publish_transit_delay(self, event: TransitDelayEvent) -> bool:
        """
        Publishes transit delay event to Kafka topic and updates the live mobility cache.
        """
        # Always update local live state cache
        live_state.record_transit_delay(event)
        self._published_delay_count += 1

        payload = event.model_dump(mode="json")
        key = event.route_id

        if self.is_connected():
            try:
                self._producer.send(self.delay_topic, key=key, value=payload)
                return True
            except Exception as e:
                logger.error("Failed to send transit delay event to Kafka topic %s: %s", self.delay_topic, e)
                return False

        return True

    def flush(self) -> None:
        if self.is_connected():
            try:
                self._producer.flush(timeout=2.0)
            except Exception as e:
                logger.warning("Error flushing Kafka producer: %s", e)

    def close(self) -> None:
        if self._producer:
            try:
                self._producer.close(timeout=2.0)
            except Exception:
                pass
            self._producer = None
            self._connected = False

    def get_stats(self) -> Dict[str, Any]:
        return {
            "connected_to_kafka": self.is_connected(),
            "bootstrap_servers": self.bootstrap_servers,
            "topics": {
                "traffic": self.traffic_topic,
                "transit_delays": self.delay_topic,
            },
            "total_traffic_events_published": self._published_traffic_count,
            "total_transit_delays_published": self._published_delay_count,
            "in_memory_buffer_size": len(live_state._traffic_events) + len(live_state._transit_delay_events),
        }


# Global producer instance
event_producer = CityFlowKafkaProducer(auto_connect=False)
