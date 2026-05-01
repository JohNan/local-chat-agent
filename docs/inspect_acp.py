import acp
import inspect
from acp.interfaces import Connection

print(f"Connection.prompt signature: {inspect.signature(Connection.prompt)}")
print(f"Is Connection.prompt async? {inspect.iscoroutinefunction(Connection.prompt)}")
