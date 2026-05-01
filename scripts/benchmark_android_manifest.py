
import timeit
import xml.etree.ElementTree as ET
from app.services import git_ops

def generate_large_manifest(num_activities=100, num_intents_per_activity=10):
    permissions = [f"android.permission.PERMISSION_{i}" for i in range(50)]
    permissions_xml = "\n".join([f'    <uses-permission android:name="{p}" />' for p in permissions])

    activities_xml = []
    for i in range(num_activities):
        intents_xml = []
        for j in range(num_intents_per_activity):
            intents_xml.append(f"""
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
                <action android:name="android.intent.action.VIEW_{j}" />
                <category android:name="android.intent.category.DEFAULT" />
            </intent-filter>
            """)
        activities_xml.append(f"""
        <activity android:name=".Activity_{i}">
            {"".join(intents_xml)}
        </activity>
        """)

    manifest_content = f"""
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.example.largeapp">
    {permissions_xml}
    <application>
        {"".join(activities_xml)}
    </application>
</manifest>
"""
    return manifest_content

def benchmark():
    content = generate_large_manifest(num_activities=100, num_intents_per_activity=10)

    def test_func():
        # We need to mock read_file because read_android_manifest calls it
        from unittest.mock import patch
        with patch("app.services.git_ops.read_file", return_value=content):
            git_ops.read_android_manifest("mock_manifest.xml")

    # Warmup
    test_func()

    iterations = 100
    timer = timeit.Timer(test_func)
    total_time = timer.timeit(number=iterations)

    print(f"Total time for {iterations} iterations: {total_time:.4f}s")
    print(f"Average time per iteration: {total_time/iterations:.6f}s")

if __name__ == "__main__":
    benchmark()
