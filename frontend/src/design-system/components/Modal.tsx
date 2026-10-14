import React, { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { motion } from 'framer-motion';
import { X } from 'lucide-react';
import { modalBackdrop, modalPanel } from '../../components/dashboard/shared';

/*
 * NemoGuard design-system Modal primitive.
 *
 * WHY THIS EXISTS (UI Modernization Spec, Section 64/56):
 * Audited both existing modals (CancelIncidentModal, EvidenceModal) before
 * writing this -- they share an identical visual structure (backdrop blur
 * + glass-panel rounded-2xl + icon/title/close header + content region)
 * but each hand-rolls that chrome independently, AND NEITHER has:
 *   - Escape-key handling to close
 *   - A focus trap (keyboard focus can tab out behind the modal)
 *   - Body-scroll lock while open
 * all of which the spec explicitly requires (Section 56: "dialog focus
 * trap", "escape handling"). This is a genuine, verified accessibility
 * gap, not a hypothetical one.
 *
 * This component preserves the exact existing visual language (same
 * backdrop/panel motion presets already defined in shared.tsx, same
 * glass-panel + ring treatment, same header layout) while fixing all
 * three gaps for every modal that migrates to it.
 */

export interface ModalProps {
    open: boolean;
    onClose: () => void;
    title: string;
    icon?: React.ReactNode;
    iconClassName?: string;
    children: React.ReactNode;
    footer?: React.ReactNode;
    maxWidth?: string;
}

export function Modal({ open, onClose, title, icon, iconClassName = 'bg-primary/12 ring-1 ring-primary/25 text-primary', children, footer, maxWidth = 'max-w-md' }: ModalProps) {
    const panelRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!open) return;

        const previouslyFocused = document.activeElement as HTMLElement | null;
        const previousOverflow = document.body.style.overflow;
        document.body.style.overflow = 'hidden';

        // Focus the panel itself first so Tab from here moves into its
        // first focusable child, establishing a basic focus trap boundary.
        panelRef.current?.focus();

        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                onClose();
                return;
            }
            if (e.key !== 'Tab' || !panelRef.current) return;

            const focusable = panelRef.current.querySelectorAll<HTMLElement>(
                'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
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
            previouslyFocused?.focus?.();
        };
    }, [open, onClose]);

    if (!open) return null;

    return createPortal(
        <motion.div
            {...modalBackdrop}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
            onMouseDown={(e) => {
                if (e.target === e.currentTarget) onClose();
            }}
        >
            <motion.div
                {...modalPanel}
                ref={panelRef}
                tabIndex={-1}
                role="dialog"
                aria-modal="true"
                aria-label={title}
                className={`glass-panel rounded-2xl shadow-2xl w-full ${maxWidth} overflow-hidden ring-1 ring-white/[0.08] outline-none`}
            >
                <div className="px-6 py-4 border-b border-white/[0.06] flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                        {icon && (
                            <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${iconClassName}`}>
                                {icon}
                            </div>
                        )}
                        <h2 className="text-[15px] font-semibold text-text-primary">{title}</h2>
                    </div>
                    <button
                        onClick={onClose}
                        aria-label="Close"
                        title="Close"
                        className="press-scale focus-ring p-2 hover:bg-white/[0.06] rounded-full transition-colors text-text-muted hover:text-text-primary"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>

                {children}

                {footer && <div className="border-t border-white/[0.06] p-5 flex justify-end gap-3">{footer}</div>}
            </motion.div>
        </motion.div>,
        document.body,
    );
}
