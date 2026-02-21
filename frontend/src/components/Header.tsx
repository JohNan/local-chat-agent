import React, { useEffect, useState } from 'react';
import { Bot, GitPullRequestArrow, Trash2, Eraser, Settings, X, List, LayoutTemplate, Smartphone, Box, Server, MessageSquare } from 'lucide-react';
import type { RepoStatus } from '../types';

interface HeaderProps {
    model: string;
    setModel: (model: string) => void;
    webSearchEnabled: boolean;
    setWebSearchEnabled: (enabled: boolean) => void;
    onToggleTasks: () => void;
}

export const Header: React.FC<HeaderProps> = ({
    model,
    setModel,
    webSearchEnabled,
    setWebSearchEnabled,
    onToggleTasks,
}) => {
    const [status, setStatus] = useState<RepoStatus | null>(null);
    const [loading, setLoading] = useState(false);
    const [showSettings, setShowSettings] = useState(false);
    const [showPersonaName, setShowPersonaName] = useState(false);
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

    const gitPull = async () => {
        if (loading) return;
        setLoading(true);
        try {
            const res = await fetch('/api/git_pull', { method: 'POST' });
            const data = await res.json();
            alert(data.output);
            updateStatus();
        } catch (e) {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            alert('Error: ' + (e as any).message);
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

    useEffect(() => {
        updateStatus();
    }, []);

    const getPersonaIcon = (persona?: string) => {
        switch (persona) {
            case 'UI': return <LayoutTemplate size={20} />;
            case 'MOBILE': return <Smartphone size={20} />;
            case 'ARCHITECT': return <Box size={20} />;
            case 'CI_CD': return <Server size={20} />;
            default: return <MessageSquare size={20} />;
        }
    };

    return (
        <>
            <div className="header">
                <div className="header-title">
                    <Bot size={24} />
                    <span>Gemini Agent</span>
                    <div
                        title={status?.active_persona || "General"}
                        onClick={() => setShowPersonaName(!showPersonaName)}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            marginLeft: '10px',
                            cursor: 'pointer',
                            position: 'relative'
                        }}
                    >
                        {getPersonaIcon(status?.active_persona)}
                        {showPersonaName && (
                            <div style={{
                                position: 'absolute',
                                top: '120%',
                                left: '50%',
                                transform: 'translateX(-50%)',
                                backgroundColor: 'var(--chat-bg)',
                                border: '1px solid var(--border-color)',
                                padding: '5px 10px',
                                borderRadius: '4px',
                                zIndex: 1000,
                                whiteSpace: 'nowrap',
                                boxShadow: '0 2px 5px rgba(0,0,0,0.5)',
                                color: 'var(--text-color)',
                                fontSize: '0.8rem'
                            }}>
                                {status?.active_persona || "General"}
                            </div>
                        )}
                    </div>
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

                            <div className="setting-actions" style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                                <button
                                    onClick={gitPull}
                                    className="icon-btn"
                                    title="Git Pull"
                                    disabled={loading}
                                    style={{
                                        border: '1px solid #454545',
                                        width: '100%',
                                        justifyContent: 'center',
                                        gap: '10px',
                                        padding: '8px'
                                    }}
                                >
                                    <GitPullRequestArrow size={20} />
                                    <span>Git Pull</span>
                                </button>
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
        </>
    );
};
