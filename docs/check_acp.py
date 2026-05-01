import sys
import json

try:
    import acp
    import acp.schema
    
    classes = [
        "AgentMessageChunk",
        "AgentThoughtChunk",
        "UserMessageChunk",
        "ToolCallStart",
        "ToolCallProgress",
        "TextContentBlock",
        "ResourceContentBlock",
        "AgentPlanUpdate",
    ]
    
    available = {}
    for cls in classes:
        available[cls] = hasattr(acp.schema, cls)
        
    print(json.dumps(available, indent=2))
except Exception as e:
    print(f"Error: {e}")
