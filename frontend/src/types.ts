export interface MessagePart {
    text: string;
}

export interface Message {
    role: 'user' | 'model' | 'ai';
    parts?: MessagePart[];
    text?: string; // Helper for when we flatten it
}

export interface HistoryResponse {
    messages: Message[];
    has_more: boolean;
}

export interface RepoStatus {
    project: string;
    branch: string;
}
