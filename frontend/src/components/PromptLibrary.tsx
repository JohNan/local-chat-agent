import React, { useEffect, useState } from 'react';
import { Trash2, ArrowUp, X } from 'lucide-react';

interface PromptLibraryProps {
    isOpen: boolean;
    onClose: () => void;
    onSelectPrompt: (prompt: string) => void;
}

export const PromptLibrary: React.FC<PromptLibraryProps> = ({ isOpen, onClose, onSelectPrompt }) => {
    const [prompts, setPrompts] = useState<string[]>([]);
    const [loading, setLoading] = useState(false);

    const fetchPrompts = async () => {
        setLoading(true);
        try {
            const res = await fetch('/prompts');
            if (res.ok) {
                const data = await res.json();
                setPrompts(data.prompts || []);
            }
        } catch (e) {
            console.error("Failed to fetch prompts:", e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (isOpen) {
            fetchPrompts();
        }
    }, [isOpen]);

    const handleDelete = async (index: number) => {
        if (!confirm("Are you sure you want to delete this prompt?")) return;

        try {
            const res = await fetch(`/prompts/${index}`, { method: 'DELETE' });
            if (res.ok) {
                // Optimistic update or refetch
                fetchPrompts();
            } else {
                alert("Failed to delete prompt");
            }
        } catch (e) {
            console.error("Failed to delete prompt:", e);
        }
    };

    return (
        <div className={`prompt-library-drawer ${isOpen ? 'open' : ''}`}>
            <div className="prompt-library-header">
                <h3>Saved Prompts</h3>
                <button onClick={onClose} className="icon-btn" title="Close">
                    <X size={20} />
                </button>
            </div>

            <div className="prompt-list">
                {loading ? (
                    <div className="loading-prompts">Loading...</div>
                ) : prompts.length === 0 ? (
                    <div className="no-prompts">No saved prompts yet.<br/>Start a message with "## Jules Prompt" to save one.</div>
                ) : (
                    prompts.map((prompt, index) => (
                        <div key={index} className="prompt-item">
                            <div className="prompt-preview">
                                {prompt.slice(0, 60)}{prompt.length > 60 ? '...' : ''}
                            </div>
                            <div className="prompt-actions">
                                <button
                                    onClick={() => {
                                        onSelectPrompt(prompt);
                                        onClose();
                                    }}
                                    className="icon-btn"
                                    title="Use Prompt"
                                >
                                    <ArrowUp size={18} />
                                </button>
                                <button
                                    onClick={() => handleDelete(index)}
                                    className="icon-btn delete-btn"
                                    title="Delete"
                                >
                                    <Trash2 size={18} />
                                </button>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};
