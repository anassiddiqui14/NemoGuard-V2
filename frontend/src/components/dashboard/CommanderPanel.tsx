import { useRef, useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Radio, ShieldCheck, ArrowUp, MessageSquare, Compass, BadgeCheck, Sparkles } from 'lucide-react';
import { useCommander } from '../../hooks/useCommander';
import { EmptyState } from './shared';

const SEVERITY_DOT: Record<string, string> = {
    critical: 'bg-critical',
    warning: 'bg-warning',
};

function PulseItem({ headline, summary, severity, created_at }: { headline: string; summary?: string; severity?: string | null; created_at: string }) {
    const dotClass = (severity && SEVERITY_DOT[severity]) || 'bg-healthy';
    const time = new Date(created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    return (
        <div className="flex items-start gap-2.5 py-2 border-b border-white/[0.04] last:border-b-0">
            <span className={`w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 ${dotClass}`} />
            <div className="min-w-0 flex-1">
                <div className="text-[12px] font-medium text-text-primary">{headline}</div>
                {summary && <div className="text-[11px] text-text-muted mt-0.5 leading-relaxed">{summary}</div>}
            </div>
            <span className="text-[9.5px] text-text-muted font-mono flex-shrink-0 mt-0.5">{time}</span>
        </div>
    );
}

function ConversationBubble({ role, intent, content, created_at }: { role: string; intent?: string | null; content: string; created_at: string }) {
    const isOperator = role === 'OPERATOR';
    const time = new Date(created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    return (
        <div className={`flex ${isOperator ? 'justify-end' : 'justify-start'} mb-2.5`}>
            <div className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 ${isOperator ? 'bg-primary/15 ring-1 ring-primary/25' : 'bg-white/[0.03] ring-1 ring-white/[0.06]'}`}>
                {intent && (
                    <div className="flex items-center gap-1 mb-1">
                        {intent === 'GUIDE' && <Compass className="w-2.5 h-2.5 text-warning" />}
                        {intent === 'ADD_FACT' && <BadgeCheck className="w-2.5 h-2.5 text-healthy" />}
                        <span className="text-[9px] font-bold uppercase tracking-wide text-text-muted">{intent.replace('_', ' ')}</span>
                    </div>
                )}
                <div className="text-[12.5px] text-text-secondary leading-relaxed whitespace-pre-wrap">{content}</div>
                <div className="text-[9px] text-text-muted mt-1 text-right">{time}</div>
            </div>
        </div>
    );
}

const THINKING_LABELS: Record<string, string> = {
    ASK: 'Thinking',
    GUIDE: 'Weighing guidance',
    ADD_FACT: 'Reconciling fact',
};

/**
 * "Commander is thinking" indicator. ASK/GUIDE/ADD_FACT can take anywhere
 * from a few seconds (guidance reactions) to 60-90s (ASK, which may call
 * real read-only tools like query_logs before answering -- see
 * CommanderLiveAgent). Without this, the input area going quiet for that
 * long looked indistinguishable from a hung/broken request.
 */
function ThinkingBubble({ mode }: { mode: 'ASK' | 'GUIDE' | 'ADD_FACT' }) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex justify-start mb-2.5"
        >
            <div className="max-w-[85%] rounded-2xl px-3.5 py-2.5 bg-white/[0.03] ring-1 ring-white/[0.06] flex items-center gap-2">
                <motion.span
                    animate={{ rotate: 360 }}
                    transition={{ duration: 2.2, repeat: Infinity, ease: 'linear' }}
                    className="flex-shrink-0"
                >
                    <Sparkles className="w-3 h-3 text-agent-active" />
                </motion.span>
                <span className="text-[11.5px] text-text-muted font-medium">{THINKING_LABELS[mode]}</span>
                <span className="flex items-center gap-0.5">
                    {[0, 1, 2].map((i) => (
                        <motion.span
                            key={i}
                            className="w-1 h-1 rounded-full bg-text-muted"
                            animate={{ opacity: [0.25, 1, 0.25], y: [0, -2, 0] }}
                            transition={{ duration: 1.1, repeat: Infinity, delay: i * 0.15, ease: 'easeInOut' }}
                        />
                    ))}
                </span>
            </div>
        </motion.div>
    );
}

export function CommanderPanel({ incidentId }: { incidentId: string | null }) {
    const { pulse, messages, optimisticMessages, loading, sending, ask, guide, addFact } = useCommander(incidentId);
    const [mode, setMode] = useState<'ASK' | 'GUIDE' | 'ADD_FACT'>('ASK');
    const [text, setText] = useState('');
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
    }, [messages.length, sending]);

    // BUG FIX (user-reported live, confirmed via screenshot showing two
    // identical "ASK what's the RCA?" bubbles at the SAME timestamp):
    // handleSubmit's guard checked the React `sending` STATE, which only
    // updates on the NEXT render -- it does nothing to stop a second
    // synchronous call to handleSubmit that happens before that re-render
    // commits (e.g. the Enter keydown handler and a near-simultaneous
    // click on the send button both firing handleSubmit in the same tick,
    // or a fast double-press). Both invocations read the same stale
    // `sending === false` and both went through, sending two identical
    // requests. A plain useRef lock is checked and flipped SYNCHRONOUSLY
    // (no render involved), so the second call is blocked immediately,
    // regardless of React's render/state-update timing.
    const submitLockRef = useRef(false);

    const handleSubmit = async () => {
        if (!text.trim() || sending || submitLockRef.current) return;
        submitLockRef.current = true;
        const value = text;
        setText('');
        try {
            if (mode === 'ASK') await ask(value);
            else if (mode === 'GUIDE') await guide(value);
            else await addFact(value);
        } finally {
            submitLockRef.current = false;
        }
    };

    if (!incidentId) {
        return (
            <div className="console-surface rounded-2xl min-h-[300px] flex items-center justify-center">
                <EmptyState icon={<MessageSquare className="w-5 h-5" />} title="No incident selected" subtitle="Select an incident to open its Commander session." />
            </div>
        );
    }

    return (
        <div className="grid grid-cols-1 lg:grid-cols-[0.9fr_1.1fr] gap-4">
            {/* Commander Pulse */}
            <div className="console-surface rounded-2xl overflow-hidden flex flex-col h-[480px]">
                <div className="px-4 py-3.5 flex items-center justify-between border-b border-white/[0.05]">
                    <div className="flex items-center gap-2">
                        <Radio className="w-3.5 h-3.5 text-primary" />
                        <div className="font-semibold text-[13px] text-text-primary">Commander Pulse</div>
                    </div>
                    <span className="text-[9.5px] font-semibold uppercase tracking-wide text-text-muted">{pulse.length} updates</span>
                </div>
                <div className="flex-1 overflow-y-auto px-4 py-2">
                    {loading ? (
                        <div className="text-[11px] text-text-muted py-4 text-center">Loading status...</div>
                    ) : pulse.length === 0 ? (
                        <EmptyState icon={<Radio className="w-5 h-5" />} title="No status updates yet" subtitle="Commander Pulse will populate as the investigation progresses." />
                    ) : (
                        <AnimatePresence initial={false}>
                            {pulse.map((u, idx) => (
                                <motion.div
                                    key={u.update_id}
                                    initial={{ opacity: 0, x: -8 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: idx === 0 ? 0 : 0.02 * idx, type: 'spring', stiffness: 260, damping: 22 }}
                                >
                                    <PulseItem headline={u.headline} summary={u.summary} severity={u.severity} created_at={u.created_at} />
                                </motion.div>
                            ))}
                        </AnimatePresence>
                    )}
                </div>
            </div>

            {/* Commander Live conversation */}
            <div className="console-surface rounded-2xl overflow-hidden flex flex-col h-[480px]">
                <div className="px-4 py-3.5 flex items-center justify-between border-b border-white/[0.05]">
                    <div className="flex items-center gap-2">
                        <motion.span
                            animate={sending ? { scale: [1, 1.15, 1], opacity: [1, 0.7, 1] } : { scale: 1, opacity: 1 }}
                            transition={sending ? { duration: 1.4, repeat: Infinity, ease: 'easeInOut' } : { duration: 0.2 }}
                        >
                            <ShieldCheck className="w-3.5 h-3.5 text-agent-active" />
                        </motion.span>
                        <div className="font-semibold text-[13px] text-text-primary">Commander</div>
                    </div>
                    <AnimatePresence>
                        {sending && (
                            <motion.span
                                initial={{ opacity: 0, x: 6 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0 }}
                                className="text-[9.5px] font-bold uppercase tracking-wide text-agent-active flex items-center gap-1.5"
                            >
                                <span className="w-1.5 h-1.5 rounded-full bg-agent-active animate-pulse" /> live
                            </motion.span>
                        )}
                    </AnimatePresence>
                </div>
                <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3">
                    {messages.length === 0 && optimisticMessages.length === 0 && !sending ? (
                        <EmptyState icon={<MessageSquare className="w-5 h-5" />} title="Ask, guide, or add a confirmed fact" subtitle="Commander will answer questions, accept investigation guidance, and record confirmed facts -- but never accepts approval or execution through chat." />
                    ) : (
                        <AnimatePresence initial={false}>
                            {messages.map((m) => (
                                <motion.div
                                    key={m.message_id}
                                    initial={{ opacity: 0, y: 10, scale: 0.98 }}
                                    animate={{ opacity: 1, y: 0, scale: 1 }}
                                    transition={{ type: 'spring', stiffness: 300, damping: 24 }}
                                >
                                    <ConversationBubble role={m.role} intent={m.intent} content={m.content} created_at={m.created_at} />
                                </motion.div>
                            ))}
                            {/* Optimistic echo of the operator's just-sent message --
                                appears INSTANTLY (before the backend round-trip
                                completes), so the operator's own text is never
                                hidden behind the Thinking indicator. Discarded the
                                moment refresh() brings back the real persisted
                                version of this same message.

                                Defense-in-depth against the "I see my message
                                twice" bug: even though useCommander now skips its
                                background poll while a send is in flight, filter
                                out any optimistic entry whose exact content
                                already appears in the real, persisted `messages`
                                list -- covers the brief window between the real
                                message landing in `messages` and sendTurn's own
                                cleanup clearing optimisticMessages. */}
                            {optimisticMessages
                                .filter((om) => !messages.some((m) => m.role === om.role && m.content === om.content))
                                .map((m) => (
                                    <motion.div
                                        key={m.message_id}
                                        initial={{ opacity: 0, y: 10, scale: 0.98 }}
                                        animate={{ opacity: 1, y: 0, scale: 1 }}
                                        transition={{ type: 'spring', stiffness: 300, damping: 24 }}
                                    >
                                        <ConversationBubble role={m.role} intent={m.intent} content={m.content} created_at={m.created_at} />
                                    </motion.div>
                                ))}
                            {sending && <ThinkingBubble key="thinking" mode={mode} />}
                        </AnimatePresence>
                    )}
                </div>
                <div className="border-t border-white/[0.06] p-3">
                    <div className="flex gap-1.5 mb-2">
                        {(['ASK', 'GUIDE', 'ADD_FACT'] as const).map((m) => (
                            <button
                                key={m}
                                onClick={() => setMode(m)}
                                disabled={sending}
                                className={`focus-ring press-scale text-[10.5px] font-semibold px-2.5 py-1.5 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${mode === m
                                    ? 'bg-primary/20 text-primary ring-1 ring-primary/35'
                                    : 'bg-white/[0.03] text-text-muted ring-1 ring-white/[0.06] hover:text-text-secondary'
                                    }`}
                            >
                                {m.replace('_', ' ')}
                            </button>
                        ))}
                    </div>
                    <div className="flex items-end gap-2">
                        <textarea
                            value={text}
                            onChange={(e) => setText(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' && !e.shiftKey) {
                                    e.preventDefault();
                                    handleSubmit();
                                }
                            }}
                            disabled={sending}
                            placeholder={
                                sending
                                    ? 'Commander is responding...'
                                    : mode === 'ASK'
                                        ? 'Ask Commander about this incident...'
                                        : mode === 'GUIDE'
                                            ? 'Provide investigation guidance...'
                                            : 'State a confirmed fact...'
                            }
                            rows={2}
                            className="flex-1 resize-none rounded-xl px-3 py-2 text-[12.5px] bg-white/[0.03] ring-1 ring-white/[0.06] text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-primary/50 transition-all disabled:opacity-60"
                        />
                        <button
                            onClick={handleSubmit}
                            disabled={!text.trim() || sending}
                            className="focus-ring press-scale flex-shrink-0 w-9 h-9 rounded-xl bg-primary text-white flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                            <ArrowUp className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
