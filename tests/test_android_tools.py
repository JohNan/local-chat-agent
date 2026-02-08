import pytest
from unittest.mock import patch, MagicMock
from app.services import git_ops


def test_get_file_outline_python():
    content = """
class MyClass:
    def method_one(self):
        pass

def global_function():
    pass
"""
    with patch("app.services.git_ops.read_file", return_value=content):
        outline = git_ops.get_file_outline("test.py")
        assert "class MyClass" in outline
        assert "def method_one" in outline
        assert "def global_function" in outline


def test_get_file_outline_kotlin():
    content = """
package com.example

@Composable
fun MyScreen() {
}

class ViewModel : ViewModel() {
}
"""
    with patch("app.services.git_ops.read_file", return_value=content):
        outline = git_ops.get_file_outline("test.kt")
        assert "@Composable" in outline
        assert "fun MyScreen" in outline
        assert "class ViewModel" in outline


def test_get_file_outline_js():
    content = """
export const myConst = 1;

export function myFunction() {
}

class MyComponent extends React.Component {
}
"""
    with patch("app.services.git_ops.read_file", return_value=content):
        outline = git_ops.get_file_outline("test.js")
        assert "export const myConst" in outline
        assert "export function myFunction" in outline
        assert "class MyComponent" in outline


def test_read_android_manifest():
    content = """
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.example.app">
    <uses-permission android:name="android.permission.INTERNET" />
    <application>
        <activity android:name=".MainActivity">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
        <activity android:name=".DetailActivity" />
    </application>
</manifest>
"""
    with patch("app.services.git_ops.read_file", return_value=content):
        info = git_ops.read_android_manifest()
        assert "Package: com.example.app" in info
        assert "android.permission.INTERNET" in info
        assert ".MainActivity [ENTRY POINT]" in info
        assert ".DetailActivity" in info
        assert ".DetailActivity [ENTRY POINT]" not in info
