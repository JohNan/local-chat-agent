from acp import schema
import inspect

for cls_name in ["AgentMessageChunk", "AgentThoughtChunk", "UserMessageChunk", "TextContentBlock"]:
    cls = getattr(schema, cls_name, None)
    if cls:
        print(f"--- {cls_name} ---")
        try:
            # For Pydantic models, __fields__ or model_fields might be available
            if hasattr(cls, "model_fields"):
                print(f"Fields: {list(cls.model_fields.keys())}")
            elif hasattr(cls, "__fields__"):
                print(f"Fields: {list(cls.__fields__.keys())}")
            else:
                print(f"Attributes: {[a for a in dir(cls) if not a.startswith('_')]}")
        except Exception as e:
            print(f"Error inspecting {cls_name}: {e}")
