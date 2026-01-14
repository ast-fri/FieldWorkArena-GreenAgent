"""
Integration tests for FWAGreenAgent.

These tests start actual agent servers and test the full evaluation flow.
Run with: uv run pytest tests/agent/test_fwa_green_agent.py -v

Environment Variables:
    FWA_TEST_TOKEN: API token for testing (required for integration tests)
"""
import asyncio
import os
import pytest
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import httpx
from a2a.client import A2ACardResolver

# Get the fixtures directory path
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "scenarios" / "fwa"
SCENARIO_TEMPLATE_PATH = FIXTURES_DIR / "scenario.toml"


pytestmark = pytest.mark.integration


def create_test_scenario_file() -> Path:
    """Create a temporary scenario.toml with token from environment variable.
    
    Returns:
        Path to the temporary scenario file.
        
    Raises:
        pytest.skip: If FWA_TEST_TOKEN is not set.
    """
    token = os.environ.get("FWA_TEST_TOKEN")
    if not token:
        pytest.skip("FWA_TEST_TOKEN environment variable not set. Set it to run integration tests.")
    
    # Read the template scenario file
    with open(SCENARIO_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        scenario_content = f.read()
    
    # Replace the empty token with the actual token
    scenario_content = scenario_content.replace('token=""', f'token="{token}"')
    
    # Create a temporary file
    temp_file = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".toml",
        delete=False,
        encoding="utf-8"
    )
    temp_file.write(scenario_content)
    temp_file.close()
    
    return Path(temp_file.name)


async def wait_for_agent(endpoint: str, timeout: int = 30) -> bool:
    """Wait for an agent to be ready."""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                resolver = A2ACardResolver(httpx_client=client, base_url=endpoint)
                await resolver.get_agent_card()
                return True
        except Exception:
            await asyncio.sleep(0.5)
    
    return False


@pytest.fixture
async def green_agent_server():
    """Start the Green Agent server for testing."""
    parent_bin = str(Path(sys.executable).parent)
    env = os.environ.copy()
    env["PATH"] = parent_bin + os.pathsep + env.get("PATH", "")
    
    # Start green agent with output capture for debugging
    proc = subprocess.Popen(
        ["fwa-server", "--host", "127.0.0.1", "--port", "9009"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        text=True,
    )
    
    # Wait for agent to be ready
    ready = await wait_for_agent("http://127.0.0.1:9009", timeout=30)
    
    if not ready:
        proc.terminate()
        stdout, stderr = proc.communicate(timeout=5)
        pytest.fail(f"Green agent failed to start\nstdout: {stdout}\nstderr: {stderr}")
    
    yield proc
    
    # Cleanup
    try:
        if sys.platform == "win32":
            proc.terminate()
        else:
            os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=5)
    except Exception:
        if sys.platform == "win32":
            proc.kill()
        else:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                pass


@pytest.fixture
async def purple_agent_server():
    """Start the test Purple Agent server."""
    parent_bin = str(Path(sys.executable).parent)
    env = os.environ.copy()
    env["PATH"] = parent_bin + os.pathsep + env.get("PATH", "")
    
    test_agent_path = FIXTURES_DIR / "purple_agent" / "test_agent.py"
    
    # Start purple agent
    proc = subprocess.Popen(
        [sys.executable, str(test_agent_path), "--host", "127.0.0.1", "--port", "9019"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    
    # Wait for agent to be ready
    ready = await wait_for_agent("http://127.0.0.1:9019", timeout=30)
    
    if not ready:
        proc.terminate()
        proc.wait()
        pytest.fail("Purple agent failed to start")
    
    yield proc
    
    # Cleanup
    try:
        if sys.platform == "win32":
            proc.terminate()
        else:
            os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=5)
    except Exception:
        if sys.platform == "win32":
            proc.kill()
        else:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                pass


@pytest.mark.asyncio
async def test_green_agent_evaluation(green_agent_server, purple_agent_server):
    """Test full evaluation flow with Green and Purple agents.
    
    Requires FWA_TEST_TOKEN environment variable to be set.
    """
    # Create temporary scenario file with token from environment
    scenario_path = create_test_scenario_file()
    
    try:
        # Give agents a moment to fully initialize
        await asyncio.sleep(2)
        
        # Run the client to send evaluation request
        parent_bin = str(Path(sys.executable).parent)
        env = os.environ.copy()
        env["PATH"] = parent_bin + os.pathsep + env.get("PATH", "")
        
        print("Starting evaluation client...")
        client_proc = subprocess.Popen(
            [sys.executable, "-m", "fieldworkarena.agent.client", str(scenario_path)],
            env=env,
            stdout=None,
            stderr=None,
            text=True,
        )
        
        try:
            # Wait for client to complete (increased timeout for complex evaluations)
            print(f"Waiting for evaluation to complete (timeout: 180s)...")
            returncode = client_proc.wait(timeout=180)
            
            # Check that the evaluation completed successfully
            assert returncode == 0, f"Client failed with return code {returncode}"
            
        except subprocess.TimeoutExpired:
            client_proc.kill()
            pytest.fail("Evaluation timed out")
    finally:
        # Clean up temporary file
        if scenario_path.exists():
            scenario_path.unlink()


@pytest.mark.asyncio
async def test_green_agent_card():
    """Test that Green Agent returns a valid agent card."""
    # This test doesn't need the full setup, just checks the agent card
    parent_bin = str(Path(sys.executable).parent)
    env = os.environ.copy()
    env["PATH"] = parent_bin + os.pathsep + env.get("PATH", "")
    
    proc = subprocess.Popen(
        ["fwa-server", "--host", "127.0.0.1", "--port", "9010"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        text=True,
    )
    
    try:
        ready = await wait_for_agent("http://127.0.0.1:9010", timeout=30)
        if not ready:
            proc.terminate()
            stdout, stderr = proc.communicate(timeout=5)
            pytest.fail(f"Green agent failed to start\nstdout: {stdout}\nstderr: {stderr}")
        
        # Get agent card
        async with httpx.AsyncClient() as client:
            resolver = A2ACardResolver(httpx_client=client, base_url="http://127.0.0.1:9010")
            card = await resolver.get_agent_card()
            
            assert card is not None
            assert card.name is not None
            assert "FWA" in card.name or "Field" in card.name
            
    finally:
        try:
            if sys.platform == "win32":
                proc.terminate()
            else:
                os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=5)
        except Exception:
            if sys.platform == "win32":
                proc.kill()
            else:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except Exception:
                    pass
