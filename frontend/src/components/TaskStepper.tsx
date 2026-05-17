import React from 'react';
import { Check, Loader2 } from 'lucide-react';

interface TaskStepperProps {
    topics: string[];
    currentTopic?: string;
    activeTool?: string | null;
}

export const TaskStepper: React.FC<TaskStepperProps> = ({ topics, currentTopic, activeTool }) => {
    if (topics.length === 0 && !currentTopic) return null;

    return (
        <div className="task-stepper">
            {topics.map((topic, idx) => (
                <div key={idx} className="step-item completed">
                    <div className="step-icon">
                        <Check size={14} />
                    </div>
                    <div className="step-content">
                        <span className="step-topic">{topic}</span>
                    </div>
                </div>
            ))}

            {currentTopic && (
                <div className="step-item active">
                    <div className="step-icon pulse">
                        <div className="pulse-dot"></div>
                    </div>
                    <div className="step-content">
                        <span className="step-topic">{currentTopic}</span>
                        {activeTool && (
                            <div className="step-tool">
                                <Loader2 size={12} className="animate-spin" />
                                <span>{activeTool}</span>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};
