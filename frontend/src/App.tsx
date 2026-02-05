import { useEffect, useState, useCallback, useMemo } from 'react';
import './index.css';
import { Header } from './components/Header';
import { ChatInterface } from './components/ChatInterface';
import { InputArea } from './components/InputArea';
import type { Message } from './types';

const generateId = () => {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        return crypto.randomUUID();
    }
    return Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
};

function App() {
    const [messages, setMessages] = useState<Message[]>([]);
    const [model, setModel] = useState("gemini-3-pro-preview");
    const [currentToolStatus, setCurrentToolStatus] = useState<string | null>(null);
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
                    id: m.id || generateId(),
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
        const userMsg: Message = { id: generateId(), role: 'user', text, parts: [{text}] };
        setMessages(prev => [...prev, userMsg]);
        setOffset(prev => prev + 1);

        // Add placeholder for AI message
        const aiMsg: Message = { id: generateId(), role: 'model', text: "", parts: [{text: ""}] };
        setMessages(prev => [...prev, aiMsg]);

        let currentText = "";

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text, model })
            });

            if (!response.body) throw new Error("No response body");
            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");
            let buffer = "";

            let lastUpdate = 0;
            const THROTTLE_MS = 16; // ~60fps

            while (true) {
                const { done, value } = await reader.read();
                if (done) {
                    // Final update to ensure we didn't miss anything
                    setMessages(prev => {
                        const newMsgs = [...prev];
                        const lastIndex = newMsgs.length - 1;
                        const last = newMsgs[lastIndex];
                        if (last && (last.role === 'model' || last.role === 'ai')) {
                            newMsgs[lastIndex] = { ...last, text: currentText, parts: [{ text: currentText }] };
                        }
                        return newMsgs;
                    });
                    break;
                }

                buffer += decoder.decode(value, { stream: true });
                const parts = buffer.split('\n\n');
                buffer = parts.pop() || ""; // Keep incomplete chunk

                let hasNewText = false;

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
                            hasNewText = true;
                        } catch (e) {
                            console.error("Failed to parse message data:", data, e);
                        }
                    } else if (eventType === 'tool') {
                        try {
                            // Now we expect a JSON string, just like 'message' events
                            const parsedStatus = JSON.parse(data);
                            setCurrentToolStatus(parsedStatus);
                        } catch (e) {
                            console.warn("Tool status parse error:", e);
                            // Fallback if something goes wrong, but show the error
                            setCurrentToolStatus("Executing tools...");
                        }
                    } else if (eventType === 'done' || eventType === 'error') {
                        if (eventType === 'error') console.error("Stream error:", data);
                        setCurrentToolStatus(null);
                        // Final update to ensure we didn't miss anything
                        setMessages(prev => {
                            const newMsgs = [...prev];
                            const lastIndex = newMsgs.length - 1;
                            const last = newMsgs[lastIndex];
                            if (last && (last.role === 'model' || last.role === 'ai')) {
                                newMsgs[lastIndex] = { ...last, text: currentText, parts: [{ text: currentText }] };
                            }
                            return newMsgs;
                        });
                        return; // Exit loop
                    }
                }

                if (hasNewText) {
                    const now = Date.now();
                    if (now - lastUpdate > THROTTLE_MS) {
                        setMessages(prev => {
                            const newMsgs = [...prev];
                            const lastIndex = newMsgs.length - 1;
                            const last = newMsgs[lastIndex];
                            if (last && (last.role === 'model' || last.role === 'ai')) {
                                newMsgs[lastIndex] = { ...last, text: currentText, parts: [{ text: currentText }] };
                            }
                            return newMsgs;
                        });
                        setCurrentToolStatus(null);
                        lastUpdate = now;
                    }
                }
            }
        } catch (error) {
            console.error("Fetch failed:", error);
            setCurrentToolStatus(null);
        }
    };

    // Initial load
    useEffect(() => {
        loadHistory();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const filteredMessages = useMemo(() => {
        return messages.filter((m, index) => {
            // Hide function outputs
            if (m.role === 'function') return false;

            // Hide "Thought" messages (model messages followed by function)
            if ((m.role === 'model' || m.role === 'ai') && index + 1 < messages.length) {
                const nextMsg = messages[index + 1];
                if (nextMsg.role === 'function') return false;
            }

            return true;
        });
    }, [messages]);

    return (
        <>
            <Header model={model} setModel={setModel} />
            <ChatInterface
                messages={filteredMessages}
                onLoadHistory={loadHistory}
                toolStatus={currentToolStatus}
                isLoadingHistory={loadingHistory}
            />
            <InputArea onSendMessage={sendMessage} />
        </>
    );
}

export default App;
