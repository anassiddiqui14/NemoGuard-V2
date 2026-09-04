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

    // Optimistic local echo of the operator's own message. Without this,
    // the ONLY way the operator's just-sent message became visible was
    // waiting for the full backend round-trip (which includes a real LLM
    // call, often 10-90+ seconds) to finish and then re-fetching the whole
    // message list -- so the "Thinking" indicator appeared FIRST, and the
    // operator's own message only popped in afterward, alongside the
    // Commander's reply. This made the chat feel broken/unresponsive
    // (user-reported). optimisticMessages are rendered immediately, then
    // discarded the moment the next real refresh() brings back the
    // authoritative persisted list (which will already include this exact
    // message, now with a real message_id/created_at from the server).
    const [optimisticMessages, setOptimisticMessages] = useState<CommanderMessage[]>([]);

    const sendTurn = useCallback(
        async (
            endpoint: string,
            body: Record<string, unknown>,
            optimisticContent: string,
            optimisticIntent: CommanderMessage['intent'],
        ) => {
            if (!incidentId || !optimisticContent.trim()) return null;
            setOptimisticMessages((prev) => [
                ...prev,
                {
                    message_id: `optimistic-${Date.now()}`,
                    role: 'OPERATOR',
                    intent: optimisticIntent,
                    content: optimisticContent,
                    created_at: new Date().toISOString(),
                },
            ]);
            setSending(true);
            try {
                const res = await authFetch(`/api/v2/incidents/${incidentId}/commander/${endpoint}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });
                if (!res.ok) return null;
                const data = await res.json();
                setGuidanceRevision(data.guidance_revision ?? 0);
                await refresh();
                return data;
            } finally {
                setSending(false);
                setOptimisticMessages([]);
            }
        },
        [incidentId, refresh],
    );

    const ask = useCallback(
        (question: string) => sendTurn('ask', { question }, question, 'ASK'),
        [sendTurn],
    );

    const guide = useCallback(
        (text: string, guidanceType = 'INVESTIGATION_DIRECTION') =>
            sendTurn('guidance', { text, guidance_type: guidanceType }, text, 'GUIDE'),
        [sendTurn],
    );

    const addFact = useCallback(
        (text: string) => sendTurn('facts', { text }, text, 'ADD_FACT'),
        [sendTurn],
    );

    return { pulse, messages, optimisticMessages, guidanceRevision, loading, sending, ask, guide, addFact };
}
