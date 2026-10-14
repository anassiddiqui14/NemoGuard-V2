import { Settings, ShieldCheck } from 'lucide-react';
import {
    CommandCenterIcon,
    IncidentsIcon,
    AgentOpsIcon,
    IntelligenceIcon,
    ScenarioIcon,
    AdoptionIcon,
} from '../pages/LandingPage/NemoIcons';
import { useCurrentUser } from './useCurrentUser';

export interface NavItem {
    to: string;
    label: string;
    icon: React.ReactNode;
    end?: boolean;
}

/*
 * UI MODERNIZATION (Phase 4, mobile nav): previously this item list was
 * defined ONLY inside GlobalNavRail.tsx (the desktop-only, `hidden md:flex`
 * rail), with no mobile equivalent anywhere in the app -- meaning mobile/
 * tablet users below the md breakpoint had NO way to navigate between
 * sections at all once past the initial page. Extracted here so both the
 * desktop rail and the new mobile drawer (MobileNavDrawer.tsx) render from
 * exactly one source, guaranteeing identical order and admin-gating logic
 * rather than two lists that could silently drift apart (spec Section 26:
 * "same navigation order" as desktop).
 */
export function useNavItems(): NavItem[] {
    // "Admin" is only shown to users with the admin role -- this is purely
    // a UX convenience (hiding a section most users have no use for); the
    // real enforcement is on the backend, where every endpoint the Admin
    // page calls is already gated with require_role("admin") regardless
    // of whether this nav entry is visible.
    const { roles } = useCurrentUser();
    const isAdmin = roles.includes('admin');

    return [
        { to: '/app', label: 'Command Center', icon: <CommandCenterIcon className="w-4.5 h-4.5" />, end: true },
        { to: '/app/incidents', label: 'Incidents', icon: <IncidentsIcon className="w-4.5 h-4.5" /> },
        { to: '/app/agent-operations', label: 'Agent Operations', icon: <AgentOpsIcon className="w-4.5 h-4.5" /> },
        { to: '/app/intelligence', label: 'Intelligence', icon: <IntelligenceIcon className="w-4.5 h-4.5" /> },
        { to: '/app/scenario-cockpit', label: 'Scenario Cockpit', icon: <ScenarioIcon className="w-4.5 h-4.5" /> },
        { to: '/app/adoption-readiness', label: 'Adoption Readiness', icon: <AdoptionIcon className="w-4.5 h-4.5" /> },
        ...(isAdmin ? [{ to: '/app/admin', label: 'Admin', icon: <ShieldCheck className="w-4.5 h-4.5" /> }] : []),
        { to: '/app/settings', label: 'Settings', icon: <Settings className="w-4.5 h-4.5" /> },
    ];
}
