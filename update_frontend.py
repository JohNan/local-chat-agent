import re

with open("frontend/src/components/Header.tsx", "r") as f:
    content = f.read()

# Add states for branch selection
state_addition = """    const [pushBranchName, setPushBranchName] = useState("");
    const [createNewBranch, setCreateNewBranch] = useState(false);
    const [currentBranchName, setCurrentBranchName] = useState("");"""

content = re.sub(
    r'    const \[pushBranchName, setPushBranchName\] = useState\(""\);',
    state_addition,
    content,
)

# Update gitStatus function
gitStatus_old = """                setPushFiles(data.status);
                setPushBranchName(data.suggested_branch_name || data.branch || "main");
                setPushCommitMessage(data.suggested_commit_message || "chore: update files");
                setShowPushModal(true);"""

gitStatus_new = """                setPushFiles(data.status);
                setCurrentBranchName(data.branch || "main");
                
                // If there's a suggested branch that is different from current, default to creating a new branch
                const suggested = data.suggested_branch_name || "";
                if (suggested && suggested !== data.branch) {
                    setCreateNewBranch(true);
                    setPushBranchName(suggested);
                } else {
                    setCreateNewBranch(false);
                    setPushBranchName(data.branch || "main");
                }
                
                setPushCommitMessage(data.suggested_commit_message || "chore: update files");
                setShowPushModal(true);"""

content = content.replace(gitStatus_old, gitStatus_new)

# Update the "Branch Name" UI in the modal
branch_ui_old = """                            <div className="setting-item">
                                <label>Branch Name</label>
                                <input
                                    type="text"
                                    value={pushBranchName}
                                    onChange={(e) => setPushBranchName(e.target.value)}
                                    disabled={pushing}
                                    style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid var(--border-color)', backgroundColor: 'var(--chat-bg)', color: 'var(--text-color)' }}
                                />
                            </div>"""

branch_ui_new = """                            <div className="setting-item">
                                <label>Branch</label>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                    <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontWeight: 'normal' }}>
                                        <input
                                            type="radio"
                                            checked={!createNewBranch}
                                            onChange={() => {
                                                setCreateNewBranch(false);
                                                setPushBranchName(currentBranchName);
                                            }}
                                            disabled={pushing}
                                        />
                                        Push to current branch ({currentBranchName})
                                    </label>
                                    <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontWeight: 'normal' }}>
                                        <input
                                            type="radio"
                                            checked={createNewBranch}
                                            onChange={() => {
                                                setCreateNewBranch(true);
                                                // We don't reset pushBranchName here so it retains what they typed or the suggestion
                                            }}
                                            disabled={pushing}
                                        />
                                        Create new branch
                                    </label>
                                    {createNewBranch && (
                                        <input
                                            type="text"
                                            value={pushBranchName}
                                            onChange={(e) => setPushBranchName(e.target.value)}
                                            disabled={pushing}
                                            placeholder="Enter branch name"
                                            style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid var(--border-color)', backgroundColor: 'var(--chat-bg)', color: 'var(--text-color)', marginTop: '4px' }}
                                        />
                                    )}
                                </div>
                            </div>"""

content = content.replace(branch_ui_old, branch_ui_new)

# Also wait, when submitting the push!
# We use pushBranchName
# What if createNewBranch is false, pushBranchName is currentBranchName, which is correct.
# Wait, let's make sure the backend pushes to the current branch.

with open("frontend/src/components/Header.tsx", "w") as f:
    f.write(content)
