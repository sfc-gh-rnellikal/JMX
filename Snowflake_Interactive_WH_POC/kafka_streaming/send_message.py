#!/usr/bin/env python3
"""
Send a single test record to the orders_data Kafka topic.
Used for end-to-end connectivity verification before running the full generator.

Usage:
  python send_message.py
  python send_message.py --json '{"CR_RETURNED_DATE_SK": 2452900, ...}'
"""

import sys
import json
import random
import argparse
from datetime import datetime, timezone
from kafka import KafkaProducer

KAFKA_BOOTSTRAP_SERVERS = "localhost:29092"
TOPIC_NAME = "orders_data"


def create_producer():
    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k else None,
    )


def generate_sample_record():
    """Generate a single record matching ORDERS_INTERACTIVE schema."""
    return {
        "CR_RETURNED_DATE_SK": 2452920,
        "CR_RETURNED_TIME_SK": 43200,
        "CR_ITEM_SK": 150000,
        "CR_REFUNDED_CUSTOMER_SK": 12345678,
        "CR_REFUNDED_CDEMO_SK": 500000,
        "CR_REFUNDED_HDEMO_SK": 3000,
        "CR_REFUNDED_ADDR_SK": 5000000,
        "CR_RETURNING_CUSTOMER_SK": 12345678,
        "CR_RETURNING_CDEMO_SK": 500000,
        "CR_RETURNING_HDEMO_SK": 3000,
        "CR_RETURNING_ADDR_SK": 5000000,
        "CR_CALL_CENTER_SK": 25,
        "CR_CATALOG_PAGE_SK": 500,
        "CR_SHIP_MODE_SK": 10,
        "CR_WAREHOUSE_SK": 12,
        "CR_REASON_SK": 35,
        "CR_ORDER_NUMBER": random.randint(1600000000, 1700000000),
        "CR_RETURN_QUANTITY": 5,
        "CR_RETURN_AMOUNT": 125.50,
        "CR_RETURN_TAX": 10.04,
        "CR_RETURN_AMT_INC_TAX": 135.54,
        "CR_FEE": 3.25,
        "CR_RETURN_SHIP_COST": 15.00,
        "CR_REFUNDED_CASH": 75.30,
        "CR_REVERSED_CHARGE": 25.10,
        "CR_STORE_CREDIT": 25.10,
        "CR_NET_LOSS": 18.25,
        "INSERTED_AT": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3],
    }


def send_message(message):
    producer = create_producer()
    key = str(message.get("CR_ORDER_NUMBER", "UNKNOWN"))

    try:
        future = producer.send(TOPIC_NAME, key=key, value=message)
        record_metadata = future.get(timeout=10)
        print(f"Message sent successfully!")
        print(f"  Topic:     {record_metadata.topic}")
        print(f"  Partition: {record_metadata.partition}")
        print(f"  Offset:    {record_metadata.offset}")
        print(f"  Key:       {key}")
        print(f"  Size:      {len(json.dumps(message).encode('utf-8'))} bytes")
    except Exception as e:
        print(f"Error sending message: {e}")
        sys.exit(1)
    finally:
        producer.close()


def main():
    parser = argparse.ArgumentParser(
        description="Send a single test record to the orders_data Kafka topic"
    )
    parser.add_argument(
        "--json",
        type=str,
        default=None,
        help="Custom JSON record to send (must match ORDERS_INTERACTIVE schema)",
    )
    args = parser.parse_args()

    if args.json:
        try:
            message = json.loads(args.json)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON - {e}")
            sys.exit(1)
    else:
        message = generate_sample_record()
        print("Using generated sample record:")
        print(json.dumps(message, indent=2))
        print()

    send_message(message)
    print()
    print("Next: Check Snowflake in ~10 seconds:")
    print("  SELECT * FROM INTERACTIVE_DEMO.TPCH_INTERACTIVE.ORDERS_INTERACTIVE")
    print("  WHERE CR_ORDER_NUMBER = " + str(message.get("CR_ORDER_NUMBER", "?")))


if __name__ == "__main__":
    main()
