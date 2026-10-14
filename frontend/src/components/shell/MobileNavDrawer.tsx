import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { NavLink } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';
import { useNavItems } from '../../hooks/useNavItems';
import { Logomark } from '../../pages/LandingPage/Brand';

/*
 * NemoGuard mobile navigation drawer.
 *
 * WHY THIS EXISTS (UI Modernization Spec, Section 3/26):
 * GlobalNavRail.tsx is `hidden md:flex` -- it renders NOTHING below the md
 * breakpoint (~768px). Verified this is a genuine dead-end, not a
 * hypothetical one: there was no hamburger button, no drawer, no mobile
 * equivalent anywhere in AppShell.tsx. A user on a phone or narrow tablet
 * could reach /app once (e.g. via a bookmark or notification link) but had
 * NO way to navigate to any other section afterward.
 *
 * This drawer renders the exact same nav items, in the exact same order,
 * as the desktop rail (both now read from the shared useNavItems() hook),
 * satisfying the spec's explicit requirement that mobile nav use "same
 * navigation order" as desktop. Full accessibility treatment: Escape to
 * close, focus trap, body-scroll lock, backdrop click-to-close.
 */
export function MobileNavDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
    const items = useNavItems();
    const panelRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!open) return;

        const previousOverflow = document.body.style.overflow;
        document.body.style.overflow = 'hidden';
        panelRef.current?.focus();

        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                onClose();
                return;
            }
            if (e.key !== 'Tab' || !panelRef.current) return;
            const focusable = panelRef.current.querySelectorAll<HTMLElement>(
                'a, button, [tabindex]:not([tabindex="-1"])',
            );
            if (focusable.length === 0) return;
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (e.shiftKey && document.activeElement === first) {
                e.preventDefault();
                last.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault();
                first.focus();
            }
        };

        document.addEventListener('keydown', handleKeyDown);
        return () => {
            document.removeEventListener('keydown', handleKeyDown);
            document.body.style.overflow = previousOverflow;
        };
    }, [open, onClose]);

    return createPortal(
        <AnimatePresence>
            {open && (
                <>
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.18 }}
                        className="fixed inset-0 z-[60] bg-black/60 backdrop-blur-sm md:hidden"
                        onClick={onClose}
                    />
                    <motion.div
                        ref={panelRef}
                        tabIndex={-1}
                        role="dialog"
                        aria-modal="true"
                        aria-label="Navigation"
                        initial={{ x: '-100%' }}
                        animate={{ x: 0 }}
                        exit={{ x: '-100%' }}
                        transition={{ type: 'spring', stiffness: 360, damping: 36 }}
                        className="fixed inset-y-0 left-0 z-[61] w-[280px] max-w-[85vw] bg-surface border-r border-white/[0.08] flex flex-col md:hidden outline-none"
                    >
                        <div className="h-16 flex items-center justify-between px-4 border-b border-white/[0.06] flex-shrink-0">
                            <div className="flex items-center gap-2">
                                <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10 ring-1 ring-primary/25 text-primary">
                                    <Logomark className="w-4.5 h-4.5" />
                                </div>
                                <span className="font-semibold text-text-primary text-[14px]">
                                    Nemo<span className="text-primary">Guard</span>
                                </span>
                            </div>
                            <button
                                onClick={onClose}
                                aria-label="Close navigation"
                                title="Close navigation"
                                className="press-scale focus-ring p-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-white/[0.05]"
                            >
                                <X className="w-4.5 h-4.5" />
                            </button>
                        </div>

                        <nav className="flex-1 overflow-y-auto py-3 px-2.5 space-y-1">
                            {items.map((item) => (
                                <NavLink
                                    key={item.to}
                                    to={item.to}
                                    end={item.end}
                                    onClick={onClose}
                                    className={({ isActive }) =>
                                        `relative flex items-center gap-3 px-3 py-3 rounded-xl transition-colors ${isActive
                                            ? 'bg-primary/[0.12] text-primary ring-1 ring-primary/25'
                                            : 'text-text-secondary hover:bg-white/[0.04] hover:text-text-primary'
                                        }`
                                    }
                                >
                                    <span className="flex-shrink-0">{item.icon}</span>
                                    <span className="text-[14px] font-medium">{item.label}</span>
                                </NavLink>
                            ))}
                        </nav>
                    </motion.div>
                </>
            )}
        </AnimatePresence>,
        document.body,
    );
}
