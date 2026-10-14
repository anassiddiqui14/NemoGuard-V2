import { useEffect, useRef, useState } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { Search, Bell, Sun, Moon, Clock, FileCheck2, PanelLeftClose, PanelLeftOpen, Menu } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { Toaster } from 'react-hot-toast';
import { useTheme } from '../../contexts/ThemeContext';
import { useNotifications } from '../../hooks/useNotifications';
import { GlobalNavRail } from './GlobalNavRail';
import { MobileNavDrawer } from './MobileNavDrawer';
import { UserMenu } from './UserMenu';
import { Logomark } from '../../pages/LandingPage/Brand';
import { CommandPalette } from '../../design-system/components/CommandPalette';

function ThemeToggle() {
    const { theme, toggleTheme } = useTheme();
    return (
        <button
            onClick={toggleTheme}
            className="press-scale relative p-2 text-text-secondary hover:text-text-primary hover:bg-white/[0.04] rounded-lg transition-colors"
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        >
            <AnimatePresence mode="wait" initial={false}>
                {theme === 'dark' ? (
                    <motion.span key="moon" initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 90, opacity: 0 }} transition={{ duration: 0.2 }} className="block">
                        <Moon className="w-4 h-4" />
                    </motion.span>
                ) : (
                    <motion.span key="sun" initial={{ rotate: 90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: -90, opacity: 0 }} transition={{ duration: 0.2 }} className="block">
                        <Sun className="w-4 h-4" />
                    </motion.span>
                )}
            </AnimatePresence>
        </button>
    );
}

