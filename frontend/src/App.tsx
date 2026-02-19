import { useEffect, useState, useMemo, useRef } from 'react';
import type { InfiniteData } from '@tanstack/react-query';
import './index.css';
import { Header } from './components/Header';
import { ChatInterface } from './components/ChatInterface';
import { InputArea } from './components/InputArea';
import { TasksDrawer } from './components/TasksDrawer';
import { useChatHistory } from './hooks/useChatHistory';
import { generateId } from './utils';
import type { Message, MediaItem, HistoryResponse } from './types';

function App() {
    const {
        data,
        fetchNextPage,
        isFetchingNextPage,
        queryClient
    } = useChatHistory();

    const [model, setModel] = useState("gemini-3-pro-preview");
    const [webSearchEnabled, setWebSearchEnabled] = useState(() => {
        const saved = localStorage.getItem("webSearchEnabled");
        return saved !== null ? JSON.parse(saved) : false;
    });
    const [currentToolStatus, setCurrentToolStatus] = useState<string | null>(null);
    const [isGenerating, setIsGenerating] = useState(false);
    const [isTasksOpen, setIsTasksOpen] = useState(false);
    const abortControllerRef = useRef<AbortController | null>(null);

    // Derived messages state
    const messages = useMemo(() => {
        if (!data) return [];
        // Flatten pages: [Page1 (Older), Page0 (Newer)] -> [OlderMsgs, NewerMsgs]
        // data.pages is [Page0 (Newer), Page1 (Older)]
        return data.pages.slice().reverse().flatMap(page => page.messages);
    }, [data]);

    const addMessage = (msg: Message) => {
        queryClient.setQueryData<InfiniteData<HistoryResponse>>(['chat-history'], (oldData) => {
            if (!oldData) {
                return {
                    pages: [{ messages: [msg], has_more: false }],
                    pageParams: [0]
                } as InfiniteData<HistoryResponse>;
            }
            const newPages = [...oldData.pages];
            if (newPages.length > 0) {
                 const firstPage = { ...newPages[0] };
                 firstPage.messages = [...firstPage.messages, msg];
                 newPages[0] = firstPage;
            }
            return { ...oldData, pages: newPages };
        });
    };

    const updateLastMessage = (updater: (msg: Message) => Message) => {
        queryClient.setQueryData<InfiniteData<HistoryResponse>>(['chat-history'], (oldData) => {
            if (!oldData) return oldData;
            const newPages = [...oldData.pages];
            if (newPages.length > 0) {
                 const firstPage = { ...newPages[0] };
                 firstPage.messages = [...firstPage.messages];
                 const lastIndex = firstPage.messages.length - 1;
                 if (lastIndex >= 0) {
                     firstPage.messages[lastIndex] = updater(firstPage.messages[lastIndex]);
                 }
                 newPages[0] = firstPage;
            }
            return { ...oldData, pages: newPages };
        });
    };

    const readStream = async (
        response: Response,
        onComplete: (currentText: string) => void
    ) => {
        if (!response.body) throw new Error("No response body");
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        let currentText = "";

        let lastUpdate = 0;
        const THROTTLE_MS = 16; // ~60fps

        while (true) {
            const { done, value } = await reader.read();
            if (done) {
                // Final update
                updateLastMessage(last => {
                    if (last && (last.role === 'model' || last.role === 'ai')) {
                        return { ...last, text: currentText, parts: [{ text: currentText }] };
                    }
                    return last;
                });
                onComplete(currentText);
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
                let dataStr = "";

                for (const line of lines) {
                    if (line.startsWith('event: ')) {
                        eventType = line.slice(7).trim();
                    } else if (line.startsWith('data: ')) {
                        dataStr = line.slice(6); // Keep raw data string
                    }
                }

                if (eventType === 'message') {
                    try {
                        const parsedText = JSON.parse(dataStr);
                        currentText += parsedText;
                        hasNewText = true;
                    } catch (e) {
                        console.error("Failed to parse message data:", dataStr, e);
                    }
                } else if (eventType === 'tool') {
                    try {
                        const parsedStatus = JSON.parse(dataStr);
                        setCurrentToolStatus(parsedStatus);
                    } catch (e) {
                        console.warn("Tool status parse error:", e);
                        setCurrentToolStatus("Executing tools...");
                    }
                } else if (eventType === 'done' || eventType === 'error') {
                    if (eventType === 'error') {
                        console.error("Stream error:", dataStr);
                        try {
                            const errorMsg = JSON.parse(dataStr);
                            if (errorMsg) {
                                currentText += `\n\n> **Error**: ${errorMsg}`;
                            }
                        } catch {
                            if (dataStr) {
                                currentText += `\n\n> **Error**: ${dataStr}`;
                            }
                        }
                    }
                    setCurrentToolStatus(null);
                    // Final update
                    updateLastMessage(last => {
                        if (last && (last.role === 'model' || last.role === 'ai')) {
                            return { ...last, text: currentText, parts: [{ text: currentText }] };
                        }
                        return last;
                    });
                    onComplete(currentText);
                    return; // Exit loop
                }
            }

            if (hasNewText) {
                const now = Date.now();
                if (now - lastUpdate > THROTTLE_MS) {
                    updateLastMessage(last => {
                        if (last && (last.role === 'model' || last.role === 'ai')) {
                            return { ...last, text: currentText, parts: [{ text: currentText }] };
                        }
                        return last;
                    });
                    setCurrentToolStatus(null);
                    lastUpdate = now;
                }
            }
        }
    };

    const resumeStream = async () => {
        try {
            const res = await fetch('/api/stream/active');
            if (res.ok) {
                 // Add placeholder for AI message
                const aiMsg: Message = { id: generateId(), role: 'model', text: "", parts: [{text: ""}] };
                addMessage(aiMsg);

                await readStream(res, () => {
                     // On complete, ensure sync
                     queryClient.invalidateQueries({ queryKey: ['chat-history'] });
                });
            }
        } catch (e) {
            console.error("Failed to resume stream", e);
        }
    };

    const handleStop = async () => {
        // Client-side abort
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
        }
        setIsGenerating(false);

        // Backend abort
        try {
            await fetch('/api/stop', { method: 'POST' });
        } catch (e) {
            console.error("Failed to stop backend:", e);
        }
    };

    const sendMessage = async (text: string, media?: MediaItem[]) => {
        // Add user message
        const userMsg: Message = {
            id: generateId(),
            role: 'user',
            text,
            parts: [{text}],
            media: media
        };
        addMessage(userMsg);

        // Add placeholder for AI message
        const aiMsg: Message = { id: generateId(), role: 'model', text: "", parts: [{text: ""}] };
        addMessage(aiMsg);

        setIsGenerating(true);
        const controller = new AbortController();
        abortControllerRef.current = controller;

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: text,
                    model,
                    include_web_search: webSearchEnabled,
                    media: media
                }),
                signal: controller.signal
            });

            await readStream(response, () => {
                queryClient.invalidateQueries({ queryKey: ['chat-history'] });
            });

        } catch (error) {
            if (error instanceof Error && error.name === 'AbortError') {
                console.log("Generation stopped by user");
            } else {
                console.error("Fetch failed:", error);
            }
            setCurrentToolStatus(null);
        } finally {
            setIsGenerating(false);
            abortControllerRef.current = null;
        }
    };

    // Initial load handled by React Query automatically,
    // but we need to check for active stream on mount.
    useEffect(() => {
        resumeStream();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Persist web search preference
    useEffect(() => {
        localStorage.setItem("webSearchEnabled", JSON.stringify(webSearchEnabled));
    }, [webSearchEnabled]);

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
            <Header
                model={model}
                setModel={setModel}
                webSearchEnabled={webSearchEnabled}
                setWebSearchEnabled={setWebSearchEnabled}
                onToggleTasks={() => setIsTasksOpen(!isTasksOpen)}
            />
            <TasksDrawer isOpen={isTasksOpen} onClose={() => setIsTasksOpen(false)} />
            <ChatInterface
                messages={filteredMessages}
                onLoadHistory={fetchNextPage}
                toolStatus={currentToolStatus}
                isLoadingHistory={isFetchingNextPage}
            />
            <InputArea
                onSendMessage={sendMessage}
                isGenerating={isGenerating}
                onStop={handleStop}
            />
        </>
    );
}

export default App;
