import argparse
import sys
import time
from datetime import datetime, timezone

from app.streaming.kafka_producer import CityFlowKafkaProducer
from app.streaming.simulator import BengaluruMobilitySimulator


def main():
    parser = argparse.ArgumentParser(description="CityFlow Kafka Event Streaming Producer for Bengaluru")
    parser.add_argument("--bootstrap-servers", type=str, default=None, help="Kafka bootstrap server(s)")
    parser.add_argument("--interval", type=float, default=2.0, help="Interval in seconds between ticks (default: 2.0s)")
    parser.add_argument(
        "--scenario",
        type=str,
        default="normal",
        choices=["normal", "peak_evening", "silk_board_gridlock", "monsoon_rain"],
        help="Mobility simulation scenario",
    )
    parser.add_argument("--count", type=int, default=10, help="Number of ticks to run (0 for infinite loop)")

    args = parser.parse_args()

    producer = CityFlowKafkaProducer(bootstrap_servers=args.bootstrap_servers, auto_connect=True)
    sim = BengaluruMobilitySimulator(producer=producer)

    print(f"================================================================")
    print(f"🚀 CityFlow Bengaluru Mobility Event Producer")
    print(f"   Kafka Broker: {producer.bootstrap_servers}")
    print(f"   Connected: {producer.is_connected()}")
    print(f"   Scenario: {args.scenario} | Interval: {args.interval}s")
    print(f"   Traffic Topic: {producer.traffic_topic}")
    print(f"   Delays Topic:  {producer.delay_topic}")
    print(f"================================================================")

    ticks_run = 0
    try:
        while True:
            t_count, d_count = sim.tick(scenario=args.scenario)
            producer.flush()
            ticks_run += 1
            now_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
            print(f"[{now_str}] Tick #{ticks_run:03d} -> Sent {t_count} traffic events, {d_count} transit delays")

            if args.count > 0 and ticks_run >= args.count:
                print(f"\n✅ Completed requested {args.count} simulation ticks.")
                break

            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n🛑 Streaming stopped by user.")
    finally:
        producer.close()
        print(f"Total events published: {producer.get_stats()}")


if __name__ == "__main__":
    main()
