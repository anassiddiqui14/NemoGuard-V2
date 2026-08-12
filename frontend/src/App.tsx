import { Search, Bell, Sparkles, Sun, Moon, Clock, FileCheck2, Activity, BrainCircuit, ClipboardList, LayoutDashboard, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useTheme } from './contexts/ThemeContext';
import { useNotifications } from './hooks/useNotifications';
import { Dashboard } from './components/Dashboard';
import { WorkspacePage } from './components/WorkspacePages';

type Workspace = 'command' | 'incidents' | 'operations' | 'intelligence';

function useAuthToken() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('nemoguard_token'));

  useEffect(() => {
    if (token) return;
    (async () => {
      try {
        const res = await fetch('/api/v2/auth/mock-login?role=commander');
        if (res.ok) {
          const data = await res.json();
          localStorage.setItem('nemoguard_token', data.access_token);
          setToken(data.access_token);
        }
      } catch {
        // ignore
      }
    })();
  }, [token]);

  return token;
}

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
            className="absolute right-0 top-full mt-2 w-80 glass-panel rounded-xl shadow-2xl overflow-hidden z-50 ring-1 ring-white/[0.08]"
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

function TopBar({ onSelectIncident, onToggleNav, navCollapsed }: { onSelectIncident: (id: string) => void; onToggleNav: () => void; navCollapsed: boolean }) {
  useAuthToken();
  return (
    <div className="min-h-16 border-b border-white/[0.06] flex items-center justify-between gap-3 px-4 sm:px-6 flex-shrink-0 glass-panel z-20 relative">
      <div className="flex items-center gap-2.5 min-w-0">
        <button onClick={onToggleNav} className="hidden lg:inline-flex p-2 rounded-lg text-text-muted hover:bg-white/[0.04] hover:text-text-primary" aria-label="Toggle navigation">{navCollapsed ? <PanelLeftOpen className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}</button>
        <motion.div
          whileHover={{ rotate: 8, scale: 1.05 }}
          transition={{ type: 'spring', stiffness: 300, damping: 15 }}
          className="relative flex items-center justify-center w-9 h-9 rounded-xl bg-gradient-to-br from-primary via-indigo-500 to-agent-active shadow-lg shadow-primary/30"
        >
          <Sparkles className="w-4.5 h-4.5 text-white" strokeWidth={2.2} />
        </motion.div>
        <div className="min-w-0 flex flex-col justify-center">
          <h1 className="font-semibold text-text-primary text-[15px] leading-tight tracking-tight">
            NemoGuard <span className="text-gradient font-semibold">Command Center</span>
          </h1>
          <p className="hidden sm:block text-[11px] text-text-muted leading-tight">Agentic incident response</p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <div className="relative hidden lg:block">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
          <input
            type="text"
            placeholder="Search incidents, evidence…"
            className="pl-8 pr-3 py-2 bg-white/[0.03] border border-white/[0.06] rounded-xl text-[13px] text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary/40 w-64 transition-all"
          />
        </div>

        <ThemeToggle />
        <NotificationBell onSelectIncident={onSelectIncident} />

        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-agent-active to-primary flex items-center justify-center text-[11px] font-semibold text-white cursor-pointer shadow-md press-scale">
          SR
        </div>
      </div>
    </div>
  );
}

function Sidebar({ page, onChange, collapsed }: { page: Workspace; onChange: (page: Workspace) => void; collapsed: boolean }) {
  const navigation: { id: Workspace; label: string; icon: ReactNode; group: string }[] = [
    { id: 'command', label: 'Command Center', icon: <LayoutDashboard />, group: 'Workspace' },
    { id: 'incidents', label: 'Incidents', icon: <ClipboardList />, group: 'Response' },
    { id: 'operations', label: 'Operations', icon: <Activity />, group: 'Response' },
    { id: 'intelligence', label: 'Intelligence', icon: <BrainCircuit />, group: 'Insights' },
  ];
  return <nav className={`${collapsed ? 'lg:w-[68px] lg:p-2' : 'lg:w-[230px]'} w-full lg:h-full shrink-0 border-b lg:border-b-0 lg:border-r border-white/[0.06] bg-black/20 p-2 lg:p-3 transition-[width,padding] duration-200`}><div className={`flex lg:flex-col gap-1 overflow-x-auto ${collapsed ? 'lg:items-center' : ''}`}>{navigation.map((item, index) => <div key={item.id} className={collapsed ? 'lg:w-full' : 'contents'}>{(index === 0 || navigation[index - 1].group !== item.group) && <div className={`${collapsed ? 'lg:hidden' : ''} hidden lg:block mt-3 mb-1 px-2 text-[10px] uppercase tracking-[0.14em] font-bold text-text-muted`}>{item.group}</div>}<button onClick={() => onChange(item.id)} title={item.label} className={`${page === item.id ? 'bg-primary/14 text-primary ring-1 ring-primary/25' : 'text-text-secondary hover:bg-white/[0.04] hover:text-text-primary'} flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium whitespace-nowrap transition-colors ${collapsed ? 'lg:w-full lg:h-11 lg:justify-center lg:px-0' : ''}`}><span className="w-4 h-4 shrink-0">{item.icon}</span><span className={collapsed ? 'lg:hidden' : ''}>{item.label}</span></button></div>)}</div></nav>;
}

function App() {
  const [focusIncidentId, setFocusIncidentId] = useState<string | null>(null);
  const [page, setPage] = useState<Workspace>('command');
  const [navCollapsed, setNavCollapsed] = useState(false);
  const openIncident = (id: string) => { setFocusIncidentId(id); setPage('command'); };

  return (
    <div className="flex flex-col min-h-screen h-[100dvh] w-full bg-app-bg overflow-hidden font-sans">
      <TopBar onSelectIncident={openIncident} onToggleNav={() => setNavCollapsed((value) => !value)} navCollapsed={navCollapsed} />
      <main className="flex-1 min-h-0 flex flex-col lg:flex-row overflow-hidden">
        <Sidebar page={page} onChange={setPage} collapsed={navCollapsed} />
        {page === 'command' ? <Dashboard focusIncidentId={focusIncidentId} onFocusHandled={() => setFocusIncidentId(null)} /> : <WorkspacePage page={page} onOpenIncident={openIncident} />}
      </main>
    </div>
  );
}

export default App;
