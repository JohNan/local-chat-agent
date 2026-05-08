import React, { useState, useEffect } from 'react';
import { Terminal, Check, X } from 'lucide-react';

interface ActionRequest {
    action_id: string;
    type: string;
    data: {
        name: string;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        arguments: any;
    }
}

interface CLITerminalProps {
    isOpen: boolean;
    onClose: () => void;
    logs: string[];
    pendingAction: ActionRequest | null;
    onResolveAction: (action_id: string, decision: 'approve' | 'reject' | 'edit', editedArgs?: any) => void;
}

export const CLITerminal: React.FC<CLITerminalProps> = ({ isOpen, onClose, logs, pendingAction, onResolveAction }) => {
    const [editedArgs, setEditedArgs] = useState<string>('');

    useEffect(() => {
        if (pendingAction) {
            setEditedArgs(JSON.stringify(pendingAction.data.arguments, null, 2));
        }
    }, [pendingAction]);

    if (!isOpen) return null;

    const handleApprove = () => {
        if (pendingAction) {
            onResolveAction(pendingAction.action_id, 'approve');
        }
    };

    const handleReject = () => {
        if (pendingAction) {
            onResolveAction(pendingAction.action_id, 'reject');
        }
    };

    const handleEdit = () => {
        if (pendingAction) {
            try {
                const parsed = JSON.parse(editedArgs);
                onResolveAction(pendingAction.action_id, 'edit', parsed);
            } catch (e) {
                alert("Invalid JSON in edited arguments.");
            }
        }
    };

    return (
        <div style={{
            position: 'fixed',
            bottom: '20px',
            right: '20px',
            width: '400px',
            maxHeight: '500px',
            backgroundColor: 'var(--bg-secondary)',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            display: 'flex',
            flexDirection: 'column',
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            zIndex: 1000,
            overflow: 'hidden'
        }}>
            <div style={{
                padding: '10px',
                borderBottom: '1px solid var(--border-color)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                backgroundColor: 'var(--chat-bg)'
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 'bold' }}>
                    <Terminal size={18} />
                    CLI Workspace
                </div>
                <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-color)' }}>
                    <X size={18} />
                </button>
            </div>

            <div style={{ flex: 1, overflowY: 'auto', padding: '10px', fontFamily: 'monospace', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {logs.length === 0 ? (
                    <div style={{ color: '#888', fontStyle: 'italic' }}>Waiting for output...</div>
                ) : (
                    logs.map((log, i) => (
                        <div key={i} style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{log}</div>
                    ))
                )}
            </div>

            {pendingAction && (
                <div style={{
                    padding: '15px',
                    borderTop: '1px solid var(--border-color)',
                    backgroundColor: 'rgba(255, 165, 0, 0.1)'
                }}>
                    <h4 style={{ margin: '0 0 10px 0', color: '#ff9800' }}>Action Required: {pendingAction.data.name}</h4>
                    <textarea
                        value={editedArgs}
                        onChange={(e) => setEditedArgs(e.target.value)}
                        style={{ width: '100%', height: '80px', fontFamily: 'monospace', fontSize: '12px', backgroundColor: 'var(--chat-bg)', color: 'var(--text-color)', border: '1px solid var(--border-color)', borderRadius: '4px', padding: '5px' }}
                    />
                    <div style={{ display: 'flex', gap: '8px', marginTop: '10px' }}>
                        <button onClick={handleApprove} style={{ flex: 1, padding: '6px', backgroundColor: '#2da44e', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '4px' }}>
                            <Check size={14} /> Approve
                        </button>
                        <button onClick={handleEdit} style={{ flex: 1, padding: '6px', backgroundColor: '#0969da', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '4px' }}>
                            <Check size={14} /> Approve with Edits
                        </button>
                        <button onClick={handleReject} style={{ flex: 1, padding: '6px', backgroundColor: '#cf222e', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '4px' }}>
                            <X size={14} /> Reject
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};
