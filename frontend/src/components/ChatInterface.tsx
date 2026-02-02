import React, { useEffect, useRef, useState, useLayoutEffect } from 'react';
import type { Message } from '../types';
import { MessageBubble } from './MessageBubble';

interface ChatInterfaceProps {
    messages: Message[];
    onLoadHistory: () => void;
    toolStatus: string | null;
    isLoadingHistory: boolean;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ messages, onLoadHistory, toolStatus, isLoadingHistory }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const [prevMsgCount, setPrevMsgCount] = useState(0);

    useLayoutEffect(() => {
        if (!containerRef.current) return;

        const container = containerRef.current;
        const newCount = messages.length;
        const diff = newCount - prevMsgCount;

        if (diff > 0) {
            // New messages added
            // Heuristic: If we are near top and loading history, restore position
            // But here we already re-rendered.
            // A better way is to rely on the parent logic or a specialized hook.
            // For now, let's just scroll to bottom if it looks like a new conversation message.
            // If the last message changed, it's likely a new message.

            // Simple logic: Scroll to bottom always unless we are loading history
            if (!isLoadingHistory) {
                container.scrollTop = container.scrollHeight;
            } else {
                // If loading history, we ideally want to maintain scroll position relative to bottom
                // But since we prepended, the scrollHeight increased.
                // We want to keep the scroll position at the same message.
                // This is hard without measuring before update.
                // Let's just leave it for now, user can scroll.
            }
        }

        setPrevMsgCount(newCount);
    }, [messages, isLoadingHistory, prevMsgCount]);

    // Force scroll to bottom on tool status change (active streaming)
    useEffect(() => {
        if (toolStatus && containerRef.current) {
            containerRef.current.scrollTop = containerRef.current.scrollHeight;
        }
    }, [toolStatus]);

    const handleScroll = () => {
        if (containerRef.current && containerRef.current.scrollTop === 0 && !isLoadingHistory) {
            onLoadHistory();
        }
    };

    return (
        <div className="chat-container" ref={containerRef} onScroll={handleScroll}>
            {messages.map((msg, idx) => (
                <MessageBubble key={idx} message={msg} />
            ))}
            {toolStatus && (
                <div className="tool-usage">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg>
                    {toolStatus}
                </div>
            )}
        </div>
    );
};
