import unittest

from insights.runtime.tools import Tool, ToolError, ToolRegistry

ECHO = Tool(
    name="echo",
    description="Echo the value back.",
    input_schema={
        "type": "object",
        "required": ["value"],
        "properties": {"value": {"type": "string"}},
        "additionalProperties": False,
    },
    fn=lambda args: {"echoed": args["value"]},
)


class ToolRegistryTests(unittest.TestCase):
    def test_duplicate_names_are_rejected(self):
        with self.assertRaises(ToolError):
            ToolRegistry((ECHO, ECHO))

    def test_bad_name_is_rejected(self):
        bad = Tool(name="Echo-Tool", description="x", input_schema={"type": "object"}, fn=dict)
        with self.assertRaises(ToolError):
            ToolRegistry((bad,))

    def test_invalid_schema_is_rejected(self):
        bad = Tool(
            name="bad", description="x", input_schema={"type": "nonsense"}, fn=dict
        )
        with self.assertRaises(ToolError):
            ToolRegistry((bad,))

    def test_unknown_tool_reports_available_names(self):
        outcome = ToolRegistry((ECHO,)).invoke("missing", {})
        self.assertFalse(outcome.ok)
        self.assertIn("unknown tool", outcome.text)
        self.assertIn("echo", outcome.text)

    def test_arguments_are_schema_validated(self):
        outcome = ToolRegistry((ECHO,)).invoke("echo", {"value": 5})
        self.assertFalse(outcome.ok)
        self.assertIn("invalid arguments", outcome.text)

    def test_tool_exception_becomes_error_text(self):
        def boom(args):
            raise RuntimeError("database on fire")

        tool = Tool(name="boom", description="x", input_schema={"type": "object"}, fn=boom)
        outcome = ToolRegistry((tool,)).invoke("boom", {})
        self.assertFalse(outcome.ok)
        self.assertIn("tool failed: RuntimeError", outcome.text)

    def test_large_results_are_truncated(self):
        tool = Tool(
            name="big",
            description="x",
            input_schema={"type": "object"},
            fn=lambda args: {"text": "y" * 1000},
            max_result_chars=200,
        )
        outcome = ToolRegistry((tool,)).invoke("big", {})
        self.assertTrue(outcome.ok)
        self.assertIn("[truncated", outcome.text)
        self.assertLess(len(outcome.text), 300)

    def test_happy_path(self):
        outcome = ToolRegistry((ECHO,)).invoke("echo", {"value": "hi"})
        self.assertTrue(outcome.ok)
        self.assertIn('"echoed": "hi"', outcome.text)


if __name__ == "__main__":
    unittest.main()
