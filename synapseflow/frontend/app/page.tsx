'use client';

import { useState, useEffect } from 'react';
import axios from 'axios';
import { motion } from 'framer-motion';
import Editor from '@monaco-editor/react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

interface Task {
  id: number;
  skill_id: number;
  title: string;
  description: string;
  difficulty: number;
  starter_code: string;
  estimated_time_minutes: number;
}

interface SubmissionResult {
  submission_id: number;
  passed: boolean;
  score: number;
  mastery_level: number;
  cognitive_state?: { conceptual_gap?: string };
}

interface Hint {
  hint_type?: string;
  content?: string;
  intensity?: number;
}

export default function SynapseFlowHome() {
  const [token, setToken] = useState<string | null>(null);
  const [isRegistering, setIsRegistering] = useState(false);
  const [code, setCode] = useState('# Write your code here\n');
  const [hints, setHints] = useState<Hint[]>([]);
  const [submissionResult, setSubmissionResult] = useState<SubmissionResult | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem('synapse_token');
    if (stored) setToken(stored);
  }, []);

  useEffect(() => {
    if (!token) return;
    const fetchTasks = async () => {
      try {
        const res = await axios.get(`${API_BASE}/tasks`, { headers: { Authorization: `Bearer ${token}` } });
        setTasks(res.data);
        if (res.data.length && selectedTaskId === null) {
          const first = res.data[0];
          setSelectedTaskId(first.id);
          setCode(first.starter_code || '# Write your code here\n');
        }
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Could not load tasks');
      }
    };
    fetchTasks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const handleAuth = async (e: any) => {
    e.preventDefault();
    const username = e.target.username.value;
    const password = e.target.password.value;
    const email = e.target.email?.value;
    try {
      if (isRegistering) {
        await axios.post(`${API_BASE}/auth/register`, null, {
          params: { email: email || `${username}@example.com`, username, password },
        });
      }
      const res = await axios.post(`${API_BASE}/auth/login`, new URLSearchParams({ username, password }));
      const t = res.data.access_token;
      setToken(t);
      localStorage.setItem('synapse_token', t);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Authentication failed');
    }
  };

  const selectTask = (id: number) => {
    setSelectedTaskId(id);
    const task = tasks.find((t) => t.id === id);
    if (task) setCode(task.starter_code || '# Write your code here\n');
    setSubmissionResult(null);
    setHints([]);
    setError(null);
  };

  const handleSubmit = async () => {
    if (!token || !selectedTaskId) { setError('Please login and select a task'); return; }
    try {
      const res = await axios.post(`${API_BASE}/tasks/submit`, null, {
        params: { task_id: selectedTaskId, code, struggle_time_seconds: 30 },
        headers: { Authorization: `Bearer ${token}` },
      });
      setSubmissionResult(res.data);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Submit failed');
    }
  };

  const handleHint = async () => {
    if (!submissionResult?.submission_id) { setError('Submit code first to get a hint'); return; }
    try {
      const res = await axios.get(`${API_BASE}/hints/next`, {
        params: { submission_id: submissionResult.submission_id },
        headers: { Authorization: `Bearer ${token}` },
      });
      setHints((prev) => [...prev, res.data]);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Hint failed');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('synapse_token');
    setToken(null);
    setTasks([]);
    setSelectedTaskId(null);
  };

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-50 to-purple-50 px-4">
        <motion.form onSubmit={handleAuth} className="bg-white p-8 rounded-2xl shadow-xl max-w-md w-full"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <h1 className="text-3xl font-bold mb-2 text-center bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
            SynapseFlow
          </h1>
          <p className="text-center text-gray-500 mb-6">Adaptive AI Learning</p>
          {isRegistering && (
            <input name="email" type="email" placeholder="Email" className="w-full border rounded-lg p-3 mb-3" required />
          )}
          <input name="username" placeholder="Username" className="w-full border rounded-lg p-3 mb-3" required />
          <input name="password" type="password" placeholder="Password" className="w-full border rounded-lg p-3 mb-4" required />
          <button className="w-full bg-indigo-600 text-white py-3 rounded-lg font-semibold hover:bg-indigo-700 transition">
            {isRegistering ? 'Register & Sign In' : 'Sign In'}
          </button>
          <button type="button" onClick={() => setIsRegistering((v) => !v)}
            className="w-full mt-3 text-sm text-indigo-600 hover:underline">
            {isRegistering ? 'Already have an account? Sign in' : 'Need an account? Register'}
          </button>
          {error && <p className="text-sm text-red-600 mt-4">{error}</p>}
        </motion.form>
      </div>
    );
  }

  const selectedTask = tasks.find((t) => t.id === selectedTaskId);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm px-6 py-4 flex justify-between items-center">
        <h1 className="text-xl font-bold text-indigo-600">SynapseFlow</h1>
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-500">Adaptive Learning Mode</span>
          <button onClick={handleLogout} className="text-sm px-3 py-1 bg-gray-100 rounded-md hover:bg-gray-200">Log out</button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-xl shadow-md overflow-hidden">
          <div className="px-4 py-3 bg-gray-50 border-b flex flex-wrap justify-between items-center gap-3">
            <div className="flex items-center gap-2">
              <label htmlFor="task-select" className="text-sm font-medium text-gray-700">Task</label>
              <select id="task-select" value={selectedTaskId ?? ''} onChange={(e) => selectTask(Number(e.target.value))}
                className="border rounded-md px-2 py-1 text-sm">
                {tasks.map((t) => <option key={t.id} value={t.id}>{t.title}</option>)}
              </select>
            </div>
            <button onClick={handleSubmit}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition text-sm">
              Submit Attempt
            </button>
          </div>
          <Editor
            height="420px"
            defaultLanguage="python"
            value={code}
            onChange={(v) => setCode(v || '')}
            theme="vs-light"
            options={{ minimap: { enabled: false }, fontSize: 14 }}
          />
          {selectedTask && (
            <div className="px-4 py-3 border-t bg-gray-50 text-sm text-gray-600">
              {selectedTask.description}
            </div>
          )}
        </div>

        <div className="space-y-6">
          <div className="bg-white rounded-xl shadow-md p-5">
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-semibold text-gray-700">Scaffold Coach</h3>
              <button onClick={handleHint}
                className="text-sm px-3 py-1 bg-indigo-100 text-indigo-700 rounded-md hover:bg-indigo-200 transition">
                Request Hint
              </button>
            </div>
            <div className="space-y-3 max-h-60 overflow-y-auto">
              {hints.length === 0 && (
                <p className="text-sm text-gray-400 italic">
                  When you submit code, I'll analyze your attempt and guide you (without giving answers).
                </p>
              )}
              {hints.map((h, i) => (
                <motion.div key={i} initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }}
                  className="bg-indigo-50 p-3 rounded-lg text-sm text-gray-700 border border-indigo-100">
                  <span className="text-xs text-indigo-600 font-medium capitalize block mb-1">
                    {h.hint_type?.replace('_', ' ') ?? 'hint'} · Intensity {(h.intensity || 0.5).toFixed(2)}
                  </span>
                  {h.content}
                </motion.div>
              ))}
            </div>
          </div>

          {submissionResult && (
            <div className={`rounded-xl shadow-md p-5 border-l-4 ${submissionResult.passed ? 'bg-green-50 border-green-500' : 'bg-orange-50 border-orange-500'}`}>
              <h3 className="font-semibold mb-2">{submissionResult.passed ? '✓ Mastered!' : 'Keep Going'}</h3>
              <p className="text-sm text-gray-600">
                Score: {submissionResult.score?.toFixed(0)} / 100
              </p>
              <p className="text-sm text-gray-600">
                Mastery level: {submissionResult.mastery_level?.toFixed(1)}%
              </p>
              <p className="text-xs text-gray-400 mt-2">
                {submissionResult.cognitive_state?.conceptual_gap || 'No conceptual gaps detected'}
              </p>
            </div>
          )}

          <div className="bg-white rounded-xl shadow-md p-5">
            <h3 className="font-semibold text-gray-700 mb-3">Skill Tree</h3>
            <div className="flex flex-wrap gap-2">
              {['Variables', 'Loops', 'Functions', 'Lists', 'Dicts'].map((s) => (
                <div key={s} className="px-3 py-2 bg-gray-100 rounded-lg text-xs text-gray-600 font-medium">
                  {s}
                </div>
              ))}
            </div>
            <p className="text-xs text-gray-400 mt-3">Unlocked skills appear here based on your mastery.</p>
          </div>
        </div>
      </main>

      {error && (
        <div className="fixed bottom-4 right-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg shadow-lg max-w-sm">
          {error}
        </div>
      )}
    </div>
  );
}