import React, { useState } from 'react';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { Bot, Loader2, Rocket, Check, X, User } from 'lucide-react';
import type { Message } from '../types';

interface MessageBubbleProps {
    message: Message;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
    const isAi = message.role === 'model' || message.role === 'ai';
    const text = message.text || message.parts?.[0]?.text || "";
    const [deploying, setDeploying] = useState(false);
    const [deployResult, setDeployResult] = useState<string | null>(null);
    const [isError, setIsError] = useState(false);

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
                setDeployResult(`Started! (${sessionName})`);
                setIsError(false);
            } else {
                setDeployResult("Error: " + data.error);
                setIsError(true);
                alert("Error deploying: " + data.error);
            }
        } catch (e) {
            console.error(e);
            setDeployResult("Error");
            setIsError(true);
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
                     <Bot size={20} />
                ) : (
                     <User size={20} />
                )}
            </div>
            <div className="message-bubble">
                 <div dangerouslySetInnerHTML={renderMarkdown(text)} />
                 {isAi && hasJulesPrompt && (
                     !deployResult ? (
                         <button className="deploy-btn" onClick={deploy} disabled={deploying}>
                             {deploying ? (
                                 <>
                                    <Loader2 size={16} className="animate-spin" />
                                    Sending...
                                 </>
                             ) : (
                                 <>
                                    <Rocket size={16} />
                                    Start Jules Task
                                 </>
                             )}
                         </button>
                     ) : (
                         <button className="deploy-btn" disabled>
                             {isError ? <X size={16} /> : <Check size={16} />}
                             {deployResult}
                         </button>
                     )
                 )}
            </div>
        </div>
    );
};
