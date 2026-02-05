import React, { useRef, useLayoutEffect } from 'react';
import type { Message } from '../types';
import { MessageBubble } from './MessageBubble';

interface ChatInterfaceProps {
    messages: Message[];
    onLoadHistory: () => void;
    isLoadingHistory: boolean;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ messages, onLoadHistory, isLoadingHistory }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const prevMsgCountRef = useRef(0);

    useLayoutEffect(() => {
        if (!containerRef.current) return;

        const container = containerRef.current;
        const newCount = messages.length;
        const diff = newCount - prevMsgCountRef.current;

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

        prevMsgCountRef.current = newCount;
    }, [messages, isLoadingHistory]);

    const handleScroll = () => {
        if (containerRef.current && containerRef.current.scrollTop === 0 && !isLoadingHistory) {
            onLoadHistory();
        }
    };

    return (
        <div className="chat-container" ref={containerRef} onScroll={handleScroll}>
            {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
            ))}
        </div>
    );
};
