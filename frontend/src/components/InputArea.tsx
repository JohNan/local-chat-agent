import React, { useState } from 'react';

interface InputAreaProps {
    onSendMessage: (text: string) => void;
    disabled?: boolean;
}

export const InputArea: React.FC<InputAreaProps> = ({ onSendMessage, disabled }) => {
    const [input, setInput] = useState("");

    const handleSend = () => {
        if (input.trim()) {
            onSendMessage(input.trim());
            setInput("");
        }
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            handleSend();
        }
    };

    return (
        <div className="input-area">
            <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Ask about your code..."
                disabled={disabled}
            />
            <button className="primary-btn" onClick={handleSend} disabled={disabled || !input.trim()}>
                Send
            </button>
        </div>
    );
};
