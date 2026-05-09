"""
Email Composer - Generate professional emails using LLM
"""
import json
import logging
import re
import unicodedata
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)

# Default model configuration
DEFAULT_MODEL = "deepseek-r1:1.5b"
OLLAMA_BASE_URL = "http://localhost:11434"


class EmailComposer:
    """Generate professional emails using LLM"""
    
    def __init__(self, model: str = DEFAULT_MODEL, base_url: str = OLLAMA_BASE_URL):
        """Initialize email composer with LLM"""
        self.model = model
        self.base_url = base_url
        self.llm = ChatOllama(model=model, base_url=base_url, temperature=0.3)
    
    def generate_email(
        self,
        recipient: str,
        subject_context: str,
        tone: str = "professional",
        additional_context: str = "",
    ) -> dict:
        """
        Generate professional email subject and body.
        
        Args:
            recipient: Email recipient name/address
            subject_context: What the email is about
            tone: Email tone ('professional', 'casual', 'formal', 'friendly')
            additional_context: Any additional context for email generation
        
        Returns:
            dict with keys: subject, body, success, error
        """
        try:
            if tone == "nothing":
                return self._generate_minimal_edit_email(
                    recipient=recipient,
                    subject_context=subject_context,
                    additional_context=additional_context,
                )

            # Build prompt for email generation
            prompt_text = self._build_email_prompt(
                recipient, subject_context, tone, additional_context
            )
            
            # Generate email using LLM
            response = self.llm.invoke(prompt_text)
            
            # Parse response
            email_dict = self._parse_email_response(response)
            if email_dict["success"]:
                email_dict = self._finalize_email(
                    email_dict,
                    recipient=recipient,
                    subject_context=subject_context,
                    additional_context=additional_context,
                )
                email_dict = self._keep_close_to_original_if_needed(
                    email_dict,
                    recipient=recipient,
                    subject_context=subject_context,
                    additional_context=additional_context,
                )
            
            if email_dict["success"]:
                logger.info(f"✅ Email generated for {recipient}")
            else:
                logger.warning(f"⚠️ Email generation warning: {email_dict['error']}")
            
            return email_dict
        
        except Exception as e:
            logger.error(f"Email generation failed: {e}")
            return {
                "success": False,
                "subject": "",
                "body": "",
                "error": str(e),
            }
    
    @staticmethod
    def _build_email_prompt(
        recipient: str, subject_context: str, tone: str, additional_context: str
    ) -> str:
        """Build prompt for LLM to generate email"""
        tone_description = {
            "professional": "professional, business-appropriate, concise",
            "formal": "formal, official, with proper business etiquette",
            "casual": "casual, friendly, conversational",
            "friendly": "warm, friendly, and personable",
            "nothing": "minimal-edit only, preserving the sender's wording and style",
        }.get(tone, "professional")
        
        prompt = f"""You are an email writing assistant. Return only the email draft in the requested format.

Recipient: {recipient}
User's Original Message: {subject_context}
Email Tone: {tone_description}
{f"Additional Context: {additional_context}" if additional_context else ""}

Generate a complete email with:
1. A short subject line of 1-4 words that summarizes the purpose. Do not copy the body.
2. A natural email body that stays close to the user's original message.
3. Include every important detail from Additional Context in the body.
4. Make only small readability improvements. Do not add new points, explanations, or generic filler.
5. Do not make the email much longer than the user's original message.

Format your response exactly as follows and do not include analysis, notes, markdown, emoji, placeholders, or extra text:
SUBJECT: [subject line here]
BODY:
[email body here]

Keep the email brief, clear, and {tone_description}. Do not repeat SUBJECT or BODY inside the email body."""
        
        return prompt

    @staticmethod
    def _generate_minimal_edit_email(
        recipient: str,
        subject_context: str,
        additional_context: str = "",
    ) -> dict:
        """Create an email with only light cleanup, preserving user wording."""
        raw_message = subject_context.strip()
        if additional_context.strip():
            raw_message = f"{raw_message}\n\n{additional_context.strip()}"

        message = EmailComposer._lightly_refine_message(raw_message)
        body = EmailComposer._format_minimal_body(message, recipient)
        subject = EmailComposer._generate_short_subject(
            subject_context=subject_context,
            additional_context=additional_context,
            current_subject="",
            body=body,
        )

        return {
            "success": True,
            "subject": subject,
            "body": body,
            "error": None,
        }

    @staticmethod
    def _lightly_refine_message(message: str) -> str:
        """Apply tiny readability fixes without rewriting the sender's style."""
        message = EmailComposer._clean_body(message)
        message = EmailComposer._remove_email_labels(message)
        message = EmailComposer._remove_placeholders(message)

        replacements = {
            r"\bplese\b": "please",
            r"\bpls\b": "please",
            r"\bthnks\b": "thanks",
            r"\breguards\b": "regards",
            r"\breguard\b": "regard",
        }
        for pattern, replacement in replacements.items():
            message = re.sub(pattern, replacement, message, flags=re.IGNORECASE)

        lines = []
        for line in message.splitlines():
            cleaned = " ".join(line.strip().split())
            if cleaned:
                cleaned = EmailComposer._capitalize_first(cleaned)
                cleaned = EmailComposer._ensure_sentence_punctuation(cleaned)
                lines.append(cleaned)

        return "\n\n".join(lines).strip()

    @staticmethod
    def _format_minimal_body(message: str, recipient: str) -> str:
        """Wrap the lightly edited message in a simple email format."""
        paragraphs = EmailComposer._split_paragraphs(message)
        paragraphs = EmailComposer._remove_greeting_paragraphs(paragraphs)
        paragraphs = [
            EmailComposer._capitalize_first(paragraph)
            for paragraph in paragraphs
            if not EmailComposer._is_closing(paragraph)
        ]

        if not paragraphs:
            paragraphs = ["I wanted to share this with you."]

        return "\n\n".join(
            [
                f"{EmailComposer._build_greeting(recipient)},",
                *paragraphs,
                "Best regards,",
            ]
        )

    @staticmethod
    def _ensure_sentence_punctuation(text: str) -> str:
        """Add a full stop when the user omitted sentence punctuation."""
        if not text:
            return text
        if re.search(r"[.!?]$", text):
            return text
        return f"{text}."
    
    @staticmethod
    def _parse_email_response(response: str) -> dict:
        """Parse LLM response to extract subject and body"""
        try:
            response_text = EmailComposer._response_to_text(response)
            response_text = EmailComposer._strip_reasoning(response_text)

            subject, body = EmailComposer._extract_labeled_email(response_text)

            if not subject or not body:
                subject, body = EmailComposer._extract_json_email(response_text)

            if not subject or not body:
                subject, body = EmailComposer._extract_fallback_email(response_text)
            
            # Validate extracted content
            if not subject or not body:
                raise ValueError("Subject or body is empty")
            
            # Clean up subject (remove quotes if present)
            subject = EmailComposer._clean_subject(subject)
            body = EmailComposer._clean_body(body)
            
            return {
                "success": True,
                "subject": subject,
                "body": body,
                "error": None,
            }
        
        except Exception as e:
            logger.error(f"Failed to parse email response: {e}")
            return {
                "success": False,
                "subject": "",
                "body": "",
                "error": str(e),
            }

    @staticmethod
    def _response_to_text(response) -> str:
        """Convert LangChain/Ollama responses to plain text."""
        if hasattr(response, "content"):
            return str(response.content).strip()
        return str(response).strip()

    @staticmethod
    def _strip_reasoning(response_text: str) -> str:
        """Remove DeepSeek-R1 style reasoning blocks when present."""
        cleaned = re.sub(
            r"<think>.*?</think>",
            "",
            response_text,
            flags=re.IGNORECASE | re.DOTALL,
        ).strip()
        return cleaned or response_text.strip()

    @staticmethod
    def _extract_labeled_email(response_text: str) -> tuple[str, str]:
        """Extract email from SUBJECT/BODY labels with tolerant spacing/case."""
        patterns = [
            r"(?:^|\n)\s*\**subject\**\s*[:\-]\s*(?P<subject>.+?)\s*(?:\n|\r\n)+\s*\**body\**\s*[:\-]?\s*(?P<body>.+)",
            r"(?:^|\n)\s*subject line\s*[:\-]\s*(?P<subject>.+?)\s*(?:\n|\r\n)+\s*(?:email )?body\s*[:\-]?\s*(?P<body>.+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, response_text, flags=re.IGNORECASE | re.DOTALL)
            if match:
                return match.group("subject").strip(), match.group("body").strip()

        return "", ""

    @staticmethod
    def _extract_json_email(response_text: str) -> tuple[str, str]:
        """Extract email from JSON if the model returns structured data."""
        candidates = [response_text]
        json_block = re.search(r"\{.*\}", response_text, flags=re.DOTALL)
        if json_block:
            candidates.append(json_block.group(0))

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue

            subject = str(parsed.get("subject", "")).strip()
            body = str(parsed.get("body", parsed.get("email_body", ""))).strip()
            if subject and body:
                return subject, body

        return "", ""

    @staticmethod
    def _extract_fallback_email(response_text: str) -> tuple[str, str]:
        """Build a usable draft from plain text when labels are missing."""
        lines = [
            line.strip(" -*#")
            for line in response_text.splitlines()
            if line.strip() and not line.strip().startswith("```")
        ]
        if not lines:
            return "", ""

        first_line = lines[0]
        if len(lines) > 1 and len(first_line.split()) <= 12:
            return first_line, "\n\n".join(lines[1:]).strip()

        subject = EmailComposer._subject_from_body(response_text)
        return subject, response_text.strip()

    @staticmethod
    def _subject_from_body(body: str) -> str:
        """Create a short fallback subject from the generated body."""
        first_sentence = re.split(r"[.!?\n]", body.strip(), maxsplit=1)[0]
        words = first_sentence.split()[:10]
        return " ".join(words) or "Email Update"

    @staticmethod
    def _clean_subject(subject: str) -> str:
        """Normalize generated subject labels and markdown."""
        subject = re.sub(r"^\s*(subject|subject line)\s*[:\-]\s*", "", subject, flags=re.IGNORECASE)
        subject = subject.strip().strip('"\'`*_ ')
        return " ".join(subject.split())[:120]

    @staticmethod
    def _clean_body(body: str) -> str:
        """Normalize generated body text."""
        body = re.sub(r"^\s*(body|email body)\s*[:\-]\s*", "", body, flags=re.IGNORECASE)
        body = body.replace("**", "")
        body = EmailComposer._strip_emoji(body)
        body = re.sub(r"\s*\?{2,}\s*", " ", body)
        body = body.strip().strip("`")
        return body.strip()

    @staticmethod
    def _finalize_email(
        email_dict: dict,
        recipient: str,
        subject_context: str,
        additional_context: str,
    ) -> dict:
        """Polish generated output into a short-subject professional email."""
        body = EmailComposer._format_professional_body(
            email_dict["body"],
            recipient=recipient,
            additional_context=additional_context,
        )
        subject = EmailComposer._generate_short_subject(
            subject_context=subject_context,
            additional_context=additional_context,
            current_subject=email_dict["subject"],
            body=body,
        )

        return {
            **email_dict,
            "subject": subject,
            "body": body,
        }

    @staticmethod
    def _keep_close_to_original_if_needed(
        email_dict: dict,
        recipient: str,
        subject_context: str,
        additional_context: str,
    ) -> dict:
        """Fallback to minimal edit when the model rewrites too heavily."""
        original = f"{subject_context} {additional_context}".strip()
        original_words = EmailComposer._word_count(original)
        body_words = EmailComposer._word_count(email_dict.get("body", ""))

        has_labels = bool(
            re.search(
                r"\b(subject|body)\s*:",
                email_dict.get("body", ""),
                flags=re.IGNORECASE,
            )
        )
        too_long = original_words > 0 and body_words > max(original_words + 25, int(original_words * 1.8))

        if has_labels or too_long:
            return EmailComposer._generate_minimal_edit_email(
                recipient=recipient,
                subject_context=subject_context,
                additional_context=additional_context,
            )

        return email_dict

    @staticmethod
    def _format_professional_body(body: str, recipient: str, additional_context: str) -> str:
        """Ensure the email has greeting, paragraphs, context, and closing."""
        body = EmailComposer._clean_body(body)
        body = EmailComposer._remove_email_labels(body)
        paragraphs = EmailComposer._split_paragraphs(body)

        greeting = EmailComposer._build_greeting(recipient)
        paragraphs = EmailComposer._remove_greeting_paragraphs(paragraphs)
        paragraphs = [EmailComposer._capitalize_first(paragraph) for paragraph in paragraphs]

        if not paragraphs:
            paragraphs = ["I wanted to quickly share this message with you."]

        context_paragraph = EmailComposer._additional_context_paragraph(
            additional_context,
            existing_body="\n".join(paragraphs),
        )
        if context_paragraph:
            insert_at = max(1, len(paragraphs))
            paragraphs.insert(insert_at, context_paragraph)

        closing = "Best regards"
        if paragraphs and EmailComposer._is_closing(paragraphs[-1]):
            paragraphs.pop(-1)

        formatted_parts = [f"{greeting},", *paragraphs, f"{closing},"]
        return "\n\n".join(part.strip() for part in formatted_parts if part.strip())

    @staticmethod
    def _remove_email_labels(body: str) -> str:
        """Remove repeated Subject/Body labels if the model placed them in the body."""
        cleaned_lines = []
        for line in body.splitlines():
            stripped = line.strip().strip("*`# ")
            if not stripped:
                cleaned_lines.append("")
                continue
            if re.match(r"^(subject|subject line)\s*[:\-]", stripped, re.IGNORECASE):
                continue
            stripped = re.sub(r"^(body|email body)\s*[:\-]\s*", "", stripped, flags=re.IGNORECASE)
            cleaned_lines.append(stripped)
        return "\n".join(cleaned_lines).strip()

    @staticmethod
    def _split_paragraphs(body: str) -> list[str]:
        """Split body into clean paragraphs while preserving readable spacing."""
        chunks = re.split(r"\n\s*\n", body)
        paragraphs = []
        for chunk in chunks:
            cleaned = " ".join(
                line.strip().strip("*`# ")
                for line in chunk.splitlines()
                if line.strip()
            )
            cleaned = EmailComposer._remove_placeholders(cleaned)
            if cleaned and not EmailComposer._is_placeholder_text(cleaned):
                paragraphs.append(cleaned)
        return paragraphs

    @staticmethod
    def _remove_greeting_paragraphs(paragraphs: list[str]) -> list[str]:
        """Drop model-created greetings so the app can use the real recipient."""
        cleaned = []
        for paragraph in paragraphs:
            if EmailComposer._starts_with_greeting(paragraph):
                remainder = re.sub(r"^\s*(dear|hello|hi)\b[^,]*,?\s*", "", paragraph, flags=re.IGNORECASE).strip()
                if remainder:
                    cleaned.append(remainder)
                continue
            cleaned.append(paragraph)
        return cleaned

    @staticmethod
    def _build_greeting(recipient: str) -> str:
        """Create a simple professional greeting from name or email."""
        display_name = recipient.split("@", 1)[0] if "@" in recipient else recipient
        display_name = re.sub(r"[._-]+", " ", display_name).strip()
        display_name = " ".join(part.capitalize() for part in display_name.split()[:3])
        return f"Dear {display_name}" if display_name else "Hello"

    @staticmethod
    def _starts_with_greeting(text: str) -> bool:
        return bool(re.match(r"^\s*(dear|hello|hi)\b", text, re.IGNORECASE))

    @staticmethod
    def _is_closing(text: str) -> bool:
        return bool(re.match(r"^\s*(best regards|regards|sincerely|thank you|thanks)\b", text, re.IGNORECASE))

    @staticmethod
    def _remove_placeholders(text: str) -> str:
        text = re.sub(r"\[(?:recipient'?s? name|your name|sender'?s? name|name)\]", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+,", ",", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip(" ,")

    @staticmethod
    def _is_placeholder_text(text: str) -> bool:
        normalized = EmailComposer._normalize_for_compare(text)
        return normalized in {"dear", "hello", "hi", "best regards", "regards", "sincerely", "thank you", "thanks"}

    @staticmethod
    def _additional_context_paragraph(additional_context: str, existing_body: str) -> str:
        """Return a context paragraph if those details are not already present."""
        context = " ".join(additional_context.split())
        if not context:
            return ""

        normalized_context = EmailComposer._normalize_for_compare(context)
        normalized_body = EmailComposer._normalize_for_compare(existing_body)
        if normalized_context and normalized_context in normalized_body:
            return ""

        return f"Additionally, {EmailComposer._lowercase_first(context)}"

    @staticmethod
    def _generate_short_subject(
        subject_context: str,
        additional_context: str,
        current_subject: str,
        body: str,
    ) -> str:
        """Generate a 2-3 word subject that does not copy the body."""
        current = EmailComposer._clean_subject(current_subject)
        current_words = current.split()
        body_start = EmailComposer._normalize_for_compare(body[:160])

        if 1 <= len(current_words) <= 4 and EmailComposer._normalize_for_compare(current) not in body_start:
            return EmailComposer._title_case_subject(current)

        source = f"{subject_context} {additional_context}".strip()
        phrase = EmailComposer._keyword_subject(source)
        return EmailComposer._title_case_subject(phrase or "Email Update")

    @staticmethod
    def _keyword_subject(text: str) -> str:
        """Extract a compact subject phrase from user-provided context."""
        lowered = text.lower()
        phrase_map = [
            (("test", "testing"), "Test Email"),
            (("flight", "delay"), "Flight Delay"),
            (("compensation", "refund", "reimbursement"), "Compensation Details"),
            (("leave", "absence", "sick", "vacation"), "Leave Request"),
            (("meeting", "schedule", "appointment", "call"), "Meeting Request"),
            (("project", "status", "progress"), "Project Update"),
            (("follow", "update"), "Follow Up"),
            (("invoice", "payment", "bill"), "Payment Update"),
            (("resume", "job", "interview"), "Job Application"),
            (("thank", "appreciation"), "Thank You"),
            (("deadline", "timeline"), "Timeline Update"),
            (("feedback", "review"), "Feedback Request"),
        ]
        for keywords, subject in phrase_map:
            if any(keyword in lowered for keyword in keywords):
                return subject

        words = re.findall(r"[A-Za-z][A-Za-z0-9'-]*", text)
        stopwords = {
            "a", "an", "and", "are", "as", "at", "about", "be", "by", "for",
            "from", "i", "in", "is", "it", "my", "of", "on", "or", "our",
            "please", "send", "the", "this", "to", "we", "with", "you", "your",
        }
        keywords = [word for word in words if word.lower() not in stopwords]
        return " ".join(keywords[:3])

    @staticmethod
    def _title_case_subject(subject: str) -> str:
        words = subject.split()[:4]
        return " ".join(word[:1].upper() + word[1:].lower() for word in words)

    @staticmethod
    def _lowercase_first(text: str) -> str:
        if not text:
            return text
        return text[:1].lower() + text[1:]

    @staticmethod
    def _capitalize_first(text: str) -> str:
        if not text:
            return text
        return text[:1].upper() + text[1:]

    @staticmethod
    def _strip_emoji(text: str) -> str:
        return "".join(
            char
            for char in text
            if unicodedata.category(char) not in {"So", "Cs"}
        )

    @staticmethod
    def _normalize_for_compare(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()

    @staticmethod
    def _word_count(text: str) -> int:
        return len(re.findall(r"[A-Za-z0-9']+", text))
    
    @staticmethod
    def validate_email_address(email: str) -> bool:
        """Validate email address format"""
        import re
        email_pattern = r"[\w\.-]+@[\w\.-]+"
        return bool(re.match(email_pattern, email))
    
    @staticmethod
    def resolve_recipient_name_to_email(recipient_name: str, contacts: dict = None) -> str:
        """
        Resolve a recipient name to email address.
        
        Args:
            recipient_name: Name or email of recipient
            contacts: Optional dict of saved contacts {name: email}
        
        Returns:
            Email address or original input if not found in contacts
        """
        # If already an email, return as-is
        if EmailComposer.validate_email_address(recipient_name):
            return recipient_name
        
        # Try to find in contacts
        if contacts:
            name_lower = recipient_name.lower()
            for contact_name, email in contacts.items():
                if contact_name.lower() == name_lower:
                    return email
        
        # If not found, return original (user will need to provide email)
        return recipient_name
