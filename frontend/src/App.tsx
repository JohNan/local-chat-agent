import { useEffect, useState, useCallback } from 'react';
import './index.css';
import { Header } from './components/Header';
import { ChatInterface } from './components/ChatInterface';
import { InputArea } from './components/InputArea';
import type { Message } from './types';

function App() {
    const [messages, setMessages] = useState<Message[]>([]);
    const [toolStatus, setToolStatus] = useState<string | null>(null);
    const [offset, setOffset] = useState(0);
    const [hasMore, setHasMore] = useState(true);
    const [loadingHistory, setLoadingHistory] = useState(false);

    const loadHistory = useCallback(async () => {
        if (loadingHistory || !hasMore) return;
        setLoadingHistory(true);
        try {
            const limit = 20;
            const res = await fetch(`/api/history?limit=${limit}&offset=${offset}`);
            const data = await res.json();

            if (data.messages && data.messages.length > 0) {
                // Ensure text property exists
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                const formattedMessages = data.messages.map((m: any) => ({
                    ...m,
                    text: m.parts?.[0]?.text || m.text || ""
                }));

                setMessages(prev => [...formattedMessages, ...prev]);
                setOffset(prev => prev + data.messages.length);
                setHasMore(data.has_more);
            } else {
                setHasMore(false);
            }
        } catch (e) {
            console.error(e);
        } finally {
            setLoadingHistory(false);
        }
    }, [offset, hasMore, loadingHistory]);

    const sendMessage = async (text: string) => {
        // Add user message
        const userMsg: Message = { role: 'user', text, parts: [{text}] };
        setMessages(prev => [...prev, userMsg]);
        setOffset(prev => prev + 1);

        // Add placeholder for AI message
        const aiMsg: Message = { role: 'model', text: "", parts: [{text: ""}] };
        setMessages(prev => [...prev, aiMsg]);

        let currentText = "";

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text })
            });

            if (!response.body) throw new Error("No response body");
            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");
            let buffer = "";

            // eslint-disable-next-line no-constant-condition
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const parts = buffer.split('\n\n');
                buffer = parts.pop() || ""; // Keep incomplete chunk

                for (const part of parts) {
                    if (!part.trim()) continue;
                    const lines = part.split('\n');
                    let eventType = "";
                    let data = "";

                    for (const line of lines) {
                        if (line.startsWith('event: ')) {
                            eventType = line.slice(7).trim();
                        } else if (line.startsWith('data: ')) {
                            data = line.slice(6); // Keep raw data string
                        }
                    }

                    if (eventType === 'message') {
                        try {
                             // data is like "Hello", so JSON.parse removes quotes
                            const parsedText = JSON.parse(data);
                            currentText += parsedText;
                            setMessages(prev => {
                                const newMsgs = [...prev];
                                const lastIndex = newMsgs.length - 1;
                                const last = newMsgs[lastIndex];
                                if (last && (last.role === 'model' || last.role === 'ai')) {
                                    newMsgs[lastIndex] = { ...last, text: currentText, parts: [{text: currentText}] };
                                }
                                return newMsgs;
                            });
                            setToolStatus(null);
                        } catch (e) {
                            console.error("Failed to parse message data:", data, e);
                        }
                    } else if (eventType === 'tool') {
                        setToolStatus(data || "Executing tools...");
                    } else if (eventType === 'done' || eventType === 'error') {
                        if (eventType === 'error') console.error("Stream error:", data);
                        setToolStatus(null);
                        return; // Exit loop
                    }
                }
            }
        } catch (error) {
            console.error("Fetch failed:", error);
            setToolStatus(null);
        }
    };

    // Initial load
    useEffect(() => {
        loadHistory();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return (
        <>
            <Header />
            <ChatInterface
                messages={messages}
                onLoadHistory={loadHistory}
                toolStatus={toolStatus}
                isLoadingHistory={loadingHistory}
            />
            <InputArea onSendMessage={sendMessage} />
        </>
    );
}

export default App;
