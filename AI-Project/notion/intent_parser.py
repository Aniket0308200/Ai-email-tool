import json
import logging
from typing import Dict, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_ollama import ChatOllama

logger = logging.getLogger(__name__)

class NotionIntentParser:
    def __init__(self, model: str = "deepseek-r1:1.5b"):
        self.llm = ChatOllama(
            model=model,
            base_url="http://localhost:11434",
            temperature=0,
        )
        self.parser = JsonOutputParser()
        
    def parse_intent(self, user_input: str) -> Dict:
        """
        Extract intent and entities from user input using LLM.
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert intent parser for Notion. "
                       "Analyze the user's request and extract the intent and required entities. "
                       "Supported intents: 'create_page'. "
                       "Required entities for 'create_page': 'title'. "
                       "Optional entities: 'content_instructions' (any specific details, points, or requirements for the page content). "
                       "\n\n"
                       "Rules:\n"
                       "1. Return ONLY a valid JSON object.\n"
                       "2. If the user wants specific content or points (e.g., 'make 5 points about HTML'), put that instruction in 'content_instructions'.\n"
                       "3. If the intent is to create a page, set 'intent' to 'create_page'.\n"
                       "4. If you cannot find a clear intent, set 'intent' to 'unknown'.\n"
                       "\n"
                       "Example Input: 'Create a new project page about marketing with 3 points on SEO'\n"
                       "Example Output: {{\"intent\": \"create_page\", \"entities\": {{\"title\": \"Marketing\", \"content_instructions\": \"3 points on SEO\"}}}}"),
            ("human", "{input}")
        ])
        
        chain = prompt | self.llm | self.parser
        
        try:
            result = chain.invoke({"input": user_input})
            
            # Ensure consistency: map content_instructions to content if LLM used the new name
            if "content_instructions" in result.get("entities", {}):
                result["entities"]["content"] = result["entities"]["content_instructions"]

            if result.get("intent") == "unknown" and ("create" in user_input.lower() or "page" in user_input.lower()):
                return self._fallback_parse(user_input)
                
            return result
        except Exception as e:
            logger.error(f"Error parsing Notion intent: {e}")
            return self._fallback_parse(user_input)

    def _fallback_parse(self, user_input: str) -> Dict:
        """Simple regex-based fallback."""
        user_lower = user_input.lower()
        if "create" in user_lower or "new page" in user_lower:
            import re
            # Extract title: look for what's between 'title is/named/called' and 'and/with/make'
            title = "New Page"
            title_match = re.search(r"(?:title is|named|called|create a page|new page)\s+([A-Za-z0-9\s]+?)(?:\s+(?:and|with|make|related|for)|$)", user_input, re.IGNORECASE)
            if title_match:
                title = title_match.group(1).strip()
            
            # Extract content: everything after 'and', 'with', 'make', or 'related'
            content = ""
            content_match = re.search(r"(?:and|with|make|related to|containing)\s+(.*)$", user_input, re.IGNORECASE)
            if content_match:
                content = content_match.group(1).strip()
            
            # If title is still 'New Page' and we have content, maybe the title is before the content keywords
            if title == "New Page" and content:
                # e.g. "Create a page for HTML and make points" -> title is "HTML"
                alt_title_match = re.search(r"(?:create a page for|create a page about|new page for)\s+([A-Za-z0-9\s]+?)(?:\s+(?:and|with|make|related|for)|$)", user_input, re.IGNORECASE)
                if alt_title_match:
                    title = alt_title_match.group(1).strip()

            return {
                "intent": "create_page",
                "entities": {
                    "title": title.title(),
                    "content": content
                }
            }
        return {"intent": "unknown", "entities": {}}
