import argparse
import asyncio
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import time
import tomllib

from a2a.client import A2ACardResolver
from dotenv import load_dotenv
import httpx

load_dotenv(override=True)


async def wait_for_agents(cfg: dict, timeout: int = 30) -> bool:
    """Wait for all agents to be healthy and responding.

    Args:
        cfg: Configuration dictionary containing agent info.
        timeout: Maximum time to wait in seconds.
    Returns:
        True if all agents became ready within the timeout, False otherwise.
    """
    endpoints = []

    # --- Collect all endpoints to check ---

    # Green Agents, which are orchestrating benchmark
    if cfg["green_agent"].get("cmd"):
        endpoints.append(f"http://{cfg['green_agent']['host']}:{cfg['green_agent']['port']}")

    # Purple Agents, which are responsible for solving tasks
    for p in cfg["participants"]:
        if p.get("cmd"):
            endpoints.append(f"http://{p['host']}:{p['port']}")

    if not endpoints:
        print("No agents to wait for (no 'cmd' specified for any agent). Skipping wait.")
        return True  # No agents to wait for

    print(f"Waiting for {len(endpoints)} agent(s) to be ready...")
    start_time = time.time()

    # --- end ---

    async def check_endpoint(endpoint: str) -> bool:
        """Check if an endpoint is responding by fetching the agent card."""
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                resolver = A2ACardResolver(httpx_client=client, base_url=endpoint)
                await resolver.get_agent_card()
                return True
        except Exception:
            # Any exception means the agent is not ready
            # print(f"  --- DEBUG: Endpoint {endpoint} check failed: {type(e).__name__}: {e}")
            return False

    while time.time() - start_time < timeout:
        ready_count = 0
        current_ready_endpoints = []

        for endpoint in endpoints:
            if await check_endpoint(endpoint):
                ready_count += 1
                current_ready_endpoints.append(endpoint)

        if ready_count == len(endpoints):
            print(f"All {len(endpoints)} agents ready.")
            return True

        print(f"  {ready_count}/{len(endpoints)} agents ready, waiting...")
        await asyncio.sleep(1)

    print(f"Timeout: Only {ready_count}/{len(endpoints)} agents became ready after {timeout}s")
    if ready_count < len(endpoints):
        unready_endpoints = [ep for ep in endpoints if ep not in current_ready_endpoints]
        print(f"  List of unready endpoints at timeout: {unready_endpoints}")

    return False


def parse_toml(scenario_path: str) -> dict:
    """Parse the scenario TOML file and return configuration dictionary.
    Args:
        scenario_path: Path to the scenario TOML file.
    Returns:
        Configuration dictionary with green agent, participants, and config.
    """
    path = Path(scenario_path)
    if not path.exists():
        print(f"Error: Scenario file not found: {path}")
        sys.exit(1)

    data = tomllib.loads(path.read_text())

    def host_port(ep: str):
        """Export endpoint into host and port."""
        s = ep or ""
        s = s.replace("http://", "").replace("https://", "")
        s = s.split("/", 1)[0]
        host_str, port_str = s.split(":", 1)
        return host_str, int(port_str)

    # Green Agent
    green_ep = data.get("green_agent", {}).get("endpoint", "")
    g_host, g_port = host_port(green_ep)
    green_cmd = data.get("green_agent", {}).get("cmd", "")

    # Purple Agents (participants)
    parts = []
    for p in data.get("participants", []):
        if isinstance(p, dict) and "endpoint" in p:
            h, pt = host_port(p["endpoint"])
            parts.append(
                {"role": str(p.get("role", "")), "host": h, "port": pt, "cmd": p.get("cmd", "")}
            )

    cfg = data.get("config", {})
    return {
        "green_agent": {"host": g_host, "port": g_port, "cmd": green_cmd},
        "participants": parts,
        "config": cfg,
    }


def main():
    """Main function to run the agent scenario."""

    #--- Parse command-line arguments ---
    parser = argparse.ArgumentParser(description="Run agent scenario")
    parser.add_argument("scenario", help="Path to scenario TOML file")
    parser.add_argument("--show-logs", action="store_true", help="Show agent stdout/stderr")
    parser.add_argument(
        "--serve-only",
        action="store_true",
        help="Start agent servers only without running evaluation",
    )
    args = parser.parse_args()
    #--- end ---

    # read scenario, including Green and Purple agent information and config
    cfg = parse_toml(args.scenario)

    # process other arguments
    sink = None if args.show_logs or args.serve_only else subprocess.DEVNULL
    parent_bin = str(Path(sys.executable).parent)
    base_env = os.environ.copy()
    base_env["PATH"] = parent_bin + os.pathsep + base_env.get("PATH", "")

    procs = []
    try:
        # start green agent first
        green_cmd_args = shlex.split(cfg["green_agent"].get("cmd", ""))
        if green_cmd_args:
            print(
                f"Starting green agent at {cfg['green_agent']['host']}:{cfg['green_agent']['port']}"
            )
            procs.append(
                subprocess.Popen(
                    green_cmd_args,
                    env=base_env,
                    stdout=sink,
                    stderr=sink,
                    text=True,
                    start_new_session=True,
                )
            )

        # start participant agents
        for p in cfg["participants"]:
            cmd_args = shlex.split(p.get("cmd", ""))
            if cmd_args:
                print(f"Starting {p['role']} at {p['host']}:{p['port']}")
                procs.append(
                    subprocess.Popen(
                        cmd_args,
                        env=base_env,
                        stdout=sink,
                        stderr=sink,
                        text=True,
                        start_new_session=True,
                    )
                )

        # Wait for all agents to be ready
        if not asyncio.run(wait_for_agents(cfg)):
            print("Error: Not all agents became ready. Exiting.")
            return

        print("Agents started. Press Ctrl+C to stop.")
        if args.serve_only:
            # Just launch Green and Purple agent A2A servers and wait
            while True:
                for proc in procs:
                    if proc.poll() is not None:
                        print(f"Agent exited with code {proc.returncode}")
                        break
                    time.sleep(0.5)
        else:
            # Run evaluation scenario
            client_proc = subprocess.Popen(
                [sys.executable, "-m", "fieldworkarena.agent.client", args.scenario],
                env=base_env,
                start_new_session=True,
            )
            procs.append(client_proc)
            client_proc.wait()

    except KeyboardInterrupt:
        pass

    finally:
        print("\nShutting down...")
        # Graceful shutdown (SIGTERM on Unix, terminate on Windows)
        for p in procs:
            if p.poll() is None:
                try:
                    if sys.platform == "win32":
                        p.terminate()  # Windows
                        print(f"Sent terminate signal to process {p.pid}")
                    else:
                        os.killpg(p.pid, signal.SIGTERM)  # Unix/Linux
                        print(f"Sent SIGTERM to process group {p.pid}")
                except (ProcessLookupError, AttributeError):
                    print(f"Process {p.pid} already terminated.")
                    pass
        
        time.sleep(1)  # Wait for graceful shutdown
        
        # Forceful shutdown (SIGKILL on Unix, kill on Windows)
        for p in procs:
            if p.poll() is None:
                try:
                    if sys.platform == "win32":
                        p.kill()  # Windows
                        print(f"Sent kill signal to process {p.pid}")
                    else:
                        os.killpg(p.pid, signal.SIGKILL)  # Unix/Linux
                        print(f"Sent SIGKILL to process group {p.pid}")
                except (ProcessLookupError, AttributeError):
                    print(f"Process {p.pid} already terminated.")
                    pass
        print("Shutdown complete.")


if __name__ == "__main__":
    main()
