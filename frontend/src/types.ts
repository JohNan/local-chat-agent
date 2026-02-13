export interface MediaItem {
    data: string;
    mime_type: string;
}

export interface MessagePart {
    text: string;
}

export interface Message {
    id: string;
    role: 'user' | 'model' | 'ai' | 'function' | 'system';
    parts?: MessagePart[];
    text?: string; // Helper for when we flatten it
    media?: MediaItem[];
}

export interface HistoryResponse {
    messages: Message[];
    has_more: boolean;
}

export interface RepoStatus {
    project: string;
    branch: string;
    active_persona?: string | null;
}
