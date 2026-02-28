#!/usr/bin/env python
"""
Test script to verify the sandbox server is working correctly.

Run this script to test the sandbox setup:
    python test_sandbox.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from my_agent.helpers.sandbox_client import (
    check_server_health,
    execute_code_via_server,
    install_package_via_server,
)


async def test_health_check():
    """Test 1: Health check"""
    print("=" * 70)
    print("Test 1: Health Check")
    print("=" * 70)

    healthy = await check_server_health()
    if healthy:
        print("✅ Health check passed!\n")
        return True
    else:
        print("❌ Health check failed!")
        print("\nMake sure the sandbox server is running:")
        print("  python run_sandbox_server.py\n")
        return False


async def test_simple_execution():
    """Test 2: Simple code execution"""
    print("=" * 70)
    print("Test 2: Simple Code Execution")
    print("=" * 70)

    code = "print('Hello from sandbox!')"
    print(f"Executing: {code}")

    result = await execute_code_via_server(code)

    if result["success"]:
        print(f"✅ Execution successful!")
        print(f"Output: {result['output']}")
        return True
    else:
        print(f"❌ Execution failed!")
        print(f"Error: {result['error']}")
        return False


async def test_pandas_execution():
    """Test 3: Pandas DataFrame creation"""
    print("\n" + "=" * 70)
    print("Test 3: Pandas DataFrame Creation")
    print("=" * 70)

    code = """
import pandas as pd
df = pd.DataFrame({
    'name': ['Alice', 'Bob', 'Charlie'],
    'age': [25, 30, 35],
    'city': ['NYC', 'SF', 'LA']
})
print(df)
print(f"\\nShape: {df.shape}")
"""
    print("Creating a pandas DataFrame...")

    result = await execute_code_via_server(code)

    if result["success"]:
        print(f"✅ Pandas execution successful!")
        print(f"Output:\n{result['output']}")

        if result["tables"]:
            print(f"\n📊 Auto-detected {len(result['tables'])} table(s)")

        return True
    else:
        print(f"❌ Execution failed!")
        print(f"Error: {result['error']}")
        return False


async def test_persistence():
    """Test 4: State persistence across executions"""
    print("\n" + "=" * 70)
    print("Test 4: State Persistence")
    print("=" * 70)

    # First execution: create variable
    code1 = "x = 42\nprint(f'x = {x}')"
    print(f"Step 1: {code1}")

    result1 = await execute_code_via_server(code1)

    if not result1["success"]:
        print(f"❌ Step 1 failed: {result1['error']}")
        return False

    print(f"✅ Step 1 output: {result1['output']}")

    # Second execution: use variable from first execution
    code2 = "y = x * 2\nprint(f'y = x * 2 = {y}')"
    print(f"Step 2: {code2}")

    result2 = await execute_code_via_server(code2)

    if result2["success"]:
        print(f"✅ Step 2 output: {result2['output']}")
        print("✅ State persistence working!")
        return True
    else:
        print(f"❌ Step 2 failed: {result2['error']}")
        return False


async def test_package_installation():
    """Test 5: Package installation (optional - takes time)"""
    print("\n" + "=" * 70)
    print("Test 5: Package Installation (Optional)")
    print("=" * 70)

    response = input("Do you want to test package installation? (y/n): ")

    if response.lower() != 'y':
        print("⏭️  Skipping package installation test")
        return True

    print("Installing 'requests' package...")

    result = await install_package_via_server("requests")

    if result["success"]:
        print(f"✅ Package installed successfully!")

        # Try importing it
        code = "import requests\nprint(f'requests version: {requests.__version__}')"
        exec_result = await execute_code_via_server(code)

        if exec_result["success"]:
            print(f"✅ Import successful: {exec_result['output']}")
            return True
        else:
            print(f"❌ Import failed: {exec_result['error']}")
            return False
    else:
        print(f"❌ Installation failed!")
        print(f"Error: {result['error']}")
        return False


async def test_matplotlib():
    """Test 6: Matplotlib plotting"""
    print("\n" + "=" * 70)
    print("Test 6: Matplotlib Plotting")
    print("=" * 70)

    code = """
import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(0, 2 * np.pi, 100)
y = np.sin(x)

plt.figure(figsize=(10, 6))
plt.plot(x, y)
plt.title('Sine Wave')
plt.xlabel('x')
plt.ylabel('sin(x)')
plt.grid(True)

print('Plot created!')
"""

    print("Creating a sine wave plot...")

    result = await execute_code_via_server(code)

    if result["success"]:
        print(f"✅ Plot creation successful!")
        print(f"Output: {result['output']}")

        if result["plots"]:
            print(f"📊 Saved {len(result['plots'])} plot(s):")
            for plot_path in result["plots"]:
                print(f"  - {plot_path}")

        return True
    else:
        print(f"❌ Plot creation failed!")
        print(f"Error: {result['error']}")
        return False


async def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("🧪 SANDBOX SERVER TEST SUITE")
    print("=" * 70)
    print()

    tests = [
        ("Health Check", test_health_check),
        ("Simple Execution", test_simple_execution),
        ("Pandas Execution", test_pandas_execution),
        ("State Persistence", test_persistence),
        ("Package Installation", test_package_installation),
        ("Matplotlib Plotting", test_matplotlib),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            # Stop after health check fails
            if test_name != "Health Check" and not results[0]:
                print(f"\n⏭️  Skipping {test_name} (server not available)")
                results.append(False)
                continue

            result = await test_func()
            results.append(result)

        except Exception as e:
            print(f"\n❌ {test_name} raised an exception: {e}")
            results.append(False)

    # Summary
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)

    for i, (test_name, _) in enumerate(tests):
        status = "✅ PASS" if results[i] else "❌ FAIL"
        print(f"{status} - {test_name}")

    passed = sum(results)
    total = len(results)

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Sandbox is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check the output above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
