import React from 'react';

interface InputAreaProps {
    value: string;
    onChange: (value: string) => void;
    onSendMessage: (text: string) => void;
    disabled?: boolean;
    isGenerating?: boolean;
    onStop?: () => void;
}

export const InputArea: React.FC<InputAreaProps> = ({
    value,
    onChange,
    onSendMessage,
    disabled,
    isGenerating,
    onStop
}) => {
    const handleSend = () => {
        if (value.trim()) {
            onSendMessage(value.trim());
        }
    };

    return (
        <div className="input-area">
            <textarea
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder="Ask about your code..."
                disabled={disabled || isGenerating}
                onKeyDown={(e) => {
                    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                        e.preventDefault();
                        if (!disabled && !isGenerating && value.trim()) {
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
                <button className="primary-btn" onClick={handleSend} disabled={disabled || !value.trim()}>
                    Send
                </button>
            )}
        </div>
    );
};
