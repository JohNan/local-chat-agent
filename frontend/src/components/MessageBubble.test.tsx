/// <reference types="@testing-library/jest-dom" />
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import { MessageBubble } from './MessageBubble';
import type { Message } from '../types';

expect.extend(matchers);

// Mock external dependencies
vi.mock('marked', () => ({
    marked: {
        parse: (text: string) => text,
        use: () => {},
    }
}));

vi.mock('highlight.js', () => ({
    default: {
        highlight: (code: string) => ({ value: code }),
        getLanguage: () => 'plaintext',
    }
}));

vi.mock('dompurify', () => ({
    default: {
        sanitize: (html: string) => html,
    }
}));

// Mock navigator.clipboard
const mockWriteText = vi.fn();
Object.assign(navigator, {
    clipboard: {
        writeText: mockWriteText,
    },
});

describe('MessageBubble', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        // Reset fetch mock before each test
        global.fetch = vi.fn();
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('renders user message correctly', () => {
        const message: Message = {
            id: '1',
            role: 'user',
            text: 'Hello World',
            parts: [{ text: 'Hello World' }]
        };

        render(<MessageBubble message={message} />);
        expect(screen.getByText('Hello World')).toBeInTheDocument();
    });

    it('renders AI message correctly', () => {
        const message: Message = {
            id: '2',
            role: 'model',
            text: 'I am AI',
            parts: [{ text: 'I am AI' }]
        };

        render(<MessageBubble message={message} />);
        expect(screen.getByText('I am AI')).toBeInTheDocument();
    });

    it('renders tool status when provided', () => {
        const message: Message = {
            id: '3',
            role: 'model',
            text: 'Thinking...',
            parts: [{ text: 'Thinking...' }]
        };

        render(<MessageBubble message={message} toolStatus="Processing..." />);
        expect(screen.getByText('Processing...')).toBeInTheDocument();
    });

    it('copies text to clipboard when copy button is clicked', async () => {
        const message: Message = {
            id: '4',
            role: 'model',
            text: 'Copy me',
            parts: [{ text: 'Copy me' }]
        };

        mockWriteText.mockResolvedValue(undefined);

        render(<MessageBubble message={message} />);

        const copyButton = screen.getByLabelText('Copy message');
        fireEvent.click(copyButton);

        expect(mockWriteText).toHaveBeenCalledWith('Copy me');

        // Wait for the state update (success icon) to avoid "not wrapped in act" warning
        await waitFor(() => {
            // Check icon is rendered (the button content changes)
            // The original code shows Check size={14} when copied is true
            // We can check if the button contains the Check icon or just wait for re-render
            expect(copyButton.querySelector('.lucide-check')).toBeInTheDocument();
        });
    });

    it('shows Start Jules Task button when prompt marker is present', () => {
        const message: Message = {
            id: '5',
            role: 'model',
            text: 'Here is the plan\n## Jules Prompt\nDo the task',
            parts: [{ text: 'Here is the plan\n## Jules Prompt\nDo the task' }]
        };

        render(<MessageBubble message={message} />);
        expect(screen.getByText('Start Jules Task')).toBeInTheDocument();
    });

    it('deploys task when Start Jules Task button is clicked', async () => {
        const message: Message = {
            id: '6',
            role: 'model',
            text: '## Jules Prompt\nTask content',
            parts: [{ text: '## Jules Prompt\nTask content' }]
        };

        const mockResponse = {
            success: true,
            result: { name: 'session-123' }
        };

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (global.fetch as any).mockResolvedValue({
            json: () => Promise.resolve(mockResponse),
        });

        render(<MessageBubble message={message} />);

        const deployButton = screen.getByText('Start Jules Task');
        fireEvent.click(deployButton);

        expect(screen.getByText('Sending...')).toBeInTheDocument();

        await waitFor(() => {
            expect(screen.getByText('Started! (session-123)')).toBeInTheDocument();
        });

        expect(global.fetch).toHaveBeenCalledWith('/api/deploy_to_jules', expect.objectContaining({
            method: 'POST',
            body: JSON.stringify({ prompt: 'Task content' })
        }));
    });

    it('handles deployment error', async () => {
        const message: Message = {
            id: '7',
            role: 'model',
            text: '## Jules Prompt\nTask content',
            parts: [{ text: '## Jules Prompt\nTask content' }]
        };

        const mockResponse = {
            success: false,
            error: 'Deployment failed'
        };

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (global.fetch as any).mockResolvedValue({
            json: () => Promise.resolve(mockResponse),
        });

        // Mock alert since it's used in component
        const alertMock = vi.spyOn(window, 'alert').mockImplementation(() => {});

        render(<MessageBubble message={message} />);

        const deployButton = screen.getByText('Start Jules Task');
        fireEvent.click(deployButton);

        await waitFor(() => {
            expect(screen.getByText('Error: Deployment failed')).toBeInTheDocument();
        });

        expect(alertMock).toHaveBeenCalledWith('Error deploying: Deployment failed');
    });
});
