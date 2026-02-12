import React, { useState, useRef } from 'react';
import { Paperclip, X } from 'lucide-react';
import type { MediaItem } from '../types';

interface InputAreaProps {
    onSendMessage: (text: string, media?: MediaItem[]) => void;
    disabled?: boolean;
    isGenerating?: boolean;
    onStop?: () => void;
}

export const InputArea: React.FC<InputAreaProps> = ({ onSendMessage, disabled, isGenerating, onStop }) => {
    const [input, setInput] = useState("");
    const [mediaItems, setMediaItems] = useState<MediaItem[]>([]);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleSend = () => {
        if (input.trim() || mediaItems.length > 0) {
            onSendMessage(input.trim(), mediaItems.length > 0 ? mediaItems : undefined);
            setInput("");
            setMediaItems([]);
        }
    };

    const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files) {
            const newFiles = Array.from(e.target.files);
            const newMediaItems: MediaItem[] = [];

            for (const file of newFiles) {
                try {
                    const base64 = await new Promise<string>((resolve, reject) => {
                        const reader = new FileReader();
                        reader.onload = () => resolve(reader.result as string);
                        reader.onerror = reject;
                        reader.readAsDataURL(file);
                    });
                    // remove "data:image/png;base64," prefix for backend
                    const data = base64.split(',')[1];
                    newMediaItems.push({ mime_type: file.type, data: data });
                } catch (err) {
                    console.error("Error reading file:", err);
                }
            }
            setMediaItems(prev => [...prev, ...newMediaItems]);
            // Clear input so same file can be selected again
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    };

    const removeMedia = (index: number) => {
        setMediaItems(prev => prev.filter((_, i) => i !== index));
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', width: '100%' }}>
            {mediaItems.length > 0 && (
                <div className="media-preview" style={{
                    display: 'flex',
                    gap: '10px',
                    padding: '10px 20px',
                    backgroundColor: 'var(--chat-bg)',
                    borderTop: '1px solid var(--border-color)',
                    overflowX: 'auto'
                }}>
                    {mediaItems.map((item, index) => (
                        <div key={index} className="media-thumbnail" style={{ position: 'relative', width: '60px', height: '60px' }}>
                            <img
                                src={`data:${item.mime_type};base64,${item.data}`}
                                alt="preview"
                                style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '4px' }}
                            />
                            <button
                                onClick={() => removeMedia(index)}
                                style={{
                                    position: 'absolute',
                                    top: '-5px',
                                    right: '-5px',
                                    background: 'red',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '50%',
                                    width: '18px',
                                    height: '18px',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    cursor: 'pointer',
                                    padding: 0
                                }}
                            >
                                <X size={12} />
                            </button>
                        </div>
                    ))}
                </div>
            )}
            <div className="input-area">
                <input
                    type="file"
                    multiple
                    accept="image/*"
                    ref={fileInputRef}
                    style={{ display: 'none' }}
                    onChange={handleFileSelect}
                />
                <button
                    className="icon-btn"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={disabled || isGenerating}
                    title="Attach images"
                >
                    <Paperclip size={20} />
                </button>
                <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Ask about your code..."
                    disabled={disabled || isGenerating}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                            e.preventDefault();
                            if (!disabled && !isGenerating && (input.trim() || mediaItems.length > 0)) {
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
                    <button className="primary-btn" onClick={handleSend} disabled={disabled || (!input.trim() && mediaItems.length === 0)}>
                        Send
                    </button>
                )}
            </div>
        </div>
    );
};
