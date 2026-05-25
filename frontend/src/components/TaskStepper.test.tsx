import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { TaskStepper } from './TaskStepper';
import React from 'react';

describe('TaskStepper', () => {
    it('renders null if no topics and no current topic', () => {
        const { container } = render(<TaskStepper topics={[]} />);
        expect(container.firstChild).toBeNull();
    });

    it('renders current topic as active and history as collapsed by default', () => {
        render(<TaskStepper topics={['Step 1']} currentTopic="Step 2" />);
        
        expect(screen.getByText('Step 2')).toBeDefined();
        // Step 1 should NOT be visible by default as it is in the collapsed history
        expect(screen.queryByText('Step 1')).toBeNull();
    });

    it('expands history when summary is clicked', () => {
        render(<TaskStepper topics={['Step 1']} currentTopic="Step 2" />);
        
        const summary = screen.getByText('Step 2').closest('.step-summary');
        expect(summary).not.toBeNull();
        
        fireEvent.click(summary!);
        
        // Now Step 1 should be visible
        expect(screen.getByText('Step 1')).toBeDefined();
    });

    it('shows "Task Completed" when no current topic is provided', () => {
        render(<TaskStepper topics={['Step 1', 'Step 2']} />);
        
        expect(screen.getByText('Task Completed (2 steps)')).toBeDefined();
    });

    it('shows active tool when provided', () => {
        render(<TaskStepper topics={[]} currentTopic="Running" activeTool="grep" />);
        
        expect(screen.getByText('grep')).toBeDefined();
    });
});
