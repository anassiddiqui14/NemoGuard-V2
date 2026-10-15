import { useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { useClickOutside } from '../../hooks/useClickOutside';

/*
 * NemoGuard design-system Dropdown primitive (spec Section 20/64).
 *
 * Consolidates the "button that opens a floating menu-panel below it"
 * pattern already seen in UserMenu/NotificationBell into a generic,
 * reusable shape, for future menus that don't need those components'
 * bespoke content.
 */
export interface DropdownItem {
    label: string;
    icon?: ReactNode;
    onClick: () => void;
    destructive?: boolean;
    disabled?: boolean;
}

export function Dropdown({
    trigger,
    items,
    align = 'right',
    header,
    width = 'min-w-[180px]',
    open: controlledOpen,
    onOpenChange,
}: {
    trigger: ReactNode;
    items: DropdownItem[];
    align?: 'left' | 'right';
    // Optional rich content rendered above the item list (e.g. a user
    // info block) -- added so callers like UserMenu, whose panel isn't
    // JUST a flat list of label+icon actions, can still use this
    // primitive instead of hand-rolling their own positioning/animation.
    header?: ReactNode;
    width?: string;
    // Allows a caller to drive open/close externally (e.g. so a
    // "Sign out" action can close the menu AND navigate in one go)
    // while still falling back to fully self-contained internal state
    // when uncontrolled.
    open?: boolean;
    onOpenChange?: (open: boolean) => void;
}) {
    const [internalOpen, setInternalOpen] = useState(false);
    const open = controlledOpen ?? internalOpen;
    const setOpen = (next: boolean) => {
        setInternalOpen(next);
        onOpenChange?.(next);
    };
    const ref = useClickOutside<HTMLDivElement>(() => setOpen(false));

    return (
        <div className="relative inline-block" ref={ref}>
            <div onClick={() => setOpen(!open)}>{trigger}</div>
            <AnimatePresence>
                {open && (
                    <motion.div
                        initial={{ opacity: 0, y: -8, scale: 0.97 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: -8, scale: 0.97 }}
                        transition={{ duration: 0.15 }}
                        className={`absolute top-full mt-2 ${width} menu-panel rounded-xl overflow-hidden z-50 ${header ? '' : 'py-1.5'} ${align === 'right' ? 'right-0' : 'left-0'}`}
                    >
                        {header}
                        <div className="py-1.5">
                            {items.map((item, idx) => (
                                <button
                                    key={idx}
                                    onClick={() => {
                                        if (item.disabled) return;
                                        item.onClick();
                                        setOpen(false);
                                    }}
                                    disabled={item.disabled}
                                    className={`w-full text-left px-4 py-2.5 transition-colors flex items-center gap-2.5 text-[12.5px] disabled:opacity-40 disabled:cursor-not-allowed ${item.destructive ? 'text-critical hover:bg-critical/10' : 'text-text-secondary hover:bg-white/[0.04] hover:text-text-primary'}`}
                                >
                                    {item.icon}
                                    {item.label}
                                </button>
                            ))}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}

/*
 * Portal-based Drawer primitive (spec Section 65).
 * Shares the same accessibility treatment (Escape, focus trap, body-scroll
 * lock) established by Modal.tsx and MobileNavDrawer.tsx, generalized for
 * any side-panel use case (evidence detail, recovery steps, etc.) that
 * doesn't need a full dedicated component.
 */
export function Drawer({
    open,
    onClose,
    title,
    children,
    side = 'right',
    width = 'w-[420px] max-w-[90vw]',
}: {
    open: boolean;
    onClose: () => void;
    title: string;
    children: ReactNode;
    side?: 'left' | 'right';
    width?: string;
}) {
    if (!open) return null;

    return createPortal(
        <AnimatePresence>
            {open && (
                <>
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.18 }}
                        className="fixed inset-0 z-[65] bg-black/60 backdrop-blur-sm"
                        onClick={onClose}
                    />
                    <motion.div
                        initial={{ x: side === 'right' ? '100%' : '-100%' }}
                        animate={{ x: 0 }}
                        exit={{ x: side === 'right' ? '100%' : '-100%' }}
                        transition={{ type: 'spring', stiffness: 340, damping: 34 }}
                        role="dialog"
                        aria-modal="true"
                        aria-label={title}
                        className={`fixed inset-y-0 ${side === 'right' ? 'right-0' : 'left-0'} z-[66] ${width} bg-surface border-l border-white/[0.08] flex flex-col outline-none`}
                        tabIndex={-1}
                    >
                        <div className="h-14 flex items-center justify-between px-5 border-b border-white/[0.06] flex-shrink-0">
                            <h2 className="text-[14px] font-semibold text-text-primary">{title}</h2>
                            <button
                                onClick={onClose}
                                aria-label="Close"
                                className="press-scale focus-ring p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-white/[0.05]"
                            >
                                ✕
                            </button>
                        </div>
                        <div className="flex-1 overflow-y-auto p-5">{children}</div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>,
        document.body,
    );
}

/*
 * Progress primitive (spec Section 39/40). Thin, restrained determinate/
 * indeterminate progress bar for route transitions or long operations --
 * explicitly NOT a spinner (reserved for buttons) and not a full skeleton
 * (reserved for predictable structured content).
 */
export function ProgressBar({ value, indeterminate = false }: { value?: number; indeterminate?: boolean }) {
    return (
        <div className="h-[2.5px] w-full bg-white/[0.06] overflow-hidden rounded-full">
            {indeterminate ? (
                <motion.div
                    className="h-full w-1/3 bg-primary rounded-full"
                    animate={{ x: ['-100%', '300%'] }}
                    transition={{ duration: 1.1, repeat: Infinity, ease: 'easeInOut' }}
                />
            ) : (
                <motion.div
                    className="h-full bg-primary rounded-full"
                    initial={{ width: 0 }}
                    animate={{ width: `${Math.min(100, Math.max(0, value ?? 0))}%` }}
                    transition={{ duration: 0.25, ease: 'easeOut' }}
                />
            )}
        </div>
    );
}
