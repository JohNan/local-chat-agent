export interface MessagePart {
    text: string;
}

export interface Message {
    id: string;
    role: 'user' | 'model' | 'ai' | 'function';
    parts?: MessagePart[];
    text?: string; // Helper for when we flatten it
    thought?: string;
}

export interface HistoryResponse {
    messages: Message[];
    has_more: boolean;
}

export interface RepoStatus {
    project: string;
    branch: string;
}
