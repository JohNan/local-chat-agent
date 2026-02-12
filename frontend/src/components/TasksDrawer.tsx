import React, { useEffect, useState, useRef } from 'react';
import { X, RefreshCw } from 'lucide-react';

interface Task {
    session_name: string;
    status: string;
    prompt_preview: string;
    created_at: string;
}

interface TasksDrawerProps {
    isOpen: boolean;
    onClose: () => void;
}

export const TasksDrawer: React.FC<TasksDrawerProps> = ({ isOpen, onClose }) => {
    const [tasks, setTasks] = useState<Task[]>([]);
    const [loading, setLoading] = useState(false);
    const [syncing, setSyncing] = useState<Record<string, boolean>>({});
    const pollIntervalRef = useRef<number | null>(null);

    const loadTasks = async () => {
        setLoading(true);
        try {
            const res = await fetch('/api/tasks');
            if (res.ok) {
                const data = await res.json();
                setTasks(data);
            }
        } catch (e) {
            console.error("Failed to load tasks:", e);
        } finally {
            setLoading(false);
        }
    };

    const syncTask = async (sessionName: string) => {
        setSyncing(prev => ({ ...prev, [sessionName]: true }));
        try {
            const res = await fetch(`/api/tasks/${sessionName}/sync`, { method: 'POST' });
            if (res.ok) {
                await loadTasks();
            }
        } catch (e) {
            console.error("Sync error:", e);
        } finally {
            setSyncing(prev => ({ ...prev, [sessionName]: false }));
        }
    };

    useEffect(() => {
        let isMounted = true;

        const pollTasks = async () => {
             if (!isMounted) return;
             try {
                 // 1. Fetch current tasks
                 const res = await fetch('/api/tasks');
                 if (!res.ok) return;
                 const latestTasks: Task[] = await res.json();

                 // 2. Check for running
                 const running = latestTasks.filter(t =>
                     ['running', 'pending'].includes((t.status || '').toLowerCase())
                 );

                 if (running.length > 0) {
                     // 3. Sync running
                     await Promise.all(running.map(t =>
                         fetch(`/api/tasks/${t.session_name}/sync`, { method: 'POST' })
                     ));
                     // 4. Final fetch to get updated status
                     const finalRes = await fetch('/api/tasks');
                     if (finalRes.ok) {
                         const finalTasks = await finalRes.json();
                         if (isMounted) setTasks(finalTasks);
                     }
                 } else {
                     if (isMounted) setTasks(latestTasks);
                 }
             } catch (e) {
                 console.error(e);
             }
        };

        if (isOpen) {
            loadTasks();
            pollIntervalRef.current = window.setInterval(pollTasks, 5000);
        } else {
            if (pollIntervalRef.current) {
                clearInterval(pollIntervalRef.current);
                pollIntervalRef.current = null;
            }
        }

        return () => {
            isMounted = false;
            if (pollIntervalRef.current) {
                clearInterval(pollIntervalRef.current);
            }
        };
    }, [isOpen]);

    return (
        <div className={`tasks-drawer ${isOpen ? 'open' : ''}`}>
            <div className="drawer-header">
                <span>Jules Tasks</span>
                <button className="close-btn" onClick={onClose} aria-label="Close drawer">
                    <X size={20} />
                </button>
            </div>
            <div className="tasks-list">
                {tasks.length === 0 ? (
                    <div style={{ textAlign: 'center', color: '#888', marginTop: '20px' }}>
                        {loading ? 'Loading...' : 'No tasks found.'}
                    </div>
                ) : (
                    tasks.map(task => {
                        const statusClass = `status-${(task.status || 'pending').toLowerCase()}`;
                        const dateStr = new Date(task.created_at).toLocaleString();
                        const isSyncing = syncing[task.session_name];

                        return (
                            <div className="task-card" key={task.session_name}>
                                <div className="task-header">
                                    <span className={`task-status ${statusClass}`}>{task.status}</span>
                                    <span style={{ fontFamily: 'monospace', fontSize: '0.8em', color: '#666' }}>
                                        {task.session_name.split('/').pop()}
                                    </span>
                                </div>
                                <div className="task-preview" title={task.prompt_preview}>
                                    {task.prompt_preview}
                                </div>
                                <div className="task-meta">
                                    <span>{dateStr}</span>
                                    <button
                                        className="refresh-btn"
                                        onClick={() => syncTask(task.session_name)}
                                        disabled={isSyncing}
                                        title="Sync Task"
                                    >
                                        <RefreshCw size={14} className={isSyncing ? 'animate-spin' : ''} />
                                        Sync
                                    </button>
                                </div>
                            </div>
                        );
                    })
                )}
            </div>
        </div>
    );
};
