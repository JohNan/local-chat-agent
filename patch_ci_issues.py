import sys

def fix_frontend():
    with open("frontend/src/App.tsx", "r") as f:
        content = f.read()

    old_catch = "} catch (e) {"
    new_catch = "} catch (_e) {"

    if old_catch in content:
        content = content.replace(old_catch, new_catch)
        with open("frontend/src/App.tsx", "w") as f:
            f.write(content)
        print("Fixed frontend lint issue")
    else:
        print("Could not find catch (e) in frontend")

def fix_backend():
    # Fix unused import
    with open("app/routers/chat.py", "r") as f:
        content = f.read()

    old_import = "from app.services import llm_service, git_ops"
    new_import = "from app.services import git_ops"
    content = content.replace(old_import, new_import)

    with open("app/routers/chat.py", "w") as f:
        f.write(content)
    print("Fixed backend import issue")

    # Fix line too long
    with open("app/services/llm_service.py", "r") as f:
        content = f.read()

    # 702-        # Broadcast everything from the tool output / standard agent text as 'log' for the CLI Terminal
    old_comment = "        # Broadcast everything from the tool output / standard agent text as 'log' for the CLI Terminal"
    new_comment = "        # Broadcast everything from the tool output / standard agent text as 'log'"
    content = content.replace(old_comment, new_comment)

    with open("app/services/llm_service.py", "w") as f:
        f.write(content)
    print("Fixed backend line length issue")

if __name__ == "__main__":
    fix_frontend()
    fix_backend()
