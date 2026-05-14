import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class NotionWorkflowPlanner:
    @staticmethod
    def plan_workflow(intent: str, entities: Dict) -> List[Dict]:
        """
        Generate step-by-step workflow actions based on intent and entities.
        """
        steps = []
        
        if intent == "create_page":
            title = entities.get("title", "Untitled")
            content = entities.get("content")
            
            steps = [
                {
                    "step": 1,
                    "action": "Intent Detection",
                    "description": f"Detected intent: **Create Page**",
                    "status": "complete"
                },
                {
                    "step": 2,
                    "action": "Entity Extraction",
                    "description": f"Extracted title: **{title}**" + (f" and content request" if content else ""),
                    "status": "complete"
                }
            ]
            
            if content:
                steps.append({
                    "step": 3,
                    "action": "Content Generation",
                    "description": f"Generating content related to: {content}",
                    "status": "pending"
                })
            
            next_step = len(steps) + 1
            steps.extend([
                {
                    "step": next_step,
                    "action": "Workflow Planning",
                    "description": "Planning page structure in Notion",
                    "status": "pending"
                },
                {
                    "step": next_step + 1,
                    "action": "Action Generation",
                    "description": "Generating Notion API payload",
                    "status": "pending"
                },
                {
                    "step": next_step + 2,
                    "action": "Notion Executor",
                    "description": "Executing page creation via Notion API",
                    "status": "pending"
                }
            ])
        else:
            steps = [
                {
                    "step": 1,
                    "action": "Analysis",
                    "description": "Analyzing user request...",
                    "status": "complete"
                },
                {
                    "step": 2,
                    "action": "Unknown Intent",
                    "description": "Could not determine a clear Notion action. Please try 'Create a new project page'.",
                    "status": "error"
                }
            ]
            
        return steps
