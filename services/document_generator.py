from dotenv import load_dotenv
load_dotenv()
"""
Document Generator Service
- Takes collected structured data + template
- Uses LLM to intelligently fill template (handles formatting lists, narrative sections)
- Strictly constrained: only use provided data, never invent facts
- Temperature = 0 for full reproducibility
"""

import os
import re
from pathlib import Path
from groq import Groq


DRAFTER_SYSTEM_PROMPT = """You are a legal document drafter. Your job is to fill in a legal document template using ONLY the data provided.

STRICT RULES:
1. Use ONLY the data provided in the user message. Never invent names, dates, amounts, or any facts.
2. Do NOT provide legal advice or commentary.
3. Do NOT add clauses, terms, or provisions not in the template.
4. Format lists cleanly (e.g. beneficiaries as numbered list).
5. If a field value is missing or says "N/A", write "Not specified" in that section.
6. Return ONLY the filled document text. No preamble, no explanation.
7. Today's date is 2026. Donot flag 2026 as future dates.
"""


class DocumentGenerator:
    def __init__(self):
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.model = "llama-3.3-70b-versatile"  # larger model for better document quality
        self.templates_dir = Path("templates")

    def _load_template(self, doc_type: str) -> str:
        template_path = self.templates_dir / f"{doc_type}.txt"
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")
        return template_path.read_text()

    def _simple_fill(self, template: str, data: dict) -> str:
        """Simple placeholder replacement for fields that don't need LLM"""
        result = template
        for key, value in data.items():
            if isinstance(value, list):
                formatted = "\n".join(f"  {i+1}. {item}" for i, item in enumerate(value))
                result = result.replace(f"{{{{{key}}}}}", formatted)
            else:
                result = result.replace(f"{{{{{key}}}}}", str(value) if value else "Not specified")
        return result

    def generate(self, doc_type: str, collected_data: dict) -> dict:
        """
        Generate the final legal document.
        Returns: { "document": str, "method": str, "missing_fields": list }
        """
        template = self._load_template(doc_type)

        # Find any unfilled placeholders after simple fill
        simple_filled = self._simple_fill(template, collected_data)
        missing = re.findall(r"\{\{(\w+)\}\}", simple_filled)

        # Use LLM to intelligently fill and format the document
        prompt = f"""Fill in the following legal document template using ONLY this data:

COLLECTED DATA:
{collected_data}

TEMPLATE (fill all {{{{field_name}}}} placeholders):
{template}

Return the complete filled document."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": DRAFTER_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0,  # fully deterministic — same input = same output always
            max_tokens=2000,
        )

        document = response.choices[0].message.content.strip()

        return {
            "document": document,
            "method": "llm_drafted",
            "missing_fields": missing,
            "collected_data": collected_data,
        }
