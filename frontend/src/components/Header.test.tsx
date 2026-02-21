/// <reference types="@testing-library/jest-dom" />
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import { Header } from './Header';

expect.extend(matchers);

// Mock fetch
const fetchMock = vi.fn();
global.fetch = fetchMock;

// Mock window interactions
const alertMock = vi.fn();
const confirmMock = vi.fn();
const reloadMock = vi.fn();

// Ideally, we should mock window.location but JSDOM makes it tricky.
// We'll define a simpler mock for window.location.reload if possible, or just spy on it.
Object.defineProperty(window, 'location', {
    value: { reload: reloadMock },
    writable: true,
});
window.alert = alertMock;
window.confirm = confirmMock;

describe('Header Component', () => {
    const mockSetModel = vi.fn();
    const mockSetWebSearchEnabled = vi.fn();
    const mockOnToggleTasks = vi.fn();

    const defaultProps = {
        model: 'gemini-2.0-flash-exp',
        setModel: mockSetModel,
        webSearchEnabled: false,
        setWebSearchEnabled: mockSetWebSearchEnabled,
        onToggleTasks: mockOnToggleTasks,
    };

    beforeEach(() => {
        vi.clearAllMocks();
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({}),
        });
    });

    it('renders the header title and buttons', async () => {
        render(<Header {...defaultProps} />);

        expect(screen.getByText('Gemini Agent')).toBeInTheDocument();
        // Check for main buttons by title
        expect(screen.getByTitle('Tasks')).toBeInTheDocument();
        expect(screen.getByTitle('Reset Context')).toBeInTheDocument();
        expect(screen.getByTitle('Settings')).toBeInTheDocument();

        // Wait for effects to settle
        await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    });

    it('fetches status and models on mount', async () => {
        fetchMock.mockImplementation((url) => {
            if (url === '/api/status') {
                return Promise.resolve({
                    ok: true,
                    json: async () => ({ active_persona: 'UI', project: 'TestProject', branch: 'test-branch' }),
                });
            }
            if (url === '/api/models') {
                return Promise.resolve({
                    ok: true,
                    json: async () => ({ models: ['model-1', 'model-2'] }),
                });
            }
            return Promise.resolve({ ok: true, json: async () => ({}) });
        });

        render(<Header {...defaultProps} />);

        await waitFor(() => {
            expect(fetchMock).toHaveBeenCalledWith('/api/status');
        });

        // Models are fetched when settings are opened, but check if called initially?
        // Actually, in the component: useEffect(() => { fetchModels() }, [showSettings]);
        // showSettings starts false. So fetchModels runs on mount because [false] changes? No, on mount [showSettings] runs once.
        await waitFor(() => {
            expect(fetchMock).toHaveBeenCalledWith('/api/models');
        });
    });

    it('toggles tasks drawer', async () => {
        render(<Header {...defaultProps} />);
        await waitFor(() => expect(fetchMock).toHaveBeenCalled());

        const tasksButton = screen.getByTitle('Tasks');
        fireEvent.click(tasksButton);
        expect(mockOnToggleTasks).toHaveBeenCalledTimes(1);
    });

    it('opens settings modal and displays info', async () => {
        fetchMock.mockImplementation((url) => {
            if (url === '/api/status') {
                return Promise.resolve({
                    ok: true,
                    json: async () => ({ active_persona: 'UI', project: 'TestRepo', branch: 'dev' }),
                });
            }
            if (url === '/api/models') {
                return Promise.resolve({
                    ok: true,
                    json: async () => ({ models: ['model-A', 'model-B'] }),
                });
            }
            return Promise.resolve({ ok: true, json: async () => ({}) });
        });

        render(<Header {...defaultProps} />);

        // Open settings
        const settingsButton = screen.getByTitle('Settings');
        fireEvent.click(settingsButton);

        expect(screen.getByText('Settings')).toBeInTheDocument();

        // Check repo status display
        await waitFor(() => {
            expect(screen.getByText(/TestRepo \(dev\)/)).toBeInTheDocument();
        });

        // Check model selector
        await waitFor(() => {
            expect(screen.getByText('model-A')).toBeInTheDocument();
            expect(screen.getByText('model-B')).toBeInTheDocument();
        });
    });

    it('handles model change', async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({ models: ['model-X', 'model-Y'] }),
        });

        render(<Header {...defaultProps} />);

        // Open settings to access model select
        fireEvent.click(screen.getByTitle('Settings'));

        await waitFor(() => {
             expect(screen.getByText('model-X')).toBeInTheDocument();
        });

        const select = screen.getByRole('combobox');
        fireEvent.change(select, { target: { value: 'model-Y' } });

        expect(mockSetModel).toHaveBeenCalledWith('model-Y');
    });

    it('handles web search toggle', async () => {
        render(<Header {...defaultProps} />);
        await waitFor(() => expect(fetchMock).toHaveBeenCalled());

        fireEvent.click(screen.getByTitle('Settings'));

        const checkbox = screen.getByLabelText('Enable Web Search');
        fireEvent.click(checkbox);

        // initial was false, so clicking should call with true
        expect(mockSetWebSearchEnabled).toHaveBeenCalledWith(true);
    });

    it('handles Git Pull action', async () => {
        fetchMock.mockImplementation((url) => {
            if (url === '/api/git_pull') {
                return Promise.resolve({
                    ok: true,
                    json: async () => ({ output: 'Pull successful' }),
                });
            }
            return Promise.resolve({ ok: true, json: async () => ({}) });
        });

        render(<Header {...defaultProps} />);
        fireEvent.click(screen.getByTitle('Settings'));

        const pullButton = screen.getByTitle('Git Pull');
        fireEvent.click(pullButton);

        await waitFor(() => {
            expect(fetchMock).toHaveBeenCalledWith('/api/git_pull', expect.objectContaining({ method: 'POST' }));
            expect(alertMock).toHaveBeenCalledWith('Pull successful');
        });
    });

    it('handles Clear History action', async () => {
        confirmMock.mockReturnValue(true);
        fetchMock.mockImplementation((url) => {
            if (url === '/api/reset') {
                return Promise.resolve({
                    ok: true,
                    json: async () => ({ status: 'success' }),
                });
            }
            return Promise.resolve({ ok: true, json: async () => ({}) });
        });

        render(<Header {...defaultProps} />);
        fireEvent.click(screen.getByTitle('Settings'));

        const clearButton = screen.getByTitle('Clear History');
        fireEvent.click(clearButton);

        expect(confirmMock).toHaveBeenCalled();

        await waitFor(() => {
            expect(fetchMock).toHaveBeenCalledWith('/api/reset', expect.objectContaining({ method: 'POST' }));
            expect(reloadMock).toHaveBeenCalled();
        });
    });

    it('handles Reset Context action', async () => {
        confirmMock.mockReturnValue(true);
        fetchMock.mockImplementation((url) => {
            if (url === '/api/context_reset') {
                return Promise.resolve({
                    ok: true,
                    json: async () => ({}),
                });
            }
            return Promise.resolve({ ok: true, json: async () => ({}) });
        });

        render(<Header {...defaultProps} />);

        // Based on current implementation, this is in the main header controls
        const resetButton = screen.getByTitle('Reset Context');
        fireEvent.click(resetButton);

        expect(confirmMock).toHaveBeenCalled();

        await waitFor(() => {
            expect(fetchMock).toHaveBeenCalledWith('/api/context_reset', expect.objectContaining({ method: 'POST' }));
            expect(reloadMock).toHaveBeenCalled();
        });
    });
});
