import React, { useEffect, useState } from 'react';

export default function App() {
  const [health, setHealth] = useState<string>('checking...');

  useEffect(() => {
    fetch('/api/example/ping')
      .then(r => r.json())
      .then(d => setHealth(d.message))
      .catch(() => setHealth('server not running'));
  }, []);

  return (
    <div className="p-8 font-sans">
      <h1 className="text-2xl font-bold mb-2">OneDay Full</h1>
      <p className="text-gray-600 mb-4">TypeScript + React + Tailwind + Express 模板</p>
      <div className="text-sm bg-gray-100 rounded px-3 py-2 inline-block">
        API 状态: <span className="font-mono">{health}</span>
      </div>
    </div>
  );
}
