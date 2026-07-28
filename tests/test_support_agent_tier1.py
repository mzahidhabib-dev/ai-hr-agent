"""
tests/test_support_agent_tier1.py

End-to-end integration test suite for Support Agent Tier 1 (Production MVP).

Verifies:
  1. Micro-Step 1.1 & 1.2: State schema & Prompt templates
  2. Micro-Step 2.1 - 2.3: Omnichannel Intake, Customer 360, & Groq Classification
  3. Micro-Step 3.1 - 3.3: Knowledge RAG, Technical Diagnosis, & Grounded Response
  4. Micro-Step 4.1 - 4.3: HITL Decision Cards, Human Escalation, & Compiled StateGraph
"""

import unittest
from dotenv import load_dotenv
load_dotenv(override=True)

from business_agents.support.state import SupportState
from business_agents.support.prompts import (
    CLASSIFICATION_PROMPT,
    DIAGNOSIS_PROMPT,
    GROUNDED_RESPONSE_PROMPT,
    HUMAN_HANDOFF_PROMPT
)
from business_agents.support.nodes import (
    IntakeNode,
    CustomerContextNode,
    ClassificationNode,
    KnowledgeRAGNode,
    DiagnosisNode,
    ResponseNode,
    ActionNode,
    EscalationNode
)
from business_agents.support.graph import support_pipeline


class TestSupportAgentTier1(unittest.TestCase):

    def test_01_support_state_schema(self):
        """Verify SupportState TypedDict imports and instantiates cleanly."""
        state: SupportState = {
            "tenant_id": "tenant-1",
            "inbound_message": "Hello support",
            "status": "NEW"
        }
        self.assertEqual(state["tenant_id"], "tenant-1")
        self.assertEqual(state["inbound_message"], "Hello support")

    def test_02_prompts_formatting(self):
        """Verify all prompt templates contain required format keys."""
        self.assertIn("{message}", CLASSIFICATION_PROMPT)
        self.assertIn("{message}", DIAGNOSIS_PROMPT)
        self.assertIn("{evidence_context}", GROUNDED_RESPONSE_PROMPT)
        self.assertIn("{state_summary}", HUMAN_HANDOFF_PROMPT)

    def test_03_intake_deduplication(self):
        """Verify IntakeNode deduplicates external_message_id."""
        state1 = {
            "tenant_id": "tenant-1",
            "inbound_message": "Deduplication test",
            "external_message_id": "msg-unique-999"
        }
        res1 = IntakeNode(state1)
        self.assertEqual(res1["status"], "NEW")
        
        # Second call with same message id
        res2 = IntakeNode(state1)
        self.assertEqual(res2["status"], "DUPLICATE_SKIPPED")

    def test_04_customer_context_assembly(self):
        """Verify CustomerContextNode populates Customer 360 package."""
        state = {
            "tenant_id": "tenant-1",
            "customer_id": "cust-vip-101"
        }
        res = CustomerContextNode(state)
        self.assertIn("customer_context", res)
        ctx = res["customer_context"]
        self.assertEqual(ctx["customer_id"], "cust-vip-101")
        self.assertIn("plan", ctx)
        self.assertIn("SLA", ctx)

    def test_05_groq_classification(self):
        """Verify ClassificationNode classifies intent via Groq AI."""
        state = {
            "tenant_id": "tenant-1",
            "inbound_message": "I want a full refund because the service was unusable."
        }
        res = ClassificationNode(state)
        self.assertEqual(res["status"], "CLASSIFIED")
        self.assertIn("intent", res)
        self.assertIn("frustration_score", res)

    def test_06_knowledge_rag_retrieval(self):
        """Verify KnowledgeRAGNode retrieves evidence chunks."""
        state = {
            "tenant_id": "tenant-1",
            "inbound_message": "What is your refund policy?"
        }
        res = KnowledgeRAGNode(state)
        self.assertIn("retrieved_evidence", res)
        self.assertGreater(len(res["retrieved_evidence"]), 0)
        self.assertIn("document_name", res["retrieved_evidence"][0])

    def test_07_technical_diagnosis(self):
        """Verify DiagnosisNode formulates technical hypotheses for TECHNICAL intent."""
        state = {
            "tenant_id": "tenant-1",
            "inbound_message": "Getting 500 error on API call /v1/auth",
            "intent": "TECHNICAL"
        }
        res = DiagnosisNode(state)
        self.assertIn("diagnostic_hypotheses", res)
        self.assertGreater(len(res["diagnostic_hypotheses"]), 0)

    def test_08_grounded_response_generation(self):
        """Verify ResponseNode outputs citation-backed response with normalized confidence score."""
        state = {
            "tenant_id": "tenant-1",
            "inbound_message": "What is the SLA response time?",
            "retrieved_evidence": [{
                "content": "SLA priority response time is guaranteed under 2 hours.",
                "page_number": 1,
                "document_name": "SLA_Policy.pdf"
            }]
        }
        res = ResponseNode(state)
        self.assertIn("response_text", res)
        self.assertIn("citations", res)
        self.assertGreater(res["confidence_score"], 50.0)

    def test_09_action_hitl_decision_cards(self):
        """Verify ActionNode generates Decision Card row in PostgreSQL DB for high-risk actions."""
        state_high = {
            "tenant_id": "tenant-1",
            "inbound_message": "I demand a refund of $500",
            "intent": "REFUND",
            "confidence_score": 90.0
        }
        res_high = ActionNode(state_high)
        self.assertEqual(res_high["status"], "WAITING_FOR_HUMAN")
        self.assertGreater(res_high["decision_id"], 0)

    def test_10_human_escalation_handoff(self):
        """Verify EscalationNode generates 8-part handoff package in PostgreSQL DB."""
        state = {
            "tenant_id": "tenant-1",
            "inbound_message": "Database corrupted, system down!",
            "conversation_id": "conv-test-777",
            "intent": "INCIDENT",
            "urgency": "HIGH"
        }
        res = EscalationNode(state)
        self.assertEqual(res["status"], "WAITING_FOR_HUMAN")
        self.assertGreater(res["action_result"]["handoff_id"], 0)
        self.assertIn("package", res["action_result"])

    def test_11_full_pipeline_graph_execution(self):
        """Verify full support_pipeline StateGraph execution end-to-end."""
        config = {"configurable": {"thread_id": "thread-e2e-1"}}
        initial_state = {
            "tenant_id": "tenant-1",
            "inbound_message": "How do I update my billing email address?"
        }
        final_state = support_pipeline.invoke(initial_state, config)
        self.assertIn("response_text", final_state)
        self.assertIn(final_state["status"], ["RESOLVED", "WAITING_FOR_HUMAN"])
        print("\n[SUCCESS] Full support pipeline E2E invocation completed successfully!")


if __name__ == "__main__":
    unittest.main(verbosity=2)
