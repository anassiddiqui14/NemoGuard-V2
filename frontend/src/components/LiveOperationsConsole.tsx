import { useEffect, useRef } from 'react';
import { Terminal, CheckCircle, Activity, Loader2, AlertCircle } from 'lucide-react';
import type { AgentEvent } from '../hooks/useIncidentEvents';

interface Props {
  events: AgentEvent[];
  status: 'connecting' | 'connected' | 'disconnected';
}

export function LiveOperationsConsole({ events, status }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events]);

  const getEventIcon = (type: string) => {
    if (type.includes('FAILED') || type.includes('ERROR')) return <AlertCircle className="w-3.5 h-3.5 text-critical" />;
    if (type.includes('COMPLETED') || type.includes('CREATED') || type.includes('PASSED') || type.includes('RETRIEVED') || type.includes('CALCULATED') || type.includes('CORRELATED')) return <CheckCircle className="w-3.5 h-3.5 text-healthy" />;
    if (type.includes('STARTED')) return <Loader2 className="w-3.5 h-3.5 text-primary animate-spin" />;
    return <Terminal className="w-3.5 h-3.5 text-text-muted" />;
  };

  return (
    <div className="flex flex-col h-full">
      <div ref={scrollRef} className="flex-1 p-4 space-y-3" aria-live="polite">
        {events.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-text-muted">
            <Activity className={`w-7 h-7 mb-2.5 ${status === 'connected' ? 'text-primary animate-pulse' : 'text-text-muted opacity-40'}`} />
            <div className="text-[12.5px] font-medium">{status === 'connected' ? 'Listening for agent activity…' : 'Connecting to stream…'}</div>
          </div>
        ) : (
          <div className="relative before:absolute before:top-1 before:bottom-1 before:left-[13px] before:w-px before:bg-white/[0.06]">
            <div className="space-y-3">
              {events.map((evt) => (
                <div key={evt.id} className="relative flex gap-3 items-start">
                  <div className="mt-0.5 w-6 h-6 rounded-full bg-surface-secondary flex items-center justify-center relative z-10 ring-1 ring-white/[0.06]">
                    {getEventIcon(evt.event_type)}
                  </div>
                  <div className="flex-1 min-w-0 pb-0.5">
                    <div className="flex items-center gap-2 mb-1 overflow-hidden">
                      <span className="text-[11.5px] font-semibold text-text-primary truncate">{evt.source}</span>
                      <span
                        className={`text-[8.5px] font-bold px-1.5 py-0.5 rounded whitespace-nowrap flex-shrink-0 ${evt.event_type.includes('COMPLETED') || evt.event_type.includes('CREATED') || evt.event_type.includes('PASSED')
                            ? 'bg-healthy/15 text-healthy'
                            : evt.event_type.includes('FAILED')
                              ? 'bg-critical/15 text-critical'
                              : 'bg-primary/15 text-primary'
                          }`}
                      >
                        {evt.event_type.replace(/_/g, ' ')}
                      </span>
                      <span className="text-[9.5px] font-mono text-text-muted flex-shrink-0 ml-auto">
                        {new Date(evt.timestamp).toLocaleTimeString([], { hour12: false })}
                      </span>
                    </div>
                    <div className="text-[12px] text-text-secondary leading-relaxed whitespace-pre-wrap">{evt.message}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
