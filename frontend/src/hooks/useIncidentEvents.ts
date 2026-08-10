import { useEffect, useRef, useState } from 'react';

export interface AgentEvent {
    id: string;
    timestamp: string;
    source: string;
    event_type: string;
    message: string;
}

/**
 * Shared SSE subscription for a single incident's audit-event stream.
 * Both the Agent Constellation and the Live Operations Console consume
 * this same hook so the "who is running right now" visualization and the
 * raw event log are always perfectly in sync (previously the Constellation
 * only looked at `incident.status`, so it couldn't distinguish which of the
 * 4 sub-agents was actually active at a given moment).
 */
export function useIncidentEvents(incidentId: string | null) {
    const [events, setEvents] = useState<AgentEvent[]>([]);
    const [status, setStatus] = useState<'connecting' | 'connected' | 'disconnected'>('disconnected');
    const esRef = useRef<EventSource | null>(null);

    useEffect(() => {
        if (esRef.current) {
            esRef.current.close();
            esRef.current = null;
        }
        setEvents([]);

        if (!incidentId) {
            setStatus('disconnected');
            return;
        }

        setStatus('connecting');
        const es = new EventSource(`/api/v2/incidents/${incidentId}/events/stream`);
        esRef.current = es;

        es.onopen = () => setStatus('connected');
        es.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data) as AgentEvent;
                setEvents((prev) => {
                    if (prev.some((evt) => evt.id === data.id)) return prev;
                    return [...prev, data].sort(
                        (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
                    );
                });
            } catch {
                // ignore malformed frames
            }
        };
        es.onerror = () => setStatus('disconnected');

        return () => {
            es.close();
        };
    }, [incidentId]);

    return { events, status };
}
