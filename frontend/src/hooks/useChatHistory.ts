import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query';
import { generateId } from '../utils';
import type { MediaItem, HistoryResponse } from '../types';

const fetchHistory = async ({ pageParam = 0 }): Promise<HistoryResponse> => {
    const limit = 20;
    const res = await fetch(`/api/history?limit=${limit}&offset=${pageParam}`);

    if (!res.ok) {
        throw new Error(`Failed to fetch history: ${res.statusText}`);
    }

    const data = await res.json();

    // Validate response shape
    if (!data || !Array.isArray(data.messages)) {
        throw new Error("Invalid history response format");
    }

    if (data.messages.length > 0) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const formattedMessages = data.messages.map((m: any) => {
            const media: MediaItem[] = [];
            if (m.parts) {
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                m.parts.forEach((p: any) => {
                    if (p.inline_data) {
                        media.push(p.inline_data);
                    }
                });
            }
            return {
                ...m,
                id: m.id || generateId(),
                text: m.parts?.[0]?.text || m.text || "",
                media: media.length > 0 ? media : undefined
            };
        });
        return { ...data, messages: formattedMessages };
    }
    return data;
};

export const useChatHistory = () => {
    const queryClient = useQueryClient();

    const query = useInfiniteQuery({
        queryKey: ['chat-history'],
        initialPageParam: 0,
        queryFn: fetchHistory,
        getNextPageParam: (lastPage, allPages) => {
            if (!lastPage.has_more) return undefined;
            // Calculate total messages loaded so far to determine next offset
            const totalLoaded = allPages.reduce((acc, page) => acc + page.messages.length, 0);
            return totalLoaded;
        },
        staleTime: Infinity, // History doesn't change unless we send a message
    });

    return {
        ...query,
        queryClient,
    };
};
