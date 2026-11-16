import argparse
import json
import sys
from app.core.config import settings


def main():
    parser = argparse.ArgumentParser(description="Inspect CityFlow Kafka Stream Events")
    parser.add_argument("--bootstrap-servers", type=str, default=settings.KAFKA_BOOTSTRAP_SERVERS)
    parser.add_argument("--topic", type=str, default=settings.KAFKA_TRAFFIC_TOPIC)
    parser.add_argument("--limit", type=int, default=10)

    args = parser.parse_args()

    print(f"Connecting to Kafka at {args.bootstrap_servers} on topic {args.topic}...")
    try:
        from kafka import KafkaConsumer  # type: ignore

        consumer = KafkaConsumer(
            args.topic,
            bootstrap_servers=args.bootstrap_servers.split(","),
            auto_offset_reset="earliest",
            consumer_timeout_ms=5000,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        )
        count = 0
        for msg in consumer:
            print(f"[{msg.topic} P:{msg.partition} O:{msg.offset}] Key: {msg.key.decode('utf-8') if msg.key else None}")
            print(json.dumps(msg.value, indent=2))
            count += 1
            if count >= args.limit:
                break
        print(f"\nRead {count} message(s).")
    except Exception as e:
        print(f"Could not read from Kafka broker: {e}")
        print("Tip: Start the Kafka container with `docker compose up -d kafka` or query the `/api/v1/live/events` endpoint.")


if __name__ == "__main__":
    main()
