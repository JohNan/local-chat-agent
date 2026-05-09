import React, { useEffect, useState } from 'react';
import { Bot, GitPullRequestArrow, Trash2, Eraser, Settings, X, List, LayoutTemplate, Smartphone, Box, Server, MessageSquare, FileText, Upload } from 'lucide-react';
import type { RepoStatus } from '../types';

interface HeaderProps {
    model: string;
    setModel: (model: string) => void;
    webSearchEnabled: boolean;
    setWebSearchEnabled: (enabled: boolean) => void;
    embeddingsEnabled: boolean;
    setEmbeddingsEnabled: (enabled: boolean) => void;
    onToggleTasks: () => void;
    isGenerating: boolean;
    cliEditEnabled?: boolean;
    setCliEditEnabled?: (val: boolean) => void;
}

export const Header: React.FC<HeaderProps> = ({
    model,
    setModel,
    webSearchEnabled,
    setWebSearchEnabled,
    embeddingsEnabled,
    setEmbeddingsEnabled,
    onToggleTasks,
    isGenerating,
    cliEditEnabled,
    setCliEditEnabled
}) => {
    const [status, setStatus] = useState<RepoStatus | null>(null);
    const [loading, setLoading] = useState(false);
    const [showSettings, setShowSettings] = useState(false);
    const [showAgentInfo, setShowAgentInfo] = useState(false);

    const [showPushModal, setShowPushModal] = useState(false);
    const [pushFiles, setPushFiles] = useState<string[]>([]);
    const [pushBranchName, setPushBranchName] = useState("");
    const [pushCommitMessage, setPushCommitMessage] = useState("");
    const [pushing, setPushing] = useState(false);
    const [switchBack, setSwitchBack] = useState(true);

    const [availableModels, setAvailableModels] = useState<string[]>([
        "gemini-3-pro-preview",
        "gemini-2.0-flash-exp",
        "gemini-1.5-pro"
    ]);

    useEffect(() => {
        const fetchModels = async () => {
            try {
                const res = await fetch('/api/models');
                if (res.ok) {
                    const data = await res.json();
                    if (data.models && Array.isArray(data.models)) {
                        setAvailableModels(data.models);
                    }
                }
            } catch (e) {
                console.error("Failed to fetch models:", e);
            }
        };
        fetchModels();
    }, [showSettings]);

    const updateStatus = async () => {
        try {
            const res = await fetch('/api/status');
            const data = await res.json();
            setStatus(data);
        } catch (e) {
            console.error(e);
        }
    };


    const gitStatus = async () => {
        if (loading) return;
        setLoading(true);
        try {
            const res = await fetch('/api/git_status');
            const data = await res.json();
            if (data.status && data.status.length > 0) {
                setPushFiles(data.status);
                const timestamp = new Date().getTime();
                setPushBranchName(`docs-update-${timestamp}`);
                setPushCommitMessage("docs: update documentation");
                setShowPushModal(true);
            } else {
                alert("No changes to push");
            }
        } catch (e) {
            alert('Error: ' + (e as Error).message);
        } finally {
            setLoading(false);
        }
    };

    const submitPush = async () => {
        if (pushing) return;
        setPushing(true);
        try {
            const res = await fetch('/api/git_push', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    branch_name: pushBranchName,
                    commit_message: pushCommitMessage,
                    switch_back: switchBack
                })
            });
            const data = await res.json();
            if (data.success) {
                alert("Push successful\n" + data.output);
                setShowPushModal(false);
                updateStatus();
            } else {
                alert("Push failed\n" + data.output);
            }
        } catch (e) {
            alert('Error: ' + (e as Error).message);
        } finally {
            setPushing(false);
        }
    };

    const gitPull = async () => {
        if (loading) return;
        setLoading(true);
        try {
            const res = await fetch('/api/git_pull', { method: 'POST' });
            const data = await res.json();
            alert(data.output);
            updateStatus();
        } catch (e) {

            alert('Error: ' + (e as Error).message);
        } finally {
            setLoading(false);
        }
    };

    const clearHistory = async () => {
        if (!confirm("Are you sure you want to clear the chat history?")) return;
        try {
            const res = await fetch('/api/reset', { method: 'POST' });
            const data = await res.json();
            if (data.status === 'success') {
                window.location.reload();
            } else {
                alert("Failed to clear history: " + (data.error || "Unknown error"));
            }
        } catch {
            alert("Error clearing history.");
        }
    };

    const clearContext = async () => {
        if (!confirm("Are you sure you want to reset the AI context?")) return;
        try {
            await fetch('/api/context_reset', { method: 'POST' });
            window.location.reload();
        } catch {
            alert("Error resetting context.");
        }
    };

    const clearAndRebuildRag = async () => {
        if (!window.confirm("Are you sure you want to clear and rebuild the RAG index for this repository?")) return;
        try {
            const res = await fetch('/api/rag/clear_and_reindex', { method: 'POST' });
            const data = await res.json();
            alert(data.status || data.error || "Unknown response");
        } catch (e) {
            alert("Error clearing and rebuilding RAG index: " + (e as Error).message);
        }
    };

    useEffect(() => {
        updateStatus();
    }, [isGenerating]);

    const getPersonaIcon = (persona?: string) => {
        switch (persona) {
            case 'UI': return <LayoutTemplate size={20} />;
            case 'MOBILE': return <Smartphone size={20} />;
            case 'ARCHITECT': return <Box size={20} />;
            case 'CI_CD': return <Server size={20} />;
            case 'PLANNER': return <FileText size={20} />;
            default: return <MessageSquare size={20} />;
        }
    };

    return (
        <>
            <div className="header">
                <div className="header-title" onClick={() => setShowAgentInfo(!showAgentInfo)} style={{ cursor: 'pointer', position: 'relative' }}>
                    <Bot size={24} className={isGenerating ? "animate-pulse" : ""} color={isGenerating ? "#4caf50" : "currentColor"} />
                    <span>Gemini Agent</span>
                    <div
                        title={status?.active_persona || "General"}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            marginLeft: '10px',
                            cursor: 'pointer',
                        }}
                    >
                        {getPersonaIcon(status?.active_persona)}
                    </div>
                    {showAgentInfo && (
                        <div className="agent-info-popover" onClick={(e) => e.stopPropagation()}>
                            <div className="agent-info-item">
                                <span className="agent-info-label">Model:</span>
                                <span className="agent-info-value">{model}</span>
                            </div>
                            <div className="agent-info-item">
                                <span className="agent-info-label">Project:</span>
                                <span className="agent-info-value">{status?.project || 'N/A'}</span>
                            </div>
                            <div className="agent-info-item">
                                <span className="agent-info-label">Branch:</span>
                                <span className="agent-info-value">{status?.branch || 'N/A'}</span>
                            </div>
                            <div className="agent-info-item">
                                <span className="agent-info-label">Persona:</span>
                                <span className="agent-info-value">{status?.active_persona || 'General'}</span>
                            </div>
                            <div className="agent-info-item">
                                <span className="agent-info-label">Context Size:</span>
                                <span className="agent-info-value">{status?.token_count != null ? `${status.token_count.toLocaleString()} tokens` : 'Loading...'}</span>
                            </div>
                        </div>
                    )}
                </div>
                <div className="header-controls">
                    <button onClick={onToggleTasks} className="icon-btn" title="Tasks">
                        <List size={20} />
                    </button>
                    <button onClick={clearContext} className="icon-btn" title="Reset Context">
                        <Eraser size={20} />
                    </button>
                    <button onClick={() => setShowSettings(true)} className="icon-btn" title="Settings">
                        <Settings size={20} />
                    </button>
                </div>
            </div>

            {showSettings && (
                <div className="settings-overlay">
                    <div className="settings-modal">
                        <div className="settings-header">
                            <h3>Settings</h3>
                            <button onClick={() => setShowSettings(false)} className="icon-btn">
                                <X size={20} />
                            </button>
                        </div>

                        <div className="settings-content">
                             <div className="setting-item">
                                <label>Repository</label>
                                <span id="repo-status" style={{ display: 'block', padding: '5px 0' }}>
                                    {status ? `${status.project} (${status.branch})` : 'Loading...'}
                                </span>
                            </div>

                            <div className="setting-item">
                                <label>Language Servers</label>
                                {status?.lsp_servers && status.lsp_servers.length > 0 ? (
                                    <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                                        {status.lsp_servers.map((s, idx) => (
                                            <li key={idx} style={{
                                                fontSize: '0.9rem',
                                                marginBottom: '5px',
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'space-between',
                                                backgroundColor: 'var(--bg-secondary)',
                                                padding: '5px',
                                                borderRadius: '4px'
                                            }}>
                                                <span>{s.language}</span>
                                                <span title={s.root_path} style={{ opacity: 0.7, fontSize: '0.8rem', maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                                     {s.root_path.split('/').pop()}
                                                </span>
                                                <span style={{
                                                    color: s.status === 'running' ? '#4caf50' : '#f44336',
                                                    fontSize: '0.8rem'
                                                }}>
                                                    {s.status}
                                                </span>
                                            </li>
                                        ))}
                                    </ul>
                                ) : (
                                    <span style={{ opacity: 0.7, fontSize: '0.9rem' }}>No active servers</span>
                                )}
                            </div>

                             <div className="setting-item">
                                <label>Model</label>
                                <select
                                    value={model}
                                    onChange={(e) => setModel(e.target.value)}
                                    className="model-select"
                                >
                                    {availableModels.map((m) => (
                                        <option key={m} value={m}>
                                            {m}
                                        </option>
                                    ))}
                                </select>
                            </div>

                            <div className="setting-item" style={{ flexDirection: 'row', alignItems: 'center', gap: '10px' }}>
                                <input
                                    type="checkbox"
                                    id="web-search-checkbox"
                                    checked={webSearchEnabled}
                                    onChange={(e) => setWebSearchEnabled(e.target.checked)}
                                    style={{ width: 'auto' }}
                                />
                                <label htmlFor="web-search-checkbox" style={{ margin: 0, cursor: 'pointer' }}>
                                    Enable Web Search
                                </label>
                            </div>

                            <div className="setting-item" style={{ flexDirection: 'row', alignItems: 'center', gap: '10px' }}>
                                <input
                                    type="checkbox"
                                    id="embeddings-checkbox"
                                    checked={embeddingsEnabled}
                                    onChange={(e) => setEmbeddingsEnabled(e.target.checked)}
                                    style={{ width: 'auto' }}
                                />
                                <label htmlFor="embeddings-checkbox" style={{ margin: 0, cursor: 'pointer' }}>
                                    Enable Embeddings & RAG
                                </label>
                            </div>

                            <div className="setting-item" style={{ flexDirection: 'row', alignItems: 'center', gap: '10px', marginBottom: '15px' }}>
                                <input
                                    type="checkbox"
                                    id="cli-edit-checkbox"
                                    checked={!!cliEditEnabled}
                                    onChange={(e) => setCliEditEnabled?.(e.target.checked)}
                                    style={{ width: 'auto' }}
                                />
                                <label htmlFor="cli-edit-checkbox" style={{ margin: 0, cursor: 'pointer' }}>
                                    Enable CLI Edit Mode (Local Auto-Fix)
                                </label>
                            </div>
                            <div className="setting-item">
                                <button
                                    onClick={clearAndRebuildRag}
                                    className="icon-btn"
                                    title="Clear & Rebuild RAG Index"
                                    style={{
                                        border: '1px solid #454545',
                                        width: '100%',
                                        justifyContent: 'center',
                                        gap: '10px',
                                        padding: '8px'
                                    }}
                                >
                                    <Server size={20} />
                                    <span>Clear & Rebuild RAG Index</span>
                                </button>
                            </div>

                            <div className="setting-actions" style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '10px' }}>

                                <div style={{ display: 'flex', gap: '10px' }}>
                                    <button
                                        onClick={gitPull}
                                        className="icon-btn"
                                        title="Git Pull"
                                        disabled={loading}
                                        style={{
                                            border: '1px solid #454545',
                                            flex: 1,
                                            justifyContent: 'center',
                                            gap: '10px',
                                            padding: '8px'
                                        }}
                                    >
                                        <GitPullRequestArrow size={20} />
                                        <span>Git Pull</span>
                                    </button>
                                    <button
                                        onClick={gitStatus}
                                        className="icon-btn"
                                        title="Git Push"
                                        disabled={loading}
                                        style={{
                                            border: '1px solid #454545',
                                            flex: 1,
                                            justifyContent: 'center',
                                            gap: '10px',
                                            padding: '8px'
                                        }}
                                    >
                                        <Upload size={20} />
                                        <span>Git Push</span>
                                    </button>
                                </div>

                                <button
                                    onClick={clearHistory}
                                    className="icon-btn"
                                    title="Clear History"
                                    style={{
                                        border: '1px solid #454545',
                                        width: '100%',
                                        justifyContent: 'center',
                                        gap: '10px',
                                        padding: '8px'
                                    }}
                                >
                                    <Trash2 size={20} />
                                    <span>Clear History</span>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {showPushModal && (
                <div className="settings-overlay" style={{ zIndex: 1100 }}>
                    <div className="settings-modal" style={{ maxWidth: '500px' }}>
                        <div className="settings-header">
                            <h3>Push Changes</h3>
                            <button onClick={() => setShowPushModal(false)} className="icon-btn" disabled={pushing}>
                                <X size={20} />
                            </button>
                        </div>
                        <div className="settings-content">
                            <div className="setting-item">
                                <label>Changed Files</label>
                                <ul style={{ listStyle: 'none', padding: 0, margin: 0, maxHeight: '150px', overflowY: 'auto', backgroundColor: 'var(--bg-secondary)', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
                                    {pushFiles.map((file, idx) => (
                                        <li key={idx} style={{ padding: '5px 10px', fontSize: '0.9rem', borderBottom: idx < pushFiles.length - 1 ? '1px solid var(--border-color)' : 'none', fontFamily: 'monospace' }}>
                                            {file}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                            <div className="setting-item">
                                <label>Branch Name</label>
                                <input
                                    type="text"
                                    value={pushBranchName}
                                    onChange={(e) => setPushBranchName(e.target.value)}
                                    disabled={pushing}
                                    style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid var(--border-color)', backgroundColor: 'var(--chat-bg)', color: 'var(--text-color)' }}
                                />
                            </div>
                            <div className="setting-item">
                                <label>Commit Message</label>
                                <input
                                    type="text"
                                    value={pushCommitMessage}
                                    onChange={(e) => setPushCommitMessage(e.target.value)}
                                    disabled={pushing}
                                    style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid var(--border-color)', backgroundColor: 'var(--chat-bg)', color: 'var(--text-color)' }}
                                />
                            </div>
                            <div className="setting-item" style={{ flexDirection: 'row', alignItems: 'center', gap: '10px' }}>
                                <input
                                    type="checkbox"
                                    id="switch-back-checkbox"
                                    checked={switchBack}
                                    onChange={(e) => setSwitchBack(e.target.checked)}
                                    disabled={pushing}
                                    style={{ width: 'auto' }}
                                />
                                <label htmlFor="switch-back-checkbox" style={{ margin: 0, cursor: 'pointer' }}>
                                    Switch back to previous branch after push
                                </label>
                            </div>
                            <div className="setting-actions" style={{ marginTop: '20px', display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                                <button
                                    onClick={() => setShowPushModal(false)}
                                    className="icon-btn"
                                    disabled={pushing}
                                    style={{ padding: '8px 16px', border: '1px solid var(--border-color)' }}
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={submitPush}
                                    className="icon-btn"
                                    disabled={pushing || !pushBranchName || !pushCommitMessage}
                                    style={{ padding: '8px 16px', backgroundColor: 'var(--user-msg-bg)', color: 'white', border: 'none' }}
                                >
                                    {pushing ? 'Pushing...' : 'Confirm Push'}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

        </>
    );
};
