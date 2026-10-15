import { useRef, useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ShieldCheck, ArrowUp, MessageSquare, Compass, BadgeCheck, X, Bot, Sparkles } from 'lucide-react';
import { useCommander } from '../../hooks/useCommander';
import { EmptyState } from './shared';
import { BrandMark } from '../../design-system/components/BrandMark';
import { IconButton } from '../../design-system/components/IconButton';

const SEVERITY_DOT: Record<string, string> = { critical: 'bg-critical', warning: 'bg-warning' };

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

const THINKING_LABELS: Record<string, string> = { ASK: 'Thinking', GUIDE: 'Weighing guidance', ADD_FACT: 'Reconciling fact' };

/*
 * UI MODERNIZATION (spec Section 75 -- signature brand animation):
 * previously a generic spinning Lucide Sparkles icon. Swapped for the
 * consolidated BrandMark primitive in its "active" state, so the
 * actual NemoGuard mark -- not a borrowed icon-library glyph -- is
 * what an operator sees whenever Commander is genuinely processing a
 * request.
 */
function ThinkingBubble({ mode }: { mode: 'ASK' | 'GUIDE' | 'ADD_FACT' }) {
    return (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="flex justify-start mb-2.5">
            <div className="max-w-[85%] rounded-2xl px-3.5 py-2.5 bg-white/[0.03] ring-1 ring-white/[0.06] flex items-center gap-2">
                <BrandMark state="active" size="sm" />
                <span className="text-[11.5px] text-text-muted font-medium">{THINKING_LABELS[mode]}</span>
                <span className="flex items-center gap-0.5">
                    {[0, 1, 2].map((i) => (
                        <motion.span key={i} className="w-1 h-1 rounded-full bg-text-muted" animate={{ opacity: [0.25, 1, 0.25], y: [0, -2, 0] }} transition={{ duration: 1.1, repeat: Infinity, delay: i * 0.15, ease: 'easeInOut' }} />
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
    const [open, setOpen] = useState(false);
    const [tab, setTab] = useState<'chat' | 'pulse'>('chat');

    // BUG FIX (user-reported): "when i close and re open chat, it should
    // start from where i left not from starting". Root cause: the chat's
    // scrollable message container lives inside AnimatePresence's
    // conditional render (`{open && (...)}`) so it -- unlike the message
    // DATA itself, which lives in useCommander() in this always-mounted
    // outer component and survives closing fine -- is genuinely unmounted
    // every time the panel closes. Remounting on reopen always starts a
    // fresh DOM element at scrollTop=0, and the auto-scroll-to-bottom
    // effect below then always jumped it straight to the newest message,
    // discarding wherever in the conversation the operator had scrolled
    // to before closing.
    //
    // Fix: persist the last scroll position in a ref that lives in this
    // outer, never-unmounted component (survives the inner panel's
    // mount/unmount cycles), and restore it the moment the scrollable div
    // remounts. Only auto-scroll to the newest message when the operator
    // was ALREADY at (or near) the bottom before a new message arrived --
    // exactly like how real chat apps (Slack, iMessage, etc.) behave: if
    // you're actively reading history, a new message doesn't yank you
    // away from it, but if you were already caught up, it keeps you
    // caught up.
    const lastScrollTopRef = useRef(0);
    const wasNearBottomRef = useRef(true);

    useEffect(() => {
        if (sending) setOpen(true);
    }, [sending]);

    // Restore scroll position the instant the scrollable div (re)mounts --
    // this specifically handles the close/reopen case, since a fresh DOM
    // node always starts at scrollTop=0 regardless of what value we
    // previously observed.
    useEffect(() => {
        if (open && tab === 'chat' && scrollRef.current) {
            scrollRef.current.scrollTop = lastScrollTopRef.current;
        }
    }, [open, tab]);

    // Auto-scroll to the newest message ONLY if the operator was already
    // near the bottom (i.e. actively following the live conversation),
    // not if they'd scrolled up to review earlier history.
    useEffect(() => {
        if (wasNearBottomRef.current) {
            scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
        }
    }, [messages.length, sending]);

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

    if (!incidentId) return null;

    const visibleMessages = optimisticMessages.filter((om) => !messages.some((m) => m.role === om.role && m.content === om.content));

    return (
        <div className="fixed bottom-6 right-6 z-40 flex flex-col items-end gap-3">
            <AnimatePresence>
                {open && (
                    <motion.div
                        initial={{ opacity: 0, y: 16, scale: 0.96 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 16, scale: 0.96 }}
                        transition={{ type: 'spring', stiffness: 340, damping: 28 }}
                        // Uses `menu-panel`, not `console-surface`.
                        // console-surface is only 55% opaque with a
                        // backdrop blur, designed for panels that sit
                        // WITHIN the page's own scroll flow over a fairly
                        // uniform background -- as a floating overlay
                        // meant to sit on top of arbitrary page content,
                        // that translucency let page content bleed through
                        // distractingly (confirmed live via a screenshot
                        // showing "Recovery plan" tab text visible through
                        // the chat bubbles).
                        //
                        // BUG FIX (user-reported, 2nd round): my first fix
                        // used a hardcoded dark color (bg-[#0D0D15]),
                        // which broke light mode entirely -- this app has
                        // a real light/dark toggle (ThemeContext.tsx) and
                        // menu-panel is the EXISTING, theme-aware solution
                        // for this exact scenario (dropdowns/popovers
                        // floating over arbitrary content), using
                        // var(--color-surface-elevated) which resolves
                        // correctly in both themes. Should have reused
                        // this the first time instead of hardcoding.
                        className="menu-panel rounded-2xl overflow-hidden shadow-2xl w-[min(92vw,420px)] h-[min(70vh,560px)] flex flex-col"
                    >
                        <div className="px-4 py-3.5 flex items-center justify-between border-b border-white/[0.05] flex-shrink-0">
                            <div className="flex items-center gap-2">
                                <motion.span animate={sending ? { scale: [1, 1.15, 1], opacity: [1, 0.7, 1] } : { scale: 1, opacity: 1 }} transition={sending ? { duration: 1.4, repeat: Infinity, ease: 'easeInOut' } : { duration: 0.2 }}>
                                    <ShieldCheck className="w-3.5 h-3.5 text-agent-active" />
                                </motion.span>
                                <div className="font-semibold text-[13px] text-text-primary">Commander</div>
                                {sending && (
                                    <span className="text-[9.5px] font-bold uppercase tracking-wide text-agent-active flex items-center gap-1.5">
                                        <span className="w-1.5 h-1.5 rounded-full bg-agent-active animate-pulse" /> live
                                    </span>
                                )}
                            </div>
                            {/* UI MODERNIZATION (spec Section 18/73): icon-only close button had no accessible name. */}
                            <IconButton onClick={() => setOpen(false)} label="Close Commander">
                                <X className="w-4 h-4" />
                            </IconButton>
                        </div>

                        <div className="flex gap-1 px-3 pt-2.5 flex-shrink-0">
                            {(['chat', 'pulse'] as const).map((t) => (
                                <button
                                    key={t}
                                    onClick={() => setTab(t)}
                                    className={`focus-ring press-scale text-[10.5px] font-semibold px-3 py-1.5 rounded-lg transition-colors ${tab === t ? 'bg-primary/20 text-primary ring-1 ring-primary/35' : 'bg-white/[0.03] text-text-muted ring-1 ring-white/[0.06] hover:text-text-secondary'}`}
                                >
                                    {t === 'chat' ? 'Chat' : `Pulse${pulse.length > 0 ? ` (${pulse.length})` : ''}`}
                                </button>
                            ))}
                        </div>

                        {tab === 'chat' ? (
                            <>
                                <div
                                    ref={scrollRef}
                                    onScroll={(e) => {
                                        const el = e.currentTarget;
                                        lastScrollTopRef.current = el.scrollTop;
                                        wasNearBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
                                    }}
                                    className="flex-1 overflow-y-auto px-4 py-3 mt-2"
                                >
                                    {messages.length === 0 && visibleMessages.length === 0 && !sending ? (
                                        <EmptyState icon={<MessageSquare className="w-5 h-5" />} title="Ask, guide, or add a confirmed fact" subtitle="Commander answers questions, accepts guidance, and records facts -- but never approves or executes through chat." />
                                    ) : (
                                        <AnimatePresence initial={false}>
                                            {messages.map((m) => (
                                                <motion.div key={m.message_id} initial={{ opacity: 0, y: 10, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ type: 'spring', stiffness: 300, damping: 24 }}>
                                                    <ConversationBubble role={m.role} intent={m.intent} content={m.content} created_at={m.created_at} />
                                                </motion.div>
                                            ))}
                                            {visibleMessages.map((m) => (
                                                <motion.div key={m.message_id} initial={{ opacity: 0, y: 10, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ type: 'spring', stiffness: 300, damping: 24 }}>
                                                    <ConversationBubble role={m.role} intent={m.intent} content={m.content} created_at={m.created_at} />
                                                </motion.div>
                                            ))}
                                            {sending && <ThinkingBubble key="thinking" mode={mode} />}
                                        </AnimatePresence>
                                    )}
                                </div>
                                <div className="border-t border-white/[0.06] p-3 flex-shrink-0">
                                    <div className="flex gap-1.5 mb-2">
                                        {(['ASK', 'GUIDE', 'ADD_FACT'] as const).map((m) => (
                                            <button
                                                key={m}
                                                onClick={() => setMode(m)}
                                                disabled={sending}
                                                className={`focus-ring press-scale text-[10.5px] font-semibold px-2.5 py-1.5 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${mode === m ? 'bg-primary/20 text-primary ring-1 ring-primary/35' : 'bg-white/[0.03] text-text-muted ring-1 ring-white/[0.06] hover:text-text-secondary'}`}
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
                                            placeholder={sending ? 'Commander is responding...' : mode === 'ASK' ? 'Ask Commander...' : mode === 'GUIDE' ? 'Provide guidance...' : 'State a confirmed fact...'}
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
                            </>
                        ) : (
                            <div className="flex-1 overflow-y-auto px-4 py-3 mt-2">
                                {loading ? (
                                    <div className="text-[11px] text-text-muted py-4 text-center">Loading status...</div>
                                ) : pulse.length === 0 ? (
                                    <EmptyState icon={<Sparkles className="w-5 h-5" />} title="No status updates yet" subtitle="Commander Pulse populates as the investigation progresses." />
                                ) : (
                                    <AnimatePresence initial={false}>
                                        {pulse.map((u, idx) => (
                                            <motion.div key={u.update_id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: idx === 0 ? 0 : 0.02 * idx, type: 'spring', stiffness: 260, damping: 22 }}>
                                                <PulseItem headline={u.headline} summary={u.summary} severity={u.severity} created_at={u.created_at} />
                                            </motion.div>
                                        ))}
                                    </AnimatePresence>
                                )}
                            </div>
                        )}
                    </motion.div>
                )}
            </AnimatePresence>

            {/* The launcher button -- always visible, closed by default.
                Shows a pulsing badge while Commander is actively working
                so the operator has a persistent, ambient signal even with
                the panel collapsed, without ever taking up page real
                estate the way the earlier permanent-panel design did. */}
            {/* UI MODERNIZATION (spec Section 18/73): icon-only launcher button had no accessible name. */}
            <motion.button
                onClick={() => setOpen((o) => !o)}
                whileTap={{ scale: 0.92 }}
                aria-label={open ? 'Close Commander' : 'Open Commander'}
                title={open ? 'Close Commander' : 'Open Commander'}
                className="focus-ring relative w-14 h-14 rounded-full bg-primary text-white shadow-2xl shadow-primary/30 flex items-center justify-center"
            >
                <AnimatePresence mode="wait">
                    {open ? (
                        <motion.span key="close" initial={{ opacity: 0, rotate: -90 }} animate={{ opacity: 1, rotate: 0 }} exit={{ opacity: 0, rotate: 90 }}>
                            <X className="w-5 h-5" />
                        </motion.span>
                    ) : (
                        <motion.span key="bot" initial={{ opacity: 0, rotate: 90 }} animate={{ opacity: 1, rotate: 0 }} exit={{ opacity: 0, rotate: -90 }}>
                            <Bot className="w-5 h-5" />
                        </motion.span>
                    )}
                </AnimatePresence>
                {!open && sending && (
                    // BUG FIX (same theme issue as the panel background):
                    // ring-[#0A0A0F] was hardcoded dark, breaking light
                    // mode. ring-[var(--color-surface)] resolves to the
                    // real page background in whichever theme is active
                    // (dark: #0D0D16, light: #FFFFFF -- see index.css),
                    // so the badge's "cutout" ring always matches the
                    // actual page it's sitting on.
                    <motion.span
                        className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-agent-active ring-2 ring-[var(--color-surface)]"
                        animate={{ scale: [1, 1.3, 1] }}
                        transition={{ duration: 1.2, repeat: Infinity }}
                    />
                )}
            </motion.button>
        </div>
    );
}
