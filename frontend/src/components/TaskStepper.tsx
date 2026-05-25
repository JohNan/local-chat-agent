import React, { useState } from 'react';
import { Check, Loader2, ChevronDown, ChevronUp } from 'lucide-react';

interface TaskStepperProps {
    topics: string[];
    currentTopic?: string;
    activeTool?: string | null;
}

export const TaskStepper: React.FC<TaskStepperProps> = ({ topics, currentTopic, activeTool }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    
    if (topics.length === 0 && !currentTopic) return null;

    const toggleExpand = () => {
        if (topics.length > 0) {
            setIsExpanded(!isExpanded);
        }
    };

    return (
        <div className="task-stepper" style={{ marginBottom: '10px' }}>
            {/* The Summary Bar: Shows current topic or completion status */}
            <div 
                className="step-summary" 
                onClick={toggleExpand}
                style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'space-between',
                    cursor: topics.length > 0 ? 'pointer' : 'default',
                }}
            >
                <div style={{ flex: 1 }}>
                    {currentTopic ? (
                        <div className="step-item active">
                            <div className="step-icon pulse">
                                <div className="pulse-dot"></div>
                            </div>
                            <div className="step-content">
                                <span className="step-topic">{currentTopic}</span>
                                {activeTool && (
                                    <div className="step-tool" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.85em', color: '#8b949e' }}>
                                        <Loader2 size={12} className="animate-spin" />
                                        <span>{activeTool}</span>
                                    </div>
                                )}
                            </div>
                        </div>
                    ) : (
                        <div className="step-item completed">
                            <div className="step-icon">
                                <Check size={14} />
                            </div>
                            <div className="step-content">
                                <span className="step-topic">Task Completed ({topics.length} steps)</span>
                            </div>
                        </div>
                    )}
                </div>

                {topics.length > 0 && (
                    <div className="step-toggle" style={{ color: '#8b949e', marginLeft: '10px' }}>
                        {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </div>
                )}
            </div>

            {/* Collapsible History: Shows completed topics */}
            {isExpanded && topics.length > 0 && (
                <div className="step-history" style={{ 
                    marginTop: '10px', 
                    paddingTop: '10px',
                    borderTop: '1px solid rgba(255, 255, 255, 0.1)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '10px'
                }}>
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
                </div>
            )}
        </div>
    );
};
