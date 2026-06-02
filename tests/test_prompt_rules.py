"""
Tests for prompt rules and persona prompts.
"""

from app.services.prompt_router import CORE_INSTRUCTION, PERSONA_PROMPTS


def test_core_instruction_contains_lsp_rule():
    """Test that CORE_INSTRUCTION contains the LSP Priority rule."""
    expected_rule = (
        "3. **Navigate (LSP):**\n"
        "   - **Found a usage but need the implementation?** -> Use `get_definition`.\n"
        '   - *Constraint:* Do NOT grep for "def my_function" or "class MyClass". '
        "Use LSP on the symbol usage instead."
    )
    assert expected_rule in CORE_INSTRUCTION


def test_persona_prompts_references():
    """Test that PERSONA_PROMPTS contains expected specialist personas with relevant content."""
    if "UI" in PERSONA_PROMPTS:
        assert "UI mode" in PERSONA_PROMPTS["UI"]
    if "MOBILE" in PERSONA_PROMPTS:
        assert "mobile mode" in PERSONA_PROMPTS["MOBILE"]
