import time
import unittest

from insights.contracts.enums import EventType, Purpose
from insights.contracts.gateway import CompletionResult, Usage
from insights.gateway.base import ResponseSchemaError
from insights.runtime.skill_agent import SkillAgent, SkillAgentSpec
from insights.runtime.stores import MonotonicDeadline, TokenMeter
from insights.runtime.tools import Tool, ToolRegistry

OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["personas"],
    "properties": {"personas": {"type": "array"}},
    "additionalProperties": True,
}

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


class FakeGateway:
    """Replays scripted envelope objects (or raises scripted exceptions), charging fake tokens."""

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def complete(self, messages, purpose, ctx, response_schema=None):
        self.calls.append({"messages": tuple(messages), "purpose": purpose, "schema": response_schema})
        item = self.outputs.pop(0)
        if isinstance(item, Exception):
            raise item
        ctx["usage"].add(100, 50)
        if isinstance(item, CompletionResult):
            return item
        return CompletionResult(
            content=item, usage=Usage(prompt_tokens=100, completion_tokens=50), model="fake-model"
        )


def make_ctx(gateway, *, deadline_ms=60_000):
    notes = []
    ctx = {
        "run_id": "run1",
        "trace_id": "a" * 32,
        "usage": TokenMeter(),
        "deadline": MonotonicDeadline(time.monotonic, deadline_ms),
        "emit": lambda note, count=None: notes.append((note, count)),
        "gateway": gateway,
    }
    return ctx, notes


def make_agent(*, tools=(), validators=(), threshold=0.5, max_iterations=3, max_repairs=1,
               token_budget=10_000, event_sink=None, retry_on_low_confidence=False):
    spec = SkillAgentSpec(
        name="demo-skill",
        version="0.1.0",
        purpose=Purpose.DESIGN,
        prompt="unused",
        instruction="Produce the demo artifact.",
        output_key="artifact",
        output_schema="demo",
        max_iterations=max_iterations,
        max_repairs=max_repairs,
        confidence_threshold=threshold,
        token_budget=token_budget,
        timeout_ms=60_000,
        tools=tuple(tool.name for tool in tools),
        retry_on_low_confidence=retry_on_low_confidence,
    )
    registry = ToolRegistry(tuple(tools))
    return SkillAgent(
        spec,
        prompt_text="You are the demo skill.",
        output_schema=OUTPUT_SCHEMA,
        render_task=lambda input: "Task: " + str(input.get("document", "")),
        tool_factory=lambda input: registry,
        validator_factory=lambda input: tuple(validators),
        event_sink=event_sink,
    )


