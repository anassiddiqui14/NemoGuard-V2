import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, CornerDownLeft } from 'lucide-react';
import { useNavItems } from '../../hooks/useNavItems';
import { authFetch } from '../../contexts/AuthGateContext';
import type { IncidentSummary } from '../../components/dashboard/shared';
import { severityPill } from '../../components/dashboard/shared';

/*
 * NemoGuard command palette.
 *
 * WHY THIS EXISTS (UI Modernization Spec, Section 28):
 * TopBar had a static, non-functional-looking search `<input>` with no
 * keyboard shortcut, no results, and no wiring to anything -- purely
 * decorative. The spec explicitly calls for a Cmd/Ctrl+K command palette
 * supporting route navigation and incident lookup as the first iteration
 * (not full natural-language AI search). This implements exactly that:
 * fuzzy-matches the same nav items used by GlobalNavRail/MobileNavDrawer
 * (useNavItems -- single source of truth, no duplicated route list), and
 * live-searches real incidents via the existing /api/v2/incidents
 * endpoint rather than inventing a new one.
 */
export function CommandPalette({ openSignal }: { openSignal?: number }) {
    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState('');
    const [incidents, setIncidents] = useState<IncidentSummary[]>([]);
    const [activeIndex, setActiveIndex] = useState(0);
    const inputRef = useRef<HTMLInputElement>(null);
    const navigate = useNavigate();
    const navItems = useNavItems();

    // External trigger (e.g. the TopBar search button) -- incrementing
    // `openSignal` opens the palette, mirroring the Cmd/Ctrl+K shortcut
    // without requiring this self-contained component to expose an
    // imperative ref/open method. Skips the initial mount (openSignal
    // starts at 0 in AppShell) so the palette doesn't pop open
    // automatically on page load.
    const isFirstRender = useRef(true);
    useEffect(() => {
        if (isFirstRender.current) {
            isFirstRender.current = false;
            return;
        }
        setOpen(true);
    }, [openSignal]);

    // Global Cmd/Ctrl+K listener -- works from anywhere in the app, not
    // just while the TopBar search field happens to be focused.
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
                e.preventDefault();
                setOpen((o) => !o);
            } else if (e.key === 'Escape' && open) {
                setOpen(false);
            }
        };
        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [open]);

    useEffect(() => {
        if (open) {
            setQuery('');
            setActiveIndex(0);
            // Fetch once on open rather than on every keystroke -- client-
            // side filtering below is plenty fast for a reasonable incident
            // count and avoids hammering the API while typing.
            authFetch('/api/v2/incidents?state=all')
                .then((res) => (res.ok ? res.json() : []))
                .then((data) => setIncidents(Array.isArray(data) ? data.slice(0, 50) : []))
                .catch(() => setIncidents([]));
            document.body.style.overflow = 'hidden';
            setTimeout(() => inputRef.current?.focus(), 0);
        } else {
            document.body.style.overflow = '';
        }
    }, [open]);

    const matchedNav = useMemo(() => {
        const q = query.trim().toLowerCase();
        if (!q) return navItems;
        return navItems.filter((n) => n.label.toLowerCase().includes(q));
    }, [navItems, query]);

    const matchedIncidents = useMemo(() => {
        const q = query.trim().toLowerCase();
        if (!q) return [];
        return incidents
            .filter((i) => i.title?.toLowerCase().includes(q) || i.incident_id?.toLowerCase().includes(q))
            .slice(0, 8);
    }, [incidents, query]);

    // Flattened list purely for arrow-key index math -- nav results first,
    // then incident results, matching the visual grouping order below.
    const flatResults = useMemo(
        () => [
            ...matchedNav.map((n) => ({ kind: 'nav' as const, item: n })),
            ...matchedIncidents.map((i) => ({ kind: 'incident' as const, item: i })),
        ],
        [matchedNav, matchedIncidents],
    );

    const close = () => setOpen(false);

    const selectResult = (idx: number) => {
        const result = flatResults[idx];
        if (!result) return;
        if (result.kind === 'nav') {
            navigate(result.item.to);
        } else {
            navigate(`/app?incident=${encodeURIComponent(result.item.incident_id)}`);
        }
        close();
    };

    const handleInputKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            setActiveIndex((i) => Math.min(i + 1, flatResults.length - 1));
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setActiveIndex((i) => Math.max(i - 1, 0));
        } else if (e.key === 'Enter') {
            e.preventDefault();
            selectResult(activeIndex);
        }
    };

    return createPortal(
        <AnimatePresence>
            {open && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.15 }}
                    className="fixed inset-0 z-[70] bg-black/60 backdrop-blur-sm flex items-start justify-center pt-[12vh] px-4"
                    onMouseDown={(e) => {
                        if (e.target === e.currentTarget) close();
                    }}
                >
                    <motion.div
                        initial={{ opacity: 0, scale: 0.97, y: -8 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.98, y: -4 }}
                        transition={{ duration: 0.17, ease: [0.16, 1, 0.3, 1] }}
                        role="dialog"
                        aria-modal="true"
                        aria-label="Command palette"
                        className="w-full max-w-lg menu-panel rounded-2xl overflow-hidden shadow-2xl"
                    >
                        <div className="flex items-center gap-2.5 px-4 py-3.5 border-b border-white/[0.06]">
                            <Search className="w-4 h-4 text-text-muted flex-shrink-0" />
                            <input
                                ref={inputRef}
                                value={query}
                                onChange={(e) => {
                                    setQuery(e.target.value);
                                    setActiveIndex(0);
                                }}
                                onKeyDown={handleInputKeyDown}
                                placeholder="Search incidents, or jump to a page…"
                                className="flex-1 bg-transparent text-[14px] text-text-primary placeholder:text-text-muted focus:outline-none"
                            />
                            <kbd className="text-[10px] font-mono text-text-muted px-1.5 py-0.5 rounded-md ring-1 ring-white/[0.08] flex-shrink-0">Esc</kbd>
                        </div>

                        <div className="max-h-[50vh] overflow-y-auto py-2">
                            {matchedNav.length > 0 && (
                                <div className="px-2 mb-1">
                                    <div className="px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-text-muted">Navigate</div>
                                    {matchedNav.map((item, idx) => {
                                        const flatIdx = idx;
                                        const isActive = flatIdx === activeIndex;
                                        return (
                                            <button
                                                key={item.to}
                                                onClick={() => selectResult(flatIdx)}
                                                onMouseEnter={() => setActiveIndex(flatIdx)}
                                                className={`w-full flex items-center gap-3 px-2.5 py-2 rounded-lg text-left transition-colors ${isActive ? 'bg-primary/[0.12] text-primary' : 'text-text-secondary hover:bg-white/[0.04]'}`}
                                            >
                                                <span className="flex-shrink-0 w-4 h-4 flex items-center justify-center">{item.icon}</span>
                                                <span className="text-[13px] font-medium flex-1">{item.label}</span>
                                                {isActive && <CornerDownLeft className="w-3 h-3 text-text-muted flex-shrink-0" />}
                                            </button>
                                        );
                                    })}
                                </div>
                            )}

                            {matchedIncidents.length > 0 && (
                                <div className="px-2">
                                    <div className="px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-text-muted">Incidents</div>
                                    {matchedIncidents.map((inc, idx) => {
                                        const flatIdx = matchedNav.length + idx;
                                        const isActive = flatIdx === activeIndex;
                                        return (
                                            <button
                                                key={inc.incident_id}
                                                onClick={() => selectResult(flatIdx)}
                                                onMouseEnter={() => setActiveIndex(flatIdx)}
                                                className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-left transition-colors ${isActive ? 'bg-primary/[0.12]' : 'hover:bg-white/[0.04]'}`}
                                            >
                                                {severityPill(inc.severity)}
                                                <span className={`text-[13px] font-medium truncate flex-1 ${isActive ? 'text-text-primary' : 'text-text-secondary'}`}>{inc.title}</span>
                                                <span className="text-[10px] font-mono text-text-muted flex-shrink-0">{inc.incident_id}</span>
                                            </button>
                                        );
                                    })}
                                </div>
                            )}

                            {query.trim() && matchedNav.length === 0 && matchedIncidents.length === 0 && (
                                <div className="px-4 py-8 text-center text-[12.5px] text-text-muted">No matches for "{query}"</div>
                            )}
                        </div>
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>,
        document.body,
    );
}
