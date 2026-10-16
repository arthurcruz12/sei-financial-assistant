import unittest
from sei_agents import AgentResult
from sei_multi_agent import MultiAgentChat, AGENTS


class StubValidator:
    def validate(self, result):
        if result.agent == "blocked":
            raise ValueError("unsupported numerical claim")
        return result


class StubOrchestrator:
    validator = StubValidator()
    def __init__(self):
        self.calls = []
    def chat(self, message, image_bytes=None, mime_type=None):
        self.calls.append((message, image_bytes, mime_type))
        return [AgentResult(agent="macro_data", summary="Official series",
                            sources=["Official API"])]

class BrokenOrchestrator(StubOrchestrator):
    def chat(self, *args, **kwargs):
        raise RuntimeError("provider offline")


class MultiAgentChatTests(unittest.TestCase):
    def test_roles_cover_specialists(self):
        roles = {a.role for a in AGENTS}
        self.assertTrue({"macro_data", "market_data", "statistics", "econometrics",
                         "research", "validator", "router"}.issubset(roles))

    def test_routes_and_preserves_sources(self):
        stub = StubOrchestrator()
        response = MultiAgentChat(stub).chat(" Mostra IPCA ", image_bytes=b"png",
                                           mime_type="image/png")
        self.assertEqual(stub.calls, [("Mostra IPCA", b"png", "image/png")])
        self.assertEqual(response[0].sources, ["Official API"])

    def test_empty_message_without_source_request(self):
        stub = StubOrchestrator()
        response = MultiAgentChat(stub).chat(" ")
        self.assertEqual(stub.calls, [])
        self.assertIn("pergunta", response[0].summary)

    def test_failure_without_fake_numbers(self):
        response = MultiAgentChat(BrokenOrchestrator()).chat("Mostra IPCA")
        self.assertEqual(response[0].agent, "coordinator")
        self.assertEqual(response[0].data, {})
        self.assertTrue(response[0].warnings)

    def test_invalid_result_blocked(self):
        class Invalid(StubOrchestrator):
            def chat(self, *args, **kwargs):
                return [AgentResult(agent="blocked", summary="bad", data={"p": 111})]
        response = MultiAgentChat(Invalid()).chat("test")
        self.assertEqual(response[0].agent, "validator")
        self.assertEqual(response[0].data, {})


if __name__ == "__main__":
    unittest.main()