class SkillAgentTests(unittest.TestCase):
    def test_finish_on_first_turn(self):
        gateway = FakeGateway([{"action": "finish", "result": {"personas": [1]}, "confidence": 0.9}])
        ctx, _ = make_ctx(gateway)
        out = make_agent().run({"document": "d"}, ctx)
        self.assertEqual(out["label"], "ok")
        self.assertEqual(out["artifact"], {"personas": [1]})
        self.assertEqual(out["confidence"], 0.9)
        self.assertEqual(out["iterations"], 1)
        self.assertEqual(out["repairs"], 0)
        self.assertGreater(out["tokens"]["total"], 0)

    def test_tool_call_then_finish(self):
        events = []
        gateway = FakeGateway([
            {"action": "use_tool", "tool": "echo", "tool_args": {"value": "hi"}},
            {"action": "finish", "result": {"personas": []}, "confidence": 0.8},
        ])
        ctx, notes = make_ctx(gateway)
        out = make_agent(tools=(ECHO,), event_sink=events.append).run({"document": "d"}, ctx)
        self.assertEqual(out["label"], "ok")
        self.assertEqual(out["tool_calls"], 1)
        second_call = gateway.calls[1]["messages"]
        observation = second_call[-1].content
        self.assertIn("TOOL RESULT (echo)", observation)
        self.assertIn("echoed", observation)
        self.assertIn(("agent_tool_echo", None), notes)
        tool_events = [e for e in events if e.type is EventType.TOOL_CALL]
        self.assertEqual(len(tool_events), 1)
        self.assertEqual(tool_events[0].tool, "echo")
        self.assertEqual(tool_events[0].status, "ok")
        iteration_events = [e for e in events if e.type is EventType.AGENT_ITERATION]
        self.assertEqual([e.iteration for e in iteration_events], [1, 2])

    def test_validation_failure_triggers_semantic_repair_then_succeeds(self):
        validator = lambda draft: (  # noqa: E731
            [] if draft.get("personas") else ["personas: at least one persona is required"]
        )
        gateway = FakeGateway([
            {"action": "finish", "result": {"personas": []}, "confidence": 0.9},
            {"action": "finish", "result": {"personas": [{"id": "p1"}]}, "confidence": 0.9},
        ])
        ctx, _ = make_ctx(gateway)
        out = make_agent(validators=(validator,)).run({"document": "d"}, ctx)
        self.assertEqual(out["label"], "ok")
        self.assertEqual(out["repairs"], 1)
        self.assertEqual(out["iterations"], 2)
        repair = gateway.calls[1]["messages"][-1].content
        self.assertIn("REPAIR REQUEST", repair)
        self.assertIn("personas: at least one persona is required", repair)

    def test_bad_envelopes_escalate_after_max_repairs(self):
        gateway = FakeGateway([
            ResponseSchemaError("response is not valid JSON"),
            ResponseSchemaError("response is not valid JSON"),
        ])
        ctx, _ = make_ctx(gateway)
        out = make_agent(max_repairs=1).run({"document": "d"}, ctx)
        self.assertEqual(out["label"], "escalate")
        self.assertTrue(out["reason"].startswith("validation_failed"))

    def test_budget_exhaustion_escalates_instead_of_crashing(self):
        class ExpensiveGateway(FakeGateway):
            def complete(self, messages, purpose, ctx, response_schema=None):
                result = super().complete(messages, purpose, ctx, response_schema)
                ctx["usage"].add(9_000, 500)  # this call alone blows the budget
                return result

        gateway = ExpensiveGateway([
            {"action": "use_tool", "tool": "echo", "tool_args": {"value": "x"}},
            {"action": "finish", "result": {"personas": []}, "confidence": 0.9},
        ])
        ctx, _ = make_ctx(gateway)
        out = make_agent(tools=(ECHO,), token_budget=1_000).run({"document": "d"}, ctx)
        self.assertEqual(out["label"], "escalate")
        self.assertTrue(out["reason"].startswith("budget_exhausted"))
        self.assertEqual(out["confidence"], 0.0)
        self.assertEqual(len(gateway.calls), 1)  # the second turn was refused, not attempted

    def test_expired_deadline_escalates(self):
        gateway = FakeGateway([])
        ctx, _ = make_ctx(gateway, deadline_ms=0)
        out = make_agent().run({"document": "d"}, ctx)
        self.assertEqual(out["label"], "escalate")
        self.assertTrue(out["reason"].startswith("deadline"))

    def test_max_iterations_escalates(self):
        turns = [
            {"action": "use_tool", "tool": "echo", "tool_args": {"value": f"x{i}"}}
            for i in range(3)
        ]
        gateway = FakeGateway(turns)
        ctx, _ = make_ctx(gateway)
        out = make_agent(tools=(ECHO,), max_iterations=3).run({"document": "d"}, ctx)
        self.assertEqual(out["label"], "escalate")
        self.assertTrue(out["reason"].startswith("max_iterations"))
        self.assertEqual(out["tool_calls"], 3)

    def test_low_confidence_escalates_with_the_draft(self):
        gateway = FakeGateway([{"action": "finish", "result": {"personas": [1]}, "confidence": 0.2}])
        ctx, _ = make_ctx(gateway)
        out = make_agent(threshold=0.5).run({"document": "d"}, ctx)
        self.assertEqual(out["label"], "escalate")
        self.assertTrue(out["reason"].startswith("low_confidence"))
        self.assertEqual(out["artifact"], {"personas": [1]})

    def test_model_initiated_escalation(self):
        gateway = FakeGateway([
            {"action": "escalate", "reason": "needs_context: missing glossary", "confidence": 0.4}
        ])
        ctx, _ = make_ctx(gateway)
        out = make_agent().run({"document": "d"}, ctx)
        self.assertEqual(out["label"], "escalate")
        self.assertEqual(out["reason"], "model_escalated: needs_context: missing glossary")
        self.assertEqual(out["confidence"], 0.4)

    def test_tools_not_named_in_the_spec_are_invisible(self):
        """The spec is authoritative: a registered tool outside spec.tools is not described,
        not in the envelope enum, and not dispatchable."""
        gateway = FakeGateway([
            {"action": "use_tool", "tool": "echo", "tool_args": {"value": "x"}},
            {"action": "finish", "result": {"personas": []}, "confidence": 0.9},
        ])
        ctx, _ = make_ctx(gateway)
        spec = SkillAgentSpec(
            name="demo-skill", version="0.1.0", purpose=Purpose.DESIGN, prompt="unused",
            instruction="x", output_key="artifact", output_schema="demo", max_iterations=3,
            max_repairs=1, confidence_threshold=0.5, token_budget=10_000, timeout_ms=60_000,
            tools=(),  # echo exists in the registry but the spec does not name it
        )
        agent = SkillAgent(
            spec, prompt_text="p", output_schema=OUTPUT_SCHEMA,
            render_task=lambda input: "t", tool_factory=lambda input: ToolRegistry((ECHO,)),
        )
        out = agent.run({}, ctx)
        self.assertEqual(out["label"], "ok")
        self.assertIn("No tools are available", gateway.calls[0]["messages"][0].content)
        self.assertIn("unknown tool", gateway.calls[1]["messages"][-1].content)

    def test_truncated_reply_triggers_a_compactness_repair(self):
        truncated = CompletionResult(
            content={"action": "finish", "confidence": 0.9},
            usage=Usage(prompt_tokens=100, completion_tokens=50),
            model="fake-model",
            truncated=True,
        )
        gateway = FakeGateway([
            truncated,
            {"action": "finish", "result": {"personas": []}, "confidence": 0.9},
        ])
        ctx, _ = make_ctx(gateway)
        out = make_agent().run({"document": "d"}, ctx)
        self.assertEqual(out["label"], "ok")
        self.assertEqual(out["repairs"], 1)
        repair = gateway.calls[1]["messages"][-1].content
        self.assertIn("cut off at the output-token limit", repair)

    def test_stringified_result_is_rescued(self):
        gateway = FakeGateway([
            {"action": "finish", "result": '{"personas": [1]}', "confidence": 0.9}
        ])
        ctx, _ = make_ctx(gateway)
        out = make_agent().run({"document": "d"}, ctx)
        self.assertEqual(out["label"], "ok")
        self.assertEqual(out["artifact"], {"personas": [1]})

    def test_identical_tool_calls_are_detected_as_a_loop(self):
        turn = {"action": "use_tool", "tool": "echo", "tool_args": {"value": "same"}}
        gateway = FakeGateway([turn, turn, turn])
        ctx, _ = make_ctx(gateway)
        out = make_agent(tools=(ECHO,), max_iterations=5).run({"document": "d"}, ctx)
        self.assertEqual(out["label"], "escalate")
        self.assertTrue(out["reason"].startswith("loop_detected"))
        self.assertEqual(out["tool_calls"], 2)  # the third identical call was refused
        warning = gateway.calls[2]["messages"][-1].content
        self.assertIn("REPEATED IDENTICAL CALL", warning)

    def test_low_confidence_can_refine_instead_of_escalating(self):
        gateway = FakeGateway([{"action": "finish", "result": {"personas": [1]}, "confidence": 0.2}])
        ctx, _ = make_ctx(gateway)
        out = make_agent(threshold=0.5, retry_on_low_confidence=True).run({"document": "d"}, ctx)
        self.assertEqual(out["label"], "refine_self")
        self.assertTrue(out["critique"].startswith("low_confidence"))
        self.assertEqual(out["artifact"], {"personas": [1]})

    def test_invalid_tool_arguments_come_back_as_observations(self):
        gateway = FakeGateway([
            {"action": "use_tool", "tool": "echo", "tool_args": {"value": 5}},
            {"action": "finish", "result": {"personas": []}, "confidence": 0.9},
        ])
        ctx, _ = make_ctx(gateway)
        out = make_agent(tools=(ECHO,)).run({"document": "d"}, ctx)
        self.assertEqual(out["label"], "ok")
        observation = gateway.calls[1]["messages"][-1].content
        self.assertIn("TOOL ERROR (echo)", observation)
        self.assertIn("invalid arguments", observation)


if __name__ == "__main__":
    unittest.main()
