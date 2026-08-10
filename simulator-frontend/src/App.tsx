import { useState } from 'react';
import './App.css';

function App() {
  const [status, setStatus] = useState<string | null>(null);
  const [prompt, setPrompt] = useState<string>('');

  const triggerScenario = async (type: string) => {
    setStatus(`Triggering ${type}...`);
    try {
      const response = await fetch('http://localhost:8001/trigger', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_type: type })
      });
      if (response.ok) {
        setStatus(`Successfully fired ${type} into NemoGuard!`);
      } else {
        setStatus(`Failed to fire ${type}: API Error`);
      }
    } catch (e) {
      setStatus(`Network error hitting simulator backend on port 8001.`);
    }
    
    setTimeout(() => setStatus(null), 3000);
  };

  const triggerAI = async () => {
    if (!prompt.trim()) return;
    setStatus(`Contacting LLM...`);
    try {
      const response = await fetch('http://localhost:8001/trigger/ai', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt })
      });
      if (response.ok && response.body) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          const text = decoder.decode(value);
          const lines = text.split('\n');
          for (const line of lines) {
            if (line.startsWith("status: ")) {
              setStatus(line.replace("status: ", ""));
            }
          }
        }
        setPrompt('');
      } else {
        setStatus(`Failed to fire AI scenario: API Error`);
      }
    } catch (e) {
      setStatus(`Network error hitting simulator backend on port 8001.`);
    }
    setTimeout(() => setStatus(null), 5000);
  };

  const triggerReset = async () => {
    setStatus(`Resetting all incidents...`);
    try {
      const response = await fetch('http://localhost:8001/reset', { method: 'POST' });
      if (response.ok) {
        setStatus(`Successfully cleared all incidents and alerts!`);
      } else {
        setStatus(`Failed to reset incidents.`);
      }
    } catch (e) {
      setStatus(`Network error hitting simulator backend on port 8001.`);
    }
    setTimeout(() => setStatus(null), 3000);
  };

  return (
    <div style={{ padding: '2rem', fontFamily: 'system-ui, sans-serif', maxWidth: '800px', margin: '0 auto' }}>
      <h1>Chaos Engineering Simulator</h1>
      <p>
        This application runs entirely isolated from NemoGuard. It simulates your infrastructure.
        When you click a button below, this simulator will inject logs into the database (simulating a service)
        and then immediately fire a raw JSON webhook to NemoGuard over the network.
      </p>
      
      <div style={{ display: 'flex', gap: '1rem', marginTop: '2rem', flexWrap: 'wrap' }}>
        <button 
          onClick={() => triggerScenario('SCHEMA_REGRESSION')}
          style={{ padding: '1rem', background: '#dc2626', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold' }}
        >
          Fire Webhook: Schema Regression
        </button>
        
          <button 
            onClick={() => triggerScenario('OOM_CRASH')}
            style={{ padding: '1rem', background: '#ea580c', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold' }}
          >
            Fire Webhook: Spark OOM Crash
          </button>
          
          <button 
            onClick={() => triggerScenario('CASCADING_FAILURE')}
            style={{ padding: '1rem', background: '#9333ea', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold' }}
          >
            Fire Webhook: Cascading Failure
          </button>
          
          <button 
            onClick={triggerReset}
            style={{ padding: '1rem', background: '#ef4444', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold' }}
          >
            Reset All Incidents
          </button>
      </div>

      <div style={{ marginTop: '3rem', padding: '1.5rem', background: '#f8fafc', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
        <h2 style={{ marginTop: 0 }}>Generative AI Simulator</h2>
        <p style={{ color: '#64748b', marginBottom: '1rem' }}>
          Describe a completely custom incident scenario. The LLM will dynamically generate realistic logs, alerts, and dependency maps matching your description and inject them into NemoGuard.
        </p>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="e.g. A severe network partition in the payments gateway causing timeouts..."
          style={{ width: '100%', height: '100px', padding: '0.75rem', borderRadius: '8px', border: '1px solid #cbd5e1', marginBottom: '1rem', fontFamily: 'inherit', resize: 'vertical' }}
        />
        <button 
          onClick={triggerAI}
          disabled={!prompt.trim()}
          style={{ padding: '1rem 2rem', background: prompt.trim() ? '#7c3aed' : '#cbd5e1', color: 'white', border: 'none', borderRadius: '8px', cursor: prompt.trim() ? 'pointer' : 'not-allowed', fontWeight: 'bold', width: '100%' }}
        >
          Generate Custom Alert Storm
        </button>
      </div>
      
      {status && (
        <div style={{ marginTop: '2rem', padding: '1rem', background: '#f3f4f6', borderRadius: '8px', borderLeft: '4px solid #2563eb' }}>
          <strong>Status:</strong> {status}
        </div>
      )}
    </div>
  );
}

export default App;
