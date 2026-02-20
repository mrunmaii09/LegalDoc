from dotenv import load_dotenv
load_dotenv()
"""
Conversation Agent Service
- Goal-directed agent: collects all required fields from config
- Uses Groq LLM (Llama 3.1) for natural conversation
- Maintains full conversation history for context
- Detects contradictions and vague inputs via LLM
"""

import os
import json
from groq import Groq
from services.guardrails import GuardrailsService


class ConversationAgent:
    def __init__(self, doc_config: dict):
        self.doc_config = doc_config
        self.required_fields = doc_config.get("required_fields", [])
        self.collected_data = {}
        self.conversation_history = []
        self.guardrails = GuardrailsService(doc_config)
        self.is_complete = False

        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.model = "llama-3.1-8b-instant"  # fast + capable enough for this task

    def _build_system_prompt(self) -> str:
        from datetime import date
        today = date.today().strftime("%d-%B-%Y")  
    
        fields_list = "\n".join(
            f"- {f['name']}: {f['description']}" for f in self.required_fields
    )
        collected_summary = json.dumps(self.collected_data, indent=2) if self.collected_data else "Nothing yet"

        template = self.doc_config.get("system_prompt", "")
        prompt = template.format(fields=fields_list, collected=collected_summary)
    
    # Inject real date so LLM never guesses
        prompt += f"\n\nIMPORTANT: Today's actual date is {today}. Use this as the current date for all purposes."
    
        return prompt
    def _extract_collected_fields(self, assistant_message: str) -> None:
        """
        Ask LLM to extract any newly confirmed field values from the conversation.
        Separate extraction call keeps the main conversation clean.
        """
        if not self.conversation_history:
            return

        field_names = [f["name"] for f in self.required_fields]
        extraction_prompt = f"""

Look at this conversation and extract ONLY values that the user has EXPLICITLY stated.

Conversation:
{json.dumps(self.conversation_history, indent=2)}

Fields to extract: {field_names}

STRICT RULES:
- ONLY extract a field if the user directly said the value
- Do NOT infer, guess, or assume any values
- Do NOT extract anything the assistant said
- If unsure, leave the field out entirely
- Return ONLY a JSON object, nothing else

Example: if user said "my name is John", return {{"testator_name": "John"}}
If user said nothing about a field, do NOT include it. """

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": extraction_prompt}],
                temperature=0,  # deterministic extraction
                max_tokens=500,
            )
            raw = response.choices[0].message.content.strip()
            # Parse JSON safely
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end > start:
                extracted = json.loads(raw[start:end])
                self.collected_data.update(extracted)
        except Exception:
            pass  # extraction failure is non-fatal

    def chat(self, user_message: str) -> dict:
        """
        Main entry point. Returns:
        {
            "reply": str,
            "blocked": bool,
            "block_reason": str | None,
            "is_complete": bool,
            "collected_data": dict
        }
        """
        # Step 1: Guardrails check BEFORE hitting LLM
        block = self.guardrails.check(user_message)
        if block:
            return {
                "reply": block,
                "blocked": True,
                "block_reason": "guardrail_triggered",
                "is_complete": False,
                "collected_data": self.collected_data,
            }

        # Step 2: Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # Step 3: Call LLM with full conversation history
        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            *self.conversation_history
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,  
            max_tokens=400,
        )

        assistant_reply = response.choices[0].message.content.strip()

        # Step 4: Add assistant reply to history
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_reply
        })

        # Step 5: Extract any newly confirmed fields
        self._extract_collected_fields(assistant_reply)

        # Step 6: Check if collection is complete
        if "COLLECTION_COMPLETE" in assistant_reply:
            self.is_complete = True
            clean_reply = assistant_reply.replace("COLLECTION_COMPLETE", "").strip()
            clean_reply = clean_reply or "I've collected all the information needed. Generating your document now..."
        else:
            clean_reply = assistant_reply

        return {
            "reply": clean_reply,
            "blocked": False,
            "block_reason": None,
            "is_complete": self.is_complete,
            "collected_data": self.collected_data,
        }

    def get_collected_data(self) -> dict:
        return self.collected_data
