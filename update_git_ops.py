with open('app/services/git_ops.py', 'r') as f:
    content = f.read()

old_code = """            except subprocess.CalledProcessError as e:
                logger.error("Failed to create PR: %s", e.stderr)
                output += "\\nFailed to create PR: " + (e.stderr or e.stdout)"""

new_code = """            except subprocess.CalledProcessError as e:
                logger.error("Failed to create PR: %s", e.stderr)
                err_msg = e.stderr or e.stdout
                if "gh auth login" in err_msg or "not authenticated" in err_msg:
                    output += "\\n\\nFailed to create PR: GitHub CLI (gh) is not authenticated. Please run 'gh auth login' in your terminal to authenticate, or use the link provided above to create the PR manually."
                else:
                    output += "\\nFailed to create PR: " + err_msg"""

content = content.replace(old_code, new_code)

with open('app/services/git_ops.py', 'w') as f:
    f.write(content)
