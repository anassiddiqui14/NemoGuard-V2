import toast from 'react-hot-toast';
import React from 'react';

/*
 * NemoGuard toast wrapper.
 *
 * WHY THIS EXISTS (UI Modernization Spec, Section 46):
 * Confirmed via grep in Phase 0 that `toast.success()`/`toast.error()`
 * from react-hot-toast were called directly at ~15 sites across 3 files
 * (IncidentWorkspace.tsx, PlanApprovalModal.tsx, ScenarioCockpitPage.tsx)
 * with no shared abstraction. The spec explicitly calls for wrapping the
 * toast library so styling/behavior stays centralized and the underlying
 * library could be swapped later without touching every call site.
 *
 * This does not replace react-hot-toast (Phase 1 already centralized its
 * <Toaster/> mount + default styling in AppShell.tsx) -- it gives call
 * sites a semantic, NemoGuard-specific API (`ngToast.success(...)`
 * instead of `toast.success(...)`) with consistent durations per
 * severity, matching the spec's guidance that destructive/critical
 * notifications should not disappear too quickly.
 */
export const ngToast = {
    success: (message: string, opts?: { duration?: number }) =>
        toast.success(message, { duration: opts?.duration ?? 4000 }),

    error: (message: string, opts?: { duration?: number }) =>
        // Errors stay up longer by default -- an operator reading a failure
        // message mid-incident shouldn't have it vanish before they finish
        // reading it.
        toast.error(message, { duration: opts?.duration ?? 6000 }),

    info: (message: string, opts?: { duration?: number }) =>
        toast(message, { duration: opts?.duration ?? 4000, icon: 'ℹ️' }),

    warning: (message: string, opts?: { duration?: number }) =>
        toast(message, { duration: opts?.duration ?? 5000, icon: '⚠️' }),

    /** A toast with a clickable action, e.g. "View incident ->". */
    action: (message: string, actionLabel: string, onAction: () => void, opts?: { duration?: number }) =>
        toast.custom(
            (t) =>
                React.createElement(
                    'div',
                    {
                        className: `flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg transition-opacity ${t.visible ? 'opacity-100' : 'opacity-0'}`,
                        style: {
                            background: 'var(--color-surface-elevated)',
                            border: '1px solid var(--panel-border)',
                            color: 'var(--color-text-primary)',
                            fontSize: '13px',
                        },
                    },
                    React.createElement('span', { className: 'flex-1' }, message),
                    React.createElement(
                        'button',
                        {
                            onClick: () => {
                                onAction();
                                toast.dismiss(t.id);
                            },
                            className: 'text-primary font-semibold flex-shrink-0 hover:underline',
                        },
                        actionLabel,
                    ),
                ),
            { duration: opts?.duration ?? 6000 },
        ),
};
