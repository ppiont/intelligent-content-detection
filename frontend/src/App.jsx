import { useState } from 'react';
import ImageUpload from './components/ImageUpload';
import Results from './components/Results';
import './App.css';

function App() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [results, setResults] = useState(null);

  const handleUpload = async (file) => {
    setIsLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);

    const apiUrl = import.meta.env.VITE_API_URL || '';

    try {
      const response = await fetch(`${apiUrl}/api/analyze`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        let errorMessage = 'Failed to analyze image';
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorMessage;
        } catch (jsonErr) {
          try {
            const errorText = await response.text();
            errorMessage = errorText || `Server error (${response.status})`;
          } catch {
            errorMessage = `Server error (${response.status})`;
          }
        }
        throw new Error(errorMessage);
      }

      const data = await response.json();
      setResults(data);
    } catch (err) {
      setError(err.message);
      console.error('Error analyzing image:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setResults(null);
    setError(null);
  };

  const handleGenerateReport = async () => {
    if (!results) return;

    const apiUrl = import.meta.env.VITE_API_URL || '';

    try {
      const response = await fetch(`${apiUrl}/api/generate-report`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          damages: results.damages,
          summary: results.summary,
          annotated_image_url: results.annotated_image_url,
          original_image_url: results.original_image_url,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to generate report');
      }

      // Download the PDF
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `roof_damage_report_${new Date().toISOString().split('T')[0]}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      setError(err.message);
      console.error('Error generating report:', err);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>RoofScan AI</h1>
        <p className="subtitle">
          Automated Roof Damage Detection for Insurance Claims
        </p>
      </header>

      <main className="app-main">
        {error && (
          <div className="error-banner">
            <strong>Error:</strong> {error}
            <button onClick={() => setError(null)} className="close-error">
              ×
            </button>
          </div>
        )}

        {!results ? (
          <ImageUpload onUpload={handleUpload} isLoading={isLoading} />
        ) : (
          <Results
            data={results}
            onReset={handleReset}
            onGenerateReport={handleGenerateReport}
          />
        )}
      </main>

      <footer className="app-footer">
        <p>
          Powered by OpenAI GPT-4o (2024-11-20) | Advanced AI Roof Damage Detection
        </p>
      </footer>
    </div>
  );
}

export default App;
