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

    const sendMessage = (text: string) => {
        // Add user message
        const userMsg: Message = { role: 'user', text, parts: [{text}] };
        setMessages(prev => [...prev, userMsg]);
        setOffset(prev => prev + 1);

        // Start stream
        const streamUrl = '/chat?message=' + encodeURIComponent(text);
        const source = new EventSource(streamUrl);

        // Add placeholder for AI message
        const aiMsg: Message = { role: 'model', text: "", parts: [{text: ""}] };
        setMessages(prev => [...prev, aiMsg]);

        let currentText = "";

        source.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                currentText += data;

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
                console.error(e);
            }
        };

        source.addEventListener("tool", (event) => {
            setToolStatus(event.data || "Executing tools...");
        });

        source.addEventListener("done", () => {
            source.close();
            setToolStatus(null);
        });

        source.addEventListener("error", (e) => {
            if (source.readyState !== 2) {
                 console.error("EventSource failed:", e);
            }
            source.close();
            setToolStatus(null);
        });
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
