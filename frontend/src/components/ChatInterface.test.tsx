/// <reference types="@testing-library/jest-dom" />
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import { ChatInterface } from './ChatInterface';
import type { Message } from '../types';

expect.extend(matchers);

// Mock marked to avoid complex rendering and ensure it works in jsdom
vi.mock('marked', () => ({
    marked: {
        parse: (text: string) => text,
        use: () => {},
    }
}));

// Mock highlight.js
vi.mock('highlight.js', () => ({
    default: {
        highlight: (code: string) => ({ value: code }),
        getLanguage: () => 'plaintext',
    }
}));

// Mock DOMPurify
vi.mock('dompurify', () => ({
    default: {
        sanitize: (html: string) => html,
    }
}));

describe('MessageBubble Performance', () => {
    it('renders and updates messages', () => {
        const messages: Message[] = [
            { id: '1', role: 'user', text: 'Hello', parts: [{ text: 'Hello' }] },
            { id: '2', role: 'model', text: 'Hi there', parts: [{ text: 'Hi there' }] },
        ];

        const { rerender } = render(
            <ChatInterface
                messages={messages}
                onLoadHistory={() => {}}
                toolStatus={null}
                isLoadingHistory={false}
            />
        );

        // Check initial render
        expect(screen.getByText('Hello')).toBeInTheDocument();
        expect(screen.getByText('Hi there')).toBeInTheDocument();

        // Update the last message (simulate streaming)
        // Important: preserve reference for the first message to test memoization
        const updatedMessages: Message[] = [
            messages[0], // Same reference
            { ...messages[1], text: 'Hi there!', parts: [{ text: 'Hi there!' }] } // New reference
        ];

        console.log('--- UPDATING MESSAGES ---');

        rerender(
            <ChatInterface
                messages={updatedMessages}
                onLoadHistory={() => {}}
                toolStatus={null}
                isLoadingHistory={false}
            />
        );

        expect(screen.getByText('Hi there!')).toBeInTheDocument();
    });
});
