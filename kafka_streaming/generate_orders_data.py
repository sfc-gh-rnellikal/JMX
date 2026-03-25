#!/usr/bin/env python3
"""
Generate random catalog return data matching the ORDERS_INTERACTIVE schema
and stream to Kafka at a configurable rate using multiple worker processes.

Target: ~25MB/sec sustained throughput into
  INTERACTIVE_DEMO.TPCH_INTERACTIVE.ORDERS_INTERACTIVE

Usage:
  python generate_orders_data.py --rate 33800 --duration 10
  python generate_orders_data.py --rate 33800 --target-mb 500
  python generate_orders_data.py --rate 6500 --target-mb 25 --workers 1
"""

import argparse
import json
import math
import multiprocessing
import os
import random
import signal
import sys
import time
from confluent_kafka import Producer

KAFKA_BOOTSTRAP_SERVERS = "localhost:29092"
TOPIC_NAME = "orders_data"

# Value ranges derived from actual data in ORDERS_INTERACTIVE
RANGES = {
    "CR_RETURNED_DATE_SK":       (2450867, 2452903),
    "CR_RETURNED_TIME_SK":       (0, 86399),
    "CR_ITEM_SK":                (157, 401671),
    "CR_REFUNDED_CUSTOMER_SK":   (1, 65000000),
    "CR_REFUNDED_CDEMO_SK":      (1, 1920800),
    "CR_REFUNDED_HDEMO_SK":      (1, 7200),
    "CR_REFUNDED_ADDR_SK":       (1, 32500000),
    "CR_RETURNING_CUSTOMER_SK":  (1, 65000000),
    "CR_RETURNING_CDEMO_SK":     (1, 1920800),
    "CR_RETURNING_HDEMO_SK":     (1, 7200),
    "CR_RETURNING_ADDR_SK":      (1, 32500000),
    "CR_CALL_CENTER_SK":         (1, 60),
    "CR_CATALOG_PAGE_SK":        (1, 2000),
    "CR_SHIP_MODE_SK":           (1, 20),
    "CR_WAREHOUSE_SK":           (1, 25),
    "CR_REASON_SK":              (1, 70),
    "CR_ORDER_NUMBER":           (572874, 1599025200),
    "CR_RETURN_QUANTITY":        (1, 100),
}

DECIMAL_RANGES = {
    "CR_RETURN_AMOUNT":       (0.00, 20860.80),
    "CR_RETURN_TAX":          (0.00, 1877.47),
    "CR_RETURN_AMT_INC_TAX":  (0.00, 22738.27),
    "CR_FEE":                 (0.00, 100.00),
    "CR_RETURN_SHIP_COST":    (0.00, 14340.16),
    "CR_REFUNDED_CASH":       (0.00, 20060.04),
    "CR_REVERSED_CHARGE":     (0.00, 14925.85),
    "CR_STORE_CREDIT":        (0.00, 13209.51),
    "CR_NET_LOSS":            (0.00, 16312.88),
}

# Pre-compute column names for faster record generation
INT_COLS = list(RANGES.keys())
INT_BOUNDS = [(RANGES[c][0], RANGES[c][1]) for c in INT_COLS]
DEC_COLS = list(DECIMAL_RANGES.keys())
DEC_BOUNDS = [(DECIMAL_RANGES[c][0], DECIMAL_RANGES[c][1]) for c in DEC_COLS]


def generate_record():
    record = {}
    for i, col in enumerate(INT_COLS):
        record[col] = random.randint(INT_BOUNDS[i][0], INT_BOUNDS[i][1])
    for i, col in enumerate(DEC_COLS):
        record[col] = round(random.uniform(DEC_BOUNDS[i][0], DEC_BOUNDS[i][1]), 2)
    return record


def create_producer():
    return Producer({
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "batch.num.messages": 10000,
        "linger.ms": 5,
        "queue.buffering.max.messages": 200000,
        "queue.buffering.max.kbytes": 131072,
        "compression.type": "lz4",
    })


def worker_process(worker_id, worker_rate, duration_seconds, target_bytes_per_worker,
                   stats_queue, stop_event):
    """Each worker runs its own Kafka producer at a fraction of the total rate."""
    random.seed(os.getpid() + worker_id)

    producer = create_producer()
    messages_sent = 0
    bytes_sent = 0
    start_time = time.time()
    end_time = start_time + duration_seconds if duration_seconds else None
    errors = 0

    def on_delivery(err, msg):
        nonlocal errors
        if err is not None:
            errors += 1

    try:
        while not stop_event.is_set():
            if end_time and time.time() >= end_time:
                break
            if target_bytes_per_worker and bytes_sent >= target_bytes_per_worker:
                break

            batch_start = time.time()

            for _ in range(worker_rate):
                if stop_event.is_set():
                    break
                if target_bytes_per_worker and bytes_sent >= target_bytes_per_worker:
                    break

                record = generate_record()
                payload = json.dumps(record).encode("utf-8")
                bytes_sent += len(payload)
                messages_sent += 1

                producer.produce(
                    TOPIC_NAME,
                    key=str(record["CR_ORDER_NUMBER"]),
                    value=payload,
                    callback=on_delivery,
                )

                if messages_sent % 5000 == 0:
                    producer.poll(0)

            producer.poll(0)

            # Pace to 1 second per batch
            batch_elapsed = time.time() - batch_start
            if batch_elapsed < 1.0:
                time.sleep(1.0 - batch_elapsed)

            # Report stats every second
            stats_queue.put((worker_id, messages_sent, bytes_sent, errors))

    finally:
        producer.flush(timeout=30)
        stats_queue.put((worker_id, messages_sent, bytes_sent, errors))


