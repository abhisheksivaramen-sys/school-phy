import React, { useState } from 'react';

const API_KEY = "AQ.Ab8RN6Lt3289FjrYZup-V6v7FLMKLH8A6gJ_imAI_gH2sBZSjA";

export default function App() {
  const [response, setResponse] = useState("Select a Mastery Module or use the AI Tutor tools below.");
  const [loading, setLoading] = useState(false);

  const curriculum = [
    { title: "Scalar and Vector Quantities", prompt: "Define scalar and vector quantities with examples." },
    { title: "Distance and Displacement", prompt: "Distinguish between distance and displacement with examples." },
    { title: "Speed and Velocity", prompt: "Define speed and velocity. Explain their SI units and direction." },
    { title: "Acceleration and Retardation", prompt: "Define acceleration and retardation. Explain their SI units." },
    { title: "Equations of Motion", prompt: "State the three equations of motion and explain their applications." }
  ];

  const callGemini = async (inputPrompt) => {
    setLoading(true);
    try {
      const result = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key=${API_KEY}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: `You are a physics teacher. Answer this question in clean, plain text. Do not use any special formatting characters like hash, asterisk, underscore, or dollar signs. Keep it concise for a 5-10 minute review: ${inputPrompt}` }] }]
        })
      });
      const data = await result.json();
      const text = data.candidates[0].content.parts[0].text;
      const cleanText = text.replace(/[*#_$]/g, '');
      setResponse(cleanText);
    } catch (err) {
      setResponse("Connection error. Please check your API key.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#f9fafb', color: '#1f2937', padding: '24px', fontFamily: 'sans-serif' }}>
      <header style={{ maxWidth: '1200px', margin: '0 auto', marginBottom: '32px', borderBottom: '1px solid #d1d5db', paddingBottom: '24px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 'bold' }}>Physics Mastery Console</h1>
        <p style={{ color: '#4b5563', marginTop: '8px' }}>Classroom Study Interface | Motion in One Dimension</p>
      </header>

      <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'grid', gridTemplateColumns: '1fr 3fr', gap: '24px' }}>
        <nav style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <h2 style={{ fontSize: '12px', fontWeight: 'bold', textTransform: 'uppercase', color: '#6b7280', marginBottom: '8px' }}>Mastery Modules</h2>
          {curriculum.map((item, idx) => (
            <button key={idx} onClick={() => callGemini(item.prompt)} style={{ textAlign: 'left', padding: '16px', backgroundColor: 'white', border: '1px solid #d1d5db', borderRadius: '4px', cursor: 'pointer' }}>
              {item.title}
            </button>
          ))}
          
          <div style={{ marginTop: '24px', paddingTop: '24px', borderTop: '1px solid #d1d5db' }}>
            <h2 style={{ fontSize: '12px', fontWeight: 'bold', textTransform: 'uppercase', color: '#6b7280', marginBottom: '16px' }}>AI Tutor Tools</h2>
            <button onClick={() => callGemini("Generate a 5-minute practice quiz of 3 conceptual physics questions.")} style={{ width: '100%', textAlign: 'left', padding: '16px', backgroundColor: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '4px', marginBottom: '8px', cursor: 'pointer' }}>Generate Practice Quiz</button>
            <button onClick={() => callGemini("Solve this problem: The speed of a car is 72 km h-1. Express it in m s-1.")} style={{ width: '100%', textAlign: 'left', padding: '16px', backgroundColor: '#ecfdf5', border: '1px solid #a7f3d0', borderRadius: '4px', cursor: 'pointer' }}>Solve Numerical Problem</button>
          </div>
        </nav>

        <main style={{ backgroundColor: 'white', padding: '32px', border: '1px solid #d1d5db', borderRadius: '4px', minHeight: '500px' }}>
          {loading ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#6b7280' }}>Processing request...</div>
          ) : (
            <p style={{ whiteSpace: 'pre-line', fontSize: '18px', lineHeight: '1.6' }}>{response}</p>
          )}
        </main>
      </div>
    </div>
  );
}