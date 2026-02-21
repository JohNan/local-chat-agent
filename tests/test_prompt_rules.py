"""
Tests for prompt rules and persona prompts.
"""

from app.services.prompt_router import CORE_INSTRUCTION, PERSONA_PROMPTS


def test_core_instruction_contains_lsp_rule():
    """Test that CORE_INSTRUCTION contains the LSP Priority rule."""
    expected_rule = (
        "3. **LSP Priority:** When asked to find the definition of a class, function, or variable, "
        "ALWAYS prioritize using `get_definition` (LSP) over `grep_code` or `read_file`. "
        "This is faster and more accurate for supported languages (Python, TS, Kotlin)."
    )
    assert expected_rule in CORE_INSTRUCTION


def test_persona_prompts_references():
    """Test that PERSONA_PROMPTS references the correct rule numbers."""
    assert "Includes Rule 7 (Visualizing Compose UI)." in PERSONA_PROMPTS["UI"]
    assert "Includes Rule 8 (Android Configuration)." in PERSONA_PROMPTS["MOBILE"]
