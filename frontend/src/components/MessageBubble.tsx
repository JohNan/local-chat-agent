import React, { useState } from 'react';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import hljs from 'highlight.js';
import { Bot, Loader2, Rocket, Check, X, User, GitPullRequestArrow, RefreshCw } from 'lucide-react';
import type { Message } from '../types';

// Configure marked with highlight.js
marked.use({
    renderer: {
        code({ text, lang }: { text: string, lang?: string }) {
            const language = lang || 'plaintext';
            const validLanguage = hljs.getLanguage(language) ? language : 'plaintext';
            const highlighted = hljs.highlight(text, { language: validLanguage }).value;
            return `<pre><code class="hljs language-${validLanguage}">${highlighted}</code></pre>`;
        }
    }
});

interface MessageBubbleProps {
    message: Message;
    toolStatus?: string | null;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message, toolStatus }) => {
    const [deploying, setDeploying] = useState(false);
    const [deployResult, setDeployResult] = useState<string | null>(null);
    const [isError, setIsError] = useState(false);
    const [sessionId, setSessionId] = useState<string | null>(null);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const [statusData, setStatusData] = useState<any>(null);
    const [checkingStatus, setCheckingStatus] = useState(false);

    if (message.role === 'system') {
        return (
            <div className="context-reset-divider">
                {message.text || "--- Context Reset ---"}
            </div>
        );
    }

    const isAi = message.role === 'model' || message.role === 'ai';
    const text = message.text || message.parts?.[0]?.text || "";

    const renderMarkdown = (content: string) => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const html = marked.parse(content) as any; // Cast to any to avoid type issues with Promise<string> if marked is misconfigured
        const cleanHtml = DOMPurify.sanitize(html, {
            ADD_TAGS: ['details', 'summary', 'pre', 'code'],
            ADD_ATTR: ['class']
        });
        return { __html: cleanHtml };
    };

    const hasJulesPrompt = text.includes("## Jules Prompt");

    const deploy = async () => {
        setDeploying(true);
        const marker = "## Jules Prompt";
        const markerIndex = text.indexOf(marker);
        let promptText = text;
        if (markerIndex !== -1) {
            // Extract text AFTER the marker
            promptText = text.substring(markerIndex + marker.length);
        }

        // Trim whitespace
        promptText = promptText.trim();

        // Clean markdown code blocks
        promptText = promptText.replace(/^```(markdown)?\s*/, '');
        promptText = promptText.replace(/\s*```$/, '');
        promptText = promptText.trim();

        if (promptText) {
            const lines = promptText.split('\n');
            let title = lines[0];
            // Remove headers
            title = title.replace(/^#+\s*/, '');
            // Remove bold/italic markers
            title = title.replace(/[*_]/g, '');

            lines[0] = title.trim();
            promptText = lines.join('\n');
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
                setSessionId(data.result.name);
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

    const checkStatus = async () => {
        if (!sessionId) return;
        setCheckingStatus(true);
        try {
            const response = await fetch(`/api/jules_session/${sessionId}`);
            const data = await response.json();
            setStatusData(data);
        } catch (e) {
            console.error(e);
            alert("Error checking status");
        } finally {
            setCheckingStatus(false);
        }
    };

    const renderStatus = () => {
        if (!statusData) return null;

        // Find PR URL if exists
        let prUrl = null;
        if (statusData.outputs) {
             // eslint-disable-next-line @typescript-eslint/no-explicit-any
             statusData.outputs.forEach((output: any) => {
                 if (output.pullRequest && output.pullRequest.url) {
                     prUrl = output.pullRequest.url;
                 }
             });
        }

        const state = statusData.state || "UNKNOWN";

        return (
            <div className="status-box" style={{ marginTop: '10px', fontSize: '0.9em', padding: '8px', background: 'rgba(0,0,0,0.05)', borderRadius: '4px' }}>
                <div><strong>Status:</strong> {state}</div>
                {prUrl && (
                    <a href={prUrl} target="_blank" rel="noopener noreferrer" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', marginTop: '4px', color: '#0969da', textDecoration: 'none' }}>
                        <GitPullRequestArrow size={14} />
                        View PR
                    </a>
                )}
            </div>
        );
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
                 {isAi && toolStatus && (
                    <div className="tool-usage" style={{ marginLeft: 0 }}>
                        <Loader2 size={16} className="animate-spin" />
                        {toolStatus}
                    </div>
                 )}
                 {isAi && hasJulesPrompt && (
                     <div className="jules-controls" style={{ marginTop: '8px' }}>
                         {!deployResult ? (
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
                             <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                 <button className="deploy-btn" disabled>
                                     {isError ? <X size={16} /> : <Check size={16} />}
                                     {deployResult}
                                 </button>

                                 {sessionId && !isError && (
                                     <button className="deploy-btn" onClick={checkStatus} disabled={checkingStatus} style={{ background: '#f0f0f0', color: '#333', border: '1px solid #ccc' }}>
                                         {checkingStatus ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                                         Check Status
                                     </button>
                                 )}

                                 {renderStatus()}
                             </div>
                         )}
                     </div>
                 )}
            </div>
        </div>
    );
};
