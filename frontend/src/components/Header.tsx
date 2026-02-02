import React, { useEffect, useState } from 'react';
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
        } catch (e) {
            alert("Error clearing history.");
        }
    };

    useEffect(() => {
        updateStatus();
    }, []);

    return (
        <div className="header">
            <div className="header-title">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"></path>
                </svg>
                <span>Gemini Agent</span>
            </div>
            <div className="header-controls">
                <span style={{ fontSize: '0.9em', color: '#aaa' }}>
                    📂 <span id="repo-status">{status ? `${status.project} (${status.branch})` : 'Loading...'}</span>
                </span>
                <button onClick={gitPull} className="icon-btn" title="Git Pull" disabled={loading}>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2 2v-4"></path>
                        <polyline points="7 10 12 15 17 10"></polyline>
                        <line x1="12" y1="15" x2="12" y2="3"></line>
                    </svg>
                </button>
                <button onClick={clearHistory} className="icon-btn" title="Clear History">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>
                </button>
            </div>
        </div>
    );
};
