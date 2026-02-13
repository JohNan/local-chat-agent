import React, { useEffect, useRef, useLayoutEffect } from 'react';
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
    const prevMsgCountRef = useRef(0);
    const scrollHeightRef = useRef(0);
    const prevLastMsgIdRef = useRef<string | null>(null);

    useLayoutEffect(() => {
        if (!containerRef.current) return;

        const container = containerRef.current;
        const newCount = messages.length;
        const diff = newCount - prevMsgCountRef.current;
        const currentLastMsgId = messages.length > 0 ? messages[messages.length - 1].id : null;

        if (diff > 0) {
            // New messages added
            if (currentLastMsgId !== prevLastMsgIdRef.current) {
                // Case 1: Last Message Changed (New Message / Append)
                // This implies a new user message or a new AI response started.
                container.scrollTop = container.scrollHeight;
            } else {
                // Case 2: Last Message Same (History Load / Prepend)
                // This implies messages were added to the start of the list.
                // Maintain relative scroll position.
                const newScrollTop = container.scrollHeight - scrollHeightRef.current;
                container.scrollTop = newScrollTop;
            }
        }

        // Update refs for next render
        scrollHeightRef.current = container.scrollHeight;
        prevMsgCountRef.current = newCount;
        prevLastMsgIdRef.current = currentLastMsgId;
    }, [messages]);

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
            {messages.map((msg, index) => {
                let deployedSessionId = null;
                const nextMsg = messages[index + 1];
                if (nextMsg && nextMsg.role === 'model') {
                    const text = nextMsg.text || nextMsg.parts?.[0]?.text || "";
                    if (text.startsWith("Started Jules task:")) {
                        const match = text.match(/Started Jules task: ([^\n]+)/);
                        if (match) {
                            deployedSessionId = match[1].trim();
                        }
                    }
                }

                return (
                    <MessageBubble
                        key={msg.id}
                        message={msg}
                        toolStatus={index === messages.length - 1 ? toolStatus : null}
                        deployedSessionId={deployedSessionId}
                    />
                );
            })}
        </div>
    );
};
