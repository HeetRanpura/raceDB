import argparse
import json
import uuid
import sys
from pprint import pprint

from engine.scheduler import run_debug_deterministic
from engine.benchmark_runner import run_benchmark

def main():
    parser = argparse.ArgumentParser(description="RaceDB CLI Tool for Concurrency Testing")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # RUN command (Deterministic Scenarios)
    run_parser = subparsers.add_parser("run", help="Run a predefined debug scenario")
    run_parser.add_argument("file", type=str, help="Path to scenario JSON file")
    run_parser.add_argument("--isolation", type=str, default="REPEATABLE READ", help="Isolation level")

    # BENCHMARK command
    bench_parser = subparsers.add_parser("benchmark", help="Run a concurrent load benchmark")
    bench_parser.add_argument("--transactions", type=int, default=100, help="Total transactions")
    bench_parser.add_argument("--concurrency", type=int, default=10, help="Thread concurrency")
    bench_parser.add_argument("--pattern", type=str, default="mixed", choices=["read-heavy", "write-heavy", "mixed"])
    bench_parser.add_argument("--isolation", type=str, default="READ COMMITTED", help="Isolation level")

    args = parser.parse_args()

    if args.command == "run":
        try:
            with open(args.file, "r") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error loading scenario: {e}")
            sys.exit(1)

        print(f"Running Scenario: {args.file} under {args.isolation}")
        res = run_debug_deterministic(data["transactions"], args.isolation)
        
        print("\n--- RESULTS ---")
        for s in res["steps"]:
            latency = f"{s['latency_ms']}ms" if s['latency_ms'] else ""
            print(f"[{s['status']}] {s['txn_id']} Step {s['step']}: {s['query']}  ({latency})")
            
        if res["anomalies"]:
            print("\n--- ANOMALIES DETECTED ---")
            for a in res["anomalies"]:
                print(f"WARNING: {a['type']} - {a['description']}")
        else:
            print("\n✔️ No anomalies detected.")
            
    elif args.command == "benchmark":
        print(f"Running Benchmark ({args.transactions} txns, {args.concurrency} threads, {args.pattern}) under {args.isolation}")
        res = run_benchmark(args.transactions, args.concurrency, args.pattern, args.isolation)
        
        print("\n--- BENCHMARK RESULTS ---")
        print(f"Total:      {res['total_transactions']}")
        print(f"Success:    {res['successful']}")
        print(f"Aborted:    {res['aborted']}")
        print(f"Deadlocks:  {res['deadlocks']}")
        print(f"P50 Latency: {res['p50_latency_ms']}ms")
        print(f"P95 Latency: {res['p95_latency_ms']}ms")
        print(f"Throughput: {res['throughput_tps']} tps")
        
        if res["anomalies"]:
            print(f"\nANOMALIES DETECTED: {len(res['anomalies'])}")
            for a in res["anomalies"][:5]:
                print(f"  - {a['type']}: {a['description']}")
            if len(res["anomalies"]) > 5:
                print("  ... (truncated)")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
