"""
Guardrails Service
Detects: advice requests, prompt injection, vague inputs
Runs BEFORE sending user message to LLM
"""

from typing import Optional
import re


class GuardrailsService:
    def __init__(self, doc_config: dict):
        self.advice_keywords = doc_config.get("guardrails", {}).get("advice_keywords", [])
        self.injection_patterns = doc_config.get("guardrails", {}).get("injection_patterns", [])

    def check(self, user_message: str) -> Optional[str]:
        """
        Returns a block message if guardrail is triggered, else None.
        Runs before the message reaches the LLM.
        """
        msg_lower = user_message.lower()

        # 1. Prompt injection detection
        for pattern in self.injection_patterns:
            if pattern.lower() in msg_lower:
                return (
                    "⚠️ I'm unable to process that request. "
                    "I can only help you collect information for your legal document."
                )

        # 2. Advice-seeking detection
        for keyword in self.advice_keywords:
            if keyword.lower() in msg_lower:
                return (
                    "I'm not able to provide legal advice. "
                    "I can only help collect information for your document. "
                    "Please consult a qualified solicitor for legal guidance."
                )

        return None  # all clear

    def check_vague(self, field_name: str, value: str, vague_keywords: list) -> bool:
        """Check if a field value is too vague"""
        value_lower = value.lower()
        return any(kw.lower() in value_lower for kw in vague_keywords)
