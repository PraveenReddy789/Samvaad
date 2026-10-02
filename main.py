import os
import sys
import signal
import subprocess
import argparse
import asyncio
import uvicorn
from dotenv import load_dotenv

load_dotenv()

from backend.config import SERVER_HOST, SERVER_PORT
from backend.db.seed_db import seed_database
from backend.rag.indexer import load_and_index_all


def stop_service(ports=(8000, 8001, 8002)):
    """Finds and terminates any running instances of the server."""
    print("\n[i] Searching for running Collection Agent services...")
    killed_count = 0
    current_pid = os.getpid()

    for port in ports:
        try:
            cmd = f"lsof -ti :{port}"
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            pids = res.stdout.strip().split()
            for pid_str in pids:
                if pid_str:
                    pid = int(pid_str)
                    if pid != current_pid:
                        try:
                            os.kill(pid, signal.SIGTERM)
                            print(f"  ✓ Stopped process PID {pid} on port {port}")
                            killed_count += 1
                        except ProcessLookupError:
                            pass
                        except PermissionError:
                            print(f"  ⚠️ Could not stop PID {pid} (permission denied)")
        except Exception as e:
            print(f"  Error checking port {port}: {e}")

    if killed_count == 0:
        print("  • No active service found running on ports (8000-8002).")
    else:
        print(f"\n[✓] Successfully stopped {killed_count} process(es).\n")


def check_status(ports=(8000, 8001, 8002)):
    """Checks whether the backend server is currently running."""
    import urllib.request
    import json
    for port in ports:
        try:
            req = urllib.request.Request(f"http://localhost:{port}/api/health", headers={"User-Agent": "HealthCheck"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    print(f"\n[✓] Voice Collection Service is ONLINE on http://localhost:{port}")
                    print(f"    Health Status: {data}")
                    return True
        except Exception:
            pass
    print("\n[✕] Voice Collection Service is OFFLINE.")
    return False


async def run_interactive_cli(customer_id: str = "CUST001"):
    """Terminal CLI mode for testing recovery agent conversations."""
    from backend.agent.orchestrator import get_orchestrator
    from backend.db.tools import get_customer_account

    customer = get_customer_account(customer_id)
    if not customer:
        print(f"Customer {customer_id} not found in database. Run --seed first.")
        return

    orch = get_orchestrator()
    print("=" * 70)
    print(f"🎙️  Samvaad Voice Agent — Interactive Console")
    print(f"Active Customer: {customer['name']} ({customer['customer_id']})")
    print(f"Loan ID: {customer['loan_id']} | EMI: ₹{customer['emi_amount']:,.2f} | Status: {customer['status']}")
    print("Type your message (or 'exit' to quit):")
    print("=" * 70)

    session_id = f"cli_{customer_id}"
    while True:
        try:
            msg = input("\nCustomer > ").strip()
            if not msg or msg.lower() in ["exit", "quit", "q"]:
                print("Ending session.")
                break

            result = await orch.process_turn(customer_id, msg, session_id)
            print(f"\nAI Agent > {result['response']}")
            print(f"  [Intent: {result['intent']} | Outcome: {result['outcome']} | Latency: {result['turn_latency_ms']}ms]")
            if result["tool_executions"]:
                print(f"  [Tools: {result['tool_executions']}]")
            if result["citations"]:
                print(f"  [Citations: {len(result['citations'])} policy chunks]")
            if result.get("audio", {}).get("success"):
                print(f"  [Audio: Generated {result['audio']['filename']}]")

        except (KeyboardInterrupt, EOFError):
            print("\nExiting CLI.")
            break


def main():
    parser = argparse.ArgumentParser(description="Samvaad — Voice RAG Assistant Master Controller")
    parser.add_argument("--seed", action="store_true", help="Seed SQL database from customers.csv & payments.csv")
    parser.add_argument("--index", action="store_true", help="Ingest and index policies, SOPs, and products into Qdrant & BM25")
    parser.add_argument("--cli", action="store_true", help="Run interactive terminal CLI")
    parser.add_argument("--customer", default="CUST001", help="Customer ID for CLI mode (default: CUST001)")
    parser.add_argument("--status", action="store_true", help="Check server health status")
    parser.add_argument("--stop", action="store_true", help="Stop running backend server instances")
    parser.add_argument("--port", type=int, default=SERVER_PORT, help="Port to run server on")

    args = parser.parse_args()

    if args.stop:
        stop_service()
        return

    if args.status:
        check_status()
        return

    if args.seed:
        seed_database()
        return

    if args.index:
        load_and_index_all()
        return

    if args.cli:
        asyncio.run(run_interactive_cli(args.customer))
        return

    # Default action: Start the Web & API server
    print("\n" + "=" * 65)
    print("🚀 Starting Samvaad Voice RAG Assistant")
    print(f"   Dashboard UI: http://localhost:{args.port}/")
    print(f"   API Docs:     http://localhost:{args.port}/docs")
    print(f"   Metrics:      http://localhost:{args.port}/metrics")
    print("=" * 65 + "\n")

    uvicorn.run("backend.app:app", host=SERVER_HOST, port=args.port, reload=False)


if __name__ == "__main__":
    main()
