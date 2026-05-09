"""
Intent Parser - Extract email intent and entities from user input
Uses regex and keyword-based parsing for reliable entity extraction
"""
import re
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class IntentParser:
    """Parse user input for email-related intents and entities"""

    # Email intent keywords
    EMAIL_KEYWORDS = {
        "send": ["send", "compose", "write", "draft", "mail"],
        "reply": ["reply", "respond"],
        "forward": ["forward"],
    }

    # Entity patterns
    EMAIL_PATTERN = r"[\w\.-]+@[\w\.-]+"
    NAME_PATTERN = r"(?:to|@|send to|for)\s+([A-Za-z\s]+?)(?:\s+at|$|,|\.|with|about)"
    
    @staticmethod
    def detect_intent(user_input: str) -> Optional[str]:
        """
        Detect if user wants to send email.
        Returns: 'send_email' or None
        """
        user_lower = user_input.lower()
        
        for intent, keywords in IntentParser.EMAIL_KEYWORDS.items():
            for keyword in keywords:
                if keyword in user_lower and any(
                    w in user_lower for w in ["email", "mail", "send", "write"]
                ):
                    return "send_email"
        
        return None

    @staticmethod
    def extract_recipient(user_input: str) -> Optional[str]:
        """
        Extract recipient email or name from user input.
        Returns: email address or name, or None
        """
        # Try to find email address first
        email_match = re.search(IntentParser.EMAIL_PATTERN, user_input)
        if email_match:
            return email_match.group(0)
        
        # Try to find recipient name
        name_patterns = [
            r"to\s+([A-Za-z\s]+?)(?:\s+about|\s+with|\s+regarding|$)",
            r"send.*?to\s+([A-Za-z\s]+?)(?:\s+about|\s+with|$)",
            r"@\s*([A-Za-z\s]+?)(?:\s+|$)",
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                recipient = match.group(1).strip()
                if len(recipient) > 2 and len(recipient) < 50:  # Sanity check
                    return recipient
        
        return None

    @staticmethod
    def extract_subject_context(user_input: str) -> Optional[str]:
        """
        Extract email subject/purpose context from user input.
        Returns: subject context or None
        """
        patterns = [
            r"about\s+(.+?)(?:\s+to\s+|$)",
            r"regarding\s+(.+?)(?:\s+to\s+|$)",
            r"with\s+(.+?)(?:\s+to\s+|$)",
            r"send.*?about\s+(.+?)(?:\s+to\s+|$)",
            r"subject:?\s+(.+?)(?:\s+to\s+|$)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                context = match.group(1).strip()
                if len(context) > 2:
                    return context
        
        # If no pattern matches, extract after "to" recipient name
        parts = re.split(r"\s+(about|regarding|with)\s+", user_input, flags=re.IGNORECASE)
        if len(parts) > 2:
            return parts[-1].strip()
        
        return None

    @staticmethod
    def extract_tone(user_input: str) -> str:
        """
        Extract desired email tone from user input.
        Returns: tone ('professional', 'casual', 'formal', 'friendly')
        """
        user_lower = user_input.lower()
        
        tone_keywords = {
            "formal": ["formal", "official", "business"],
            "professional": ["professional", "corporate"],
            "casual": ["casual", "friendly", "informal"],
            "friendly": ["friendly", "warm", "kind"],
        }
        
        for tone, keywords in tone_keywords.items():
            for keyword in keywords:
                if keyword in user_lower:
                    return tone
        
        return "professional"  # Default tone

    @staticmethod
    def parse_email_request(user_input: str) -> Optional[Dict]:
        """
        Parse complete email request from user input.
        
        Returns:
            dict with keys: recipient, subject_context, tone, raw_input
            or None if not an email request
        """
        intent = IntentParser.detect_intent(user_input)
        if intent != "send_email":
            return None
        
        recipient = IntentParser.extract_recipient(user_input)
        subject_context = IntentParser.extract_subject_context(user_input)
        tone = IntentParser.extract_tone(user_input)
        
        if not recipient:
            logger.warning("No recipient found in user input")
            return None
        
        return {
            "recipient": recipient,
            "subject_context": subject_context or "General",
            "tone": tone,
            "raw_input": user_input,
        }
