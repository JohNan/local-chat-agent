import React, { useState } from 'react';

interface InputAreaProps {
    onSendMessage: (text: string) => void;
    disabled?: boolean;
    isGenerating?: boolean;
    onStop?: () => void;
}

export const InputArea: React.FC<InputAreaProps> = ({ onSendMessage, disabled, isGenerating, onStop }) => {
    const [input, setInput] = useState("");

    const handleSend = () => {
        if (input.trim()) {
            onSendMessage(input.trim());
            setInput("");
        }
    };

    return (
        <div className="input-area">
            <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about your code..."
                disabled={disabled || isGenerating}
                onKeyDown={(e) => {
                    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                        e.preventDefault();
                        if (!disabled && !isGenerating && input.trim()) {
                            handleSend();
                        }
                    }
                }}
            />
            {isGenerating ? (
                <button className="stop-btn" onClick={onStop}>
                    Stop
                </button>
            ) : (
                <button className="primary-btn" onClick={handleSend} disabled={disabled || !input.trim()}>
                    Send
                </button>
            )}
        </div>
    );
};