def run_generator(rate, target_mb=None, duration_minutes=None, num_workers=None):
    if num_workers is None:
        # Auto-select: ~8K msg/sec per worker is comfortable
        num_workers = max(1, math.ceil(rate / 8000))

    worker_rate = math.ceil(rate / num_workers)
    duration_seconds = duration_minutes * 60 if duration_minutes else None
    target_bytes = (target_mb * 1024 * 1024) if target_mb else None
    target_bytes_per_worker = math.ceil(target_bytes / num_workers) if target_bytes else None

    mode_desc = f"{target_mb}MB" if target_mb else f"{duration_minutes} min"
    mb_per_sec = rate * 776 / (1024 * 1024)  # ~776 bytes per record

    print(f"Starting data generation:")
    print(f"  Target rate:  {rate:,} msg/s (~{mb_per_sec:.1f} MB/s)")
    print(f"  Target:       {mode_desc}")
    print(f"  Workers:      {num_workers} (each ~{worker_rate:,} msg/s)")
    print(f"  Topic:        {TOPIC_NAME}")
    print(f"  Schema:       27 columns matching ORDERS_INTERACTIVE")
    print(f"Press Ctrl+C to stop early\n")

    stats_queue = multiprocessing.Queue()
    stop_event = multiprocessing.Event()

    # Handle Ctrl+C in parent
    original_sigint = signal.getsignal(signal.SIGINT)

    def parent_signal_handler(sig, frame):
        print("\nShutting down all workers...")
        stop_event.set()

    signal.signal(signal.SIGINT, parent_signal_handler)
    signal.signal(signal.SIGTERM, parent_signal_handler)

    workers = []
    start_time = time.time()

    for i in range(num_workers):
        p = multiprocessing.Process(
            target=worker_process,
            args=(i, worker_rate, duration_seconds, target_bytes_per_worker,
                  stats_queue, stop_event),
            daemon=True,
        )
        p.start()
        workers.append(p)

    # Aggregate stats from workers
    worker_stats = {}  # worker_id -> (messages, bytes, errors)
    try:
        while any(w.is_alive() for w in workers):
            # Drain the stats queue
            while not stats_queue.empty():
                try:
                    wid, msgs, bts, errs = stats_queue.get_nowait()
                    worker_stats[wid] = (msgs, bts, errs)
                except Exception:
                    break

            total_msgs = sum(s[0] for s in worker_stats.values())
            total_bytes = sum(s[1] for s in worker_stats.values())
            total_errors = sum(s[2] for s in worker_stats.values())
            elapsed = time.time() - start_time

            if elapsed > 0:
                actual_rate = total_msgs / elapsed
                mb_sent = total_bytes / (1024 * 1024)
                mb_rate = mb_sent / elapsed
                target_info = f" / {target_mb:.0f}MB" if target_mb else ""
                err_info = f" | Errors: {total_errors}" if total_errors else ""
                print(
                    f"\rMessages: {total_msgs:>10,} | "
                    f"Rate: {actual_rate:>8,.0f} msg/s | "
                    f"Throughput: {mb_rate:>5.1f} MB/s | "
                    f"Sent: {mb_sent:>8.1f}MB{target_info}{err_info}",
                    end="",
                )

            time.sleep(0.5)

    finally:
        stop_event.set()
        for w in workers:
            w.join(timeout=10)

        # Final drain
        while not stats_queue.empty():
            try:
                wid, msgs, bts, errs = stats_queue.get_nowait()
                worker_stats[wid] = (msgs, bts, errs)
            except Exception:
                break

        total_msgs = sum(s[0] for s in worker_stats.values())
        total_bytes = sum(s[1] for s in worker_stats.values())
        total_errors = sum(s[2] for s in worker_stats.values())
        total_time = time.time() - start_time
        mb_sent = total_bytes / (1024 * 1024)

        print(f"\n\nGeneration complete!")
        print(f"  Workers:         {num_workers}")
        print(f"  Total messages:  {total_msgs:,}")
        print(f"  Total data:      {mb_sent:.2f} MB")
        print(f"  Total time:      {total_time:.1f} seconds")
        print(f"  Average rate:    {total_msgs / total_time:,.0f} messages/second")
        print(f"  Avg throughput:  {mb_sent / total_time:.1f} MB/second")
        if total_errors:
            print(f"  Errors:          {total_errors:,}")

    signal.signal(signal.SIGINT, original_sigint)


def main():
    parser = argparse.ArgumentParser(
        description="Generate catalog return data and stream to Kafka"
    )
    parser.add_argument(
        "--rate", "-r",
        type=int,
        default=33800,
        help="Total messages per second across all workers (default: 33800 ≈ 25MB/s)",
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=None,
        help="Number of worker processes (default: auto, ~8K msg/s per worker)",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--target-mb",
        type=float,
        help="Stop after sending this many MB of data (e.g., 500)",
    )
    group.add_argument(
        "--duration", "-d",
        type=float,
        help="Duration to run in minutes (e.g., 10)",
    )

    args = parser.parse_args()

    if args.rate <= 0:
        print("Error: Rate must be positive")
        sys.exit(1)

    run_generator(args.rate, target_mb=args.target_mb,
                  duration_minutes=args.duration, num_workers=args.workers)


if __name__ == "__main__":
    main()
