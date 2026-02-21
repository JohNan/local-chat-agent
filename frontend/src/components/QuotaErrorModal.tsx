import React, { useEffect, useState } from 'react';

interface QuotaErrorModalProps {
    currentModel: string;
    error: string;
    onRetry: (newModel: string) => void;
    onCancel: () => void;
}

export const QuotaErrorModal: React.FC<QuotaErrorModalProps> = ({ currentModel, error, onRetry, onCancel }) => {
    const [models, setModels] = useState<string[]>([]);
    const [selectedModel, setSelectedModel] = useState<string>("");

    useEffect(() => {
        fetch('/api/models')
            .then(res => res.json())
            .then((data: { models: string[] }) => {
                if (data.models && Array.isArray(data.models)) {
                    setModels(data.models);
                    // Default to the first model that isn't the current one
                    const alternative = data.models.find(m => m !== currentModel);
                    if (alternative) {
                        setSelectedModel(alternative);
                    } else if (data.models.length > 0) {
                        setSelectedModel(data.models[0]);
                    }
                }
            })
            .catch(err => console.error("Failed to fetch models:", err));
    }, [currentModel]);

    return (
        <div className="settings-overlay">
            <div className="settings-modal">
                <div className="settings-header">
                    <h3>Quota Exceeded</h3>
                </div>
                <div className="settings-content">
                    <div className="error-message" style={{ padding: '10px', borderRadius: '4px', backgroundColor: 'rgba(255, 107, 107, 0.1)' }}>
                        {error}
                    </div>
                    <div className="setting-item">
                        <label>Select a different model to retry:</label>
                        <select
                            className="model-select"
                            value={selectedModel}
                            onChange={(e) => setSelectedModel(e.target.value)}
                        >
                            {models.map(m => (
                                <option key={m} value={m}>{m}</option>
                            ))}
                        </select>
                    </div>
                    <div style={{ display: 'flex', gap: '10px', marginTop: '10px', justifyContent: 'flex-end' }}>
                         <button
                            className="primary-btn"
                            onClick={() => onRetry(selectedModel)}
                            disabled={!selectedModel}
                        >
                            Retry
                        </button>
                        <button
                            className="primary-btn"
                            style={{ backgroundColor: '#454545' }}
                            onClick={onCancel}
                        >
                            Cancel
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};
