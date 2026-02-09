import sys
import os
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import agent_engine

def test_system_instruction_contains_documentation_rule():
    instruction = agent_engine.SYSTEM_INSTRUCTION
    assert "Update any relevant documentation (e.g. README, docstrings) when the task is done." in instruction

def test_system_instruction_contains_testing_rule():
    instruction = agent_engine.SYSTEM_INSTRUCTION
    assert "Write unit tests to verify the changes." in instruction
