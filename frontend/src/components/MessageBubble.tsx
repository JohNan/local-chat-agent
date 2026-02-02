import React, { useState } from 'react';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import type { Message } from '../types';

interface MessageBubbleProps {
    message: Message;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
    const isAi = message.role === 'model' || message.role === 'ai';
    const text = message.text || message.parts?.[0]?.text || "";
    const [deploying, setDeploying] = useState(false);
    const [deployResult, setDeployResult] = useState<string | null>(null);

    const renderMarkdown = (content: string) => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const html = marked.parse(content) as any; // Cast to any to avoid type issues with Promise<string> if marked is misconfigured
        const cleanHtml = DOMPurify.sanitize(html);
        return { __html: cleanHtml };
    };

    const hasJulesPrompt = text.includes("## Jules Prompt");

    const deploy = async () => {
        setDeploying(true);
        const marker = "## Jules Prompt";
        const markerIndex = text.indexOf(marker);
        let promptText = text;
        if (markerIndex !== -1) {
            promptText = text.substring(markerIndex);
        }

        try {
            const response = await fetch('/api/deploy_to_jules', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt: promptText })
            });
            const data = await response.json();
            if (data.success) {
                const sessionName = data.result.name || "Unknown Session";
                setDeployResult(`✅ Started! (${sessionName})`);
            } else {
                setDeployResult("❌ Error: " + data.error);
                alert("Error deploying: " + data.error);
            }
        } catch (e) {
            console.error(e);
            setDeployResult("❌ Error");
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            alert("Error deploying: " + (e as any).message);
        } finally {
            setDeploying(false);
        }
    };

    return (
        <div className={`message-row ${isAi ? 'ai' : 'user'}`}>
            <div className="avatar">
                {isAi ? (
                     <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"></path></svg>
                ) : (
                     <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
                )}
            </div>
            <div className="message-bubble">
                 <div dangerouslySetInnerHTML={renderMarkdown(text)} />
                 {isAi && hasJulesPrompt && (
                     !deployResult ? (
                         <button className="deploy-btn" onClick={deploy} disabled={deploying}>
                             {deploying ? "⏳ Sending..." : "🚀 Start Jules Task"}
                         </button>
                     ) : (
                         <button className="deploy-btn" disabled>
                             {deployResult}
                         </button>
                     )
                 )}
            </div>
        </div>
    );
};
