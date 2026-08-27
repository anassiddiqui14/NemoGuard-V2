import { useState, useEffect, useCallback } from 'react';
import { authFetch } from '../contexts/AuthGateContext';

export interface CommanderStatusUpdate {
    update_id: string;
    update_type: string;
    created_at: string;
    headline: string;
    summary?: string;
    severity?: string | null;
    notify_external: number;
}

export interface CommanderMessage {
    message_id: string;
    role: 'OPERATOR' | 'COMMANDER';
    intent?: 'ASK' | 'GUIDE' | 'ADD_FACT' | null;
    content: string;
    created_by?: string;
    created_at: string;
    guidance_revision?: number | null;
}

/**
 * Polls Commander Pulse (status updates) and the Commander Live
 * conversation for a given incident. Reuses the same 2s polling cadence
 * useIncidentData already uses elsewhere in this dashboard, rather than
 * opening a second live connection -- SSE carries the raw audit stream
 * already rendered by LiveOperationsConsole; Commander Pulse is a
 * deliberately lower-frequency, higher-level view on top of it.
 */
export function useCommander(incidentId: string | null) {
    const [pulse, setPulse] = useState<CommanderStatusUpdate[]>([]);
    const [messages, setMessages] = useState<CommanderMessage[]>([]);
    const [guidanceRevision, setGuidanceRevision] = useState(0);
    const [loading, setLoading] = useState(false);
    const [sending, setSending] = useState(false);

    const refresh = useCallback(async () => {
        if (!incidentId) return;
        try {
            const [pulseRes, msgRes] = await Promise.all([
                authFetch(`/api/v2/incidents/${incidentId}/commander/status`),
                authFetch(`/api/v2/incidents/${incidentId}/commander/messages`),
            ]);
            if (pulseRes.ok) {
                const pulseData = await pulseRes.json();
                if (Array.isArray(pulseData)) setPulse(pulseData);
            }
            if (msgRes.ok) {
                const msgData = await msgRes.json();
                if (Array.isArray(msgData)) setMessages(msgData);
            }
        } catch (e) {
            console.error(e);
        }
    }, [incidentId]);

    useEffect(() => {
        setPulse([]);
        setMessages([]);
        setGuidanceRevision(0);
        if (!incidentId) {
            setLoading(false);
            return;
        }
        setLoading(true);
        void refresh().finally(() => setLoading(false));
        const interval = setInterval(refresh, 4000);
        return () => clearInterval(interval);
    }, [incidentId, refresh]);

    const ask = useCallback(
        async (question: string) => {
            if (!incidentId || !question.trim()) return null;
            setSending(true);
            try {
                const res = await authFetch(`/api/v2/incidents/${incidentId}/commander/ask`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ question }),
                });
                if (!res.ok) return null;
                const data = await res.json();
                setGuidanceRevision(data.guidance_revision ?? 0);
                await refresh();
                return data;
            } finally {
                setSending(false);
            }
        },
        [incidentId, refresh],
    );

    const guide = useCallback(
        async (text: string, guidanceType = 'INVESTIGATION_DIRECTION') => {
            if (!incidentId || !text.trim()) return null;
            setSending(true);
            try {
                const res = await authFetch(`/api/v2/incidents/${incidentId}/commander/guidance`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text, guidance_type: guidanceType }),
                });
                if (!res.ok) return null;
                const data = await res.json();
                setGuidanceRevision(data.guidance_revision ?? 0);
                await refresh();
                return data;
            } finally {
                setSending(false);
            }
        },
        [incidentId, refresh],
    );

    const addFact = useCallback(
        async (text: string) => {
            if (!incidentId || !text.trim()) return null;
            setSending(true);
            try {
                const res = await authFetch(`/api/v2/incidents/${incidentId}/commander/facts`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text }),
                });
                if (!res.ok) return null;
                const data = await res.json();
                setGuidanceRevision(data.guidance_revision ?? 0);
                await refresh();
                return data;
            } finally {
                setSending(false);
            }
        },
        [incidentId, refresh],
    );

    return { pulse, messages, guidanceRevision, loading, sending, ask, guide, addFact };
}