function NotificationBell({ onSelectIncident }: { onSelectIncident: (id: string) => void }) {
    const notifications = useNotifications();
    const [open, setOpen] = useState(false);
    const ref = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const onClick = (e: MouseEvent) => {
            if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
        };
        document.addEventListener('mousedown', onClick);
        return () => document.removeEventListener('mousedown', onClick);
    }, []);

    return (
        <div className="relative" ref={ref}>
            <button
                onClick={() => setOpen((o) => !o)}
                className="press-scale relative p-2 text-text-secondary hover:text-text-primary hover:bg-white/[0.04] rounded-lg transition-colors"
            >
                <Bell className="w-4 h-4" />
                {notifications.length > 0 && (
                    <motion.span
                        key={notifications.length}
                        initial={{ scale: 0.5 }}
                        animate={{ scale: 1 }}
                        className="absolute top-1 right-1 min-w-[15px] h-[15px] px-[3px] flex items-center justify-center bg-critical rounded-full text-[9px] font-bold text-white"
                    >
                        {notifications.length}
                    </motion.span>
                )}
            </button>

            <AnimatePresence>
                {open && (
                    <motion.div
                        initial={{ opacity: 0, y: -8, scale: 0.97 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: -8, scale: 0.97 }}
                        transition={{ duration: 0.15 }}
                        className="absolute right-0 top-full mt-2 w-80 menu-panel rounded-xl overflow-hidden z-50"
                    >
                        <div className="px-4 py-3 border-b border-white/[0.06] text-[12.5px] font-semibold text-text-primary">
                            Notifications
                        </div>
                        <div className="max-h-80 overflow-y-auto">
                            {notifications.length === 0 ? (
                                <div className="px-4 py-6 text-center text-[12px] text-text-muted">You're all caught up.</div>
                            ) : (
                                notifications.map((n) => (
                                    <button
                                        key={n.id}
                                        onClick={() => {
                                            onSelectIncident(n.incident_id);
                                            setOpen(false);
                                        }}
                                        className="w-full text-left px-4 py-3 hover:bg-white/[0.04] transition-colors flex items-start gap-2.5 border-b border-white/[0.04] last:border-b-0"
                                    >
                                        <div className={`w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 mt-0.5 ${n.kind === 'sla_risk' ? 'bg-critical/15 text-critical' : 'bg-warning/15 text-warning'}`}>
                                            {n.kind === 'sla_risk' ? <Clock className="w-3.5 h-3.5" /> : <FileCheck2 className="w-3.5 h-3.5" />}
                                        </div>
                                        <div className="min-w-0">
                                            <div className="text-[12px] font-medium text-text-primary truncate">{n.title}</div>
                                            <div className="text-[11px] text-text-muted mt-0.5">{n.detail}</div>
                                        </div>
                                    </button>
                                ))
                            )}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}

function TopBar({ onSelectIncident, onToggleNav, navCollapsed, onOpenMobileNav, onOpenCommandPalette }: { onSelectIncident: (id: string) => void; onToggleNav: () => void; navCollapsed: boolean; onOpenMobileNav: () => void; onOpenCommandPalette: () => void }) {
    return (
        <div className="h-16 border-b border-white/[0.06] flex items-center justify-between px-6 flex-shrink-0 glass-panel z-20 relative">
            <div className="flex items-center gap-2.5 min-w-0">
                {/*
                 * UI MODERNIZATION (Phase 4): mobile/tablet hamburger --
                 * previously there was no way to open navigation at all
                 * below the md breakpoint, since GlobalNavRail is
                 * `hidden md:flex` with no replacement. This button is the
                 * inverse visibility of the desktop collapse toggle below
                 * (md:hidden here, hidden md:inline-flex there) so exactly
                 * one navigation control shows at any given width.
                 */}
                <button
                    onClick={onOpenMobileNav}
                    className="press-scale md:hidden p-2 -ml-1 mr-1 text-text-secondary hover:text-text-primary hover:bg-white/[0.05] rounded-lg transition-colors flex-shrink-0"
                    aria-label="Open navigation"
                    title="Open navigation"
                >
                    <Menu className="w-4.5 h-4.5" />
                </button>
                <button
                    onClick={onToggleNav}
                    className="press-scale hidden md:inline-flex p-2 -ml-1 mr-1 text-text-secondary hover:text-text-primary hover:bg-white/[0.05] rounded-lg transition-colors flex-shrink-0"
                    title={navCollapsed ? 'Expand navigation' : 'Collapse navigation'}
                >
                    {navCollapsed ? <PanelLeftOpen className="w-4.5 h-4.5" /> : <PanelLeftClose className="w-4.5 h-4.5" />}
                </button>
                <motion.div
                    whileHover={{ scale: 1.06 }}
                    transition={{ type: 'spring', stiffness: 300, damping: 15 }}
                    className="relative flex items-center justify-center w-9 h-9 rounded-xl bg-primary/10 ring-1 ring-primary/25 text-primary"
                >
                    <Logomark className="w-5 h-5" />
                </motion.div>
                <div className="min-w-0 flex flex-col justify-center">
                    <h1 className="font-semibold text-text-primary text-[15px] leading-tight tracking-tight">
                        Nemo<span className="text-primary">Guard</span> <span className="text-text-secondary font-medium">Command Center</span>
                    </h1>
                    <p className="text-[11px] text-text-muted leading-tight">Agentic incident response</p>
                </div>
            </div>

            <div className="flex items-center gap-2">
                {/*
                 * UI MODERNIZATION (Phase 5): this used to be a static,
                 * non-functional `<input>` with no keyboard shortcut and
                 * no wiring to any search logic -- purely decorative.
                 * Replaced with a trigger that opens the real command
                 * palette (Cmd/Ctrl+K also works from anywhere in the
                 * app, not just when this is focused).
                 */}
                <button
                    onClick={onOpenCommandPalette}
                    className="relative hidden sm:flex items-center gap-2 pl-8 pr-3 py-1.5 bg-white/[0.03] border border-white/[0.06] rounded-lg text-[13px] text-text-muted hover:text-text-secondary hover:bg-white/[0.05] w-56 transition-all text-left"
                >
                    <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
                    <span className="flex-1">Search incidents…</span>
                    <kbd className="text-[9.5px] font-mono px-1 py-0.5 rounded ring-1 ring-white/[0.08] flex-shrink-0">⌘K</kbd>
                </button>

                <ThemeToggle />
                <NotificationBell onSelectIncident={onSelectIncident} />
                <UserMenu />
            </div>
        </div>
    );
}

export function AppShell() {
    const navigate = useNavigate();
    // The nav rail is now a persistent, collapsible sidebar (instead of a
    // hidden overlay drawer that required an extra click before every
    // navigation) -- collapsed state persists across sessions via
    // localStorage so a user's preference sticks.
    const [navCollapsed, setNavCollapsed] = useState(() => localStorage.getItem('nemoguard_nav_collapsed') === '1');
    const [mobileNavOpen, setMobileNavOpen] = useState(false);
    const [paletteKey, setPaletteKey] = useState(0);

    const handleSelectIncident = (incidentId: string) => {
        navigate(`/app?incident=${encodeURIComponent(incidentId)}`);
    };

    const toggleNav = () => {
        setNavCollapsed((prev) => {
            const next = !prev;
            localStorage.setItem('nemoguard_nav_collapsed', next ? '1' : '0');
            return next;
        });
    };

    return (
        <div className="flex flex-col h-screen w-full bg-app-bg overflow-hidden font-sans">
            <MobileNavDrawer open={mobileNavOpen} onClose={() => setMobileNavOpen(false)} />
            {/*
             * PHASE 1 FIX (NemoGuard UI Modernization Spec, Section 46/13):
             * <Toaster/> was previously mounted only inside Dashboard.tsx,
             * which unmounts on navigation to any other /app/* route. Since
             * toast.*() calls are fired from other routes too (e.g.
             * ScenarioCockpitPage), those toasts had no mounted <Toaster/>
             * to render into and were silently lost. Mounting it once here,
             * at the persistent shell level, makes toasts work from every
             * authenticated route. Styling uses the app's actual theme
             * tokens (surface/border/text) instead of react-hot-toast's
             * hardcoded defaults so toasts match dark/light mode correctly.
             */}
            <Toaster
                position="top-right"
                toastOptions={{
                    style: {
                        background: 'var(--color-surface-elevated)',
                        color: 'var(--color-text-primary)',
                        border: '1px solid var(--panel-border)',
                        fontSize: '13px',
                        boxShadow: '0 20px 44px -22px rgba(0,0,0,0.55), 0 0 0 1px rgba(0,0,0,0.04)',
                    },
                    success: { iconTheme: { primary: 'var(--color-healthy)', secondary: 'var(--color-surface-elevated)' } },
                    error: { iconTheme: { primary: 'var(--color-critical)', secondary: 'var(--color-surface-elevated)' } },
                }}
            />
            <TopBar
                onSelectIncident={handleSelectIncident}
                onToggleNav={toggleNav}
                navCollapsed={navCollapsed}
                onOpenMobileNav={() => setMobileNavOpen(true)}
                onOpenCommandPalette={() => setPaletteKey((k) => k + 1)}
            />
            {/*
             * CommandPalette owns its own Cmd/Ctrl+K listener and open
             * state internally (so the shortcut works app-wide regardless
             * of this click trigger). `paletteKey` is a simple counter the
             * TopBar's search button bumps on every click -- incrementing
             * it (even to the same conceptual "open" state) triggers the
             * palette's internal effect to open, without needing an
             * imperative ref/open() method on a self-contained component.
             */}
            <CommandPalette openSignal={paletteKey} />
            <div className="flex flex-1 min-h-0 overflow-hidden">
                <GlobalNavRail collapsed={navCollapsed} />
                <main className="flex-1 overflow-hidden">
                    <Outlet />
                </main>
            </div>
        </div>
    );
}
