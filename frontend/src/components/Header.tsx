import React, { useEffect, useState } from 'react';
import { Bot, GitPullRequestArrow, Trash2, Eraser } from 'lucide-react';
import type { RepoStatus } from '../types';

export const Header: React.FC = () => {
    const [status, setStatus] = useState<RepoStatus | null>(null);
    const [loading, setLoading] = useState(false);

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
        } catch (e) {
            alert("Error resetting context.");
        }
    };

    useEffect(() => {
        updateStatus();
    }, []);

    return (
        <div className="header">
            <div className="header-title">
                <Bot size={24} />
                <span>Gemini Agent</span>
            </div>
            <div className="header-controls">
                <span style={{ fontSize: '0.9em', color: '#aaa' }}>
                    📂 <span id="repo-status">{status ? `${status.project} (${status.branch})` : 'Loading...'}</span>
                </span>
                <button onClick={gitPull} className="icon-btn" title="Git Pull" disabled={loading}>
                    <GitPullRequestArrow size={20} />
                </button>
                <button onClick={clearContext} className="icon-btn" title="Reset Context">
                    <Eraser size={20} />
                </button>
                <button onClick={clearHistory} className="icon-btn" title="Clear History">
                    <Trash2 size={20} />
                </button>
            </div>
        </div>
    );
};
