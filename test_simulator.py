import sys
import asyncio
sys.path.append("/Users/anassiddiqui/Downloads/NemoGuard/pipeline-copilot/simulator_backend")
from main import simulate_failure

async def test():
    try:
        gen = simulate_failure("CASCADING_FAILURE")
        async for chunk in gen:
            print(chunk)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(test())
