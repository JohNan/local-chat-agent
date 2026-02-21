"""
Service for executing Python code in a subprocess.
"""

import subprocess
import logging

logger = logging.getLogger(__name__)


def execute_code(code: str) -> str:
    """
    Executes the provided Python code in a separate process.

    Args:
        code: The Python code to execute.

    Returns:
        A string containing the standard output and standard error of the execution.
    """
    logger.info("Executing code...")
    try:
        # Run the code in a subprocess
        result = subprocess.run(
            ["python3", "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        output = result.stdout
        error = result.stderr

        response = ""
        if output:
            response += f"Output:\n{output}\n"
        if error:
            response += f"Error:\n{error}\n"

        if not response:
            response = "Code executed successfully with no output."

        return response.strip()

    except subprocess.TimeoutExpired:
        return "Error: Code execution timed out after 30 seconds."
    except Exception as e:  # pylint: disable=broad-exception-caught
        return f"Error executing code: {str(e)}"
