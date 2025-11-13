import { useState } from 'react';

export default function Results({ data, onReset, onGenerateReport }) {
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);

  const handleGenerateReport = async () => {
    setIsGeneratingReport(true);
    try {
      await onGenerateReport();
    } finally {
      setIsGeneratingReport(false);
    }
  };

  const { damages, summary, original_image_url, annotated_image_url } = data;

  return (
    <div className="results-container">
      <div className="results-header">
        <h2>Analysis Results</h2>
        <button onClick={onReset} className="reset-button">
          Analyze Another Image
        </button>
      </div>

      {/* Summary Panel */}
      <div className="summary-panel">
        <h3>Summary</h3>
        <div className="summary-stats">
          <div className="stat-card">
            <div className="stat-value">{summary.total_damages}</div>
            <div className="stat-label">Total Damages</div>
          </div>

          {summary.by_severity && (
            <>
              <div className="stat-card severity-severe">
                <div className="stat-value">
                  {summary.by_severity.severe || 0}
                </div>
                <div className="stat-label">Severe</div>
              </div>
              <div className="stat-card severity-moderate">
                <div className="stat-value">
                  {summary.by_severity.moderate || 0}
                </div>
                <div className="stat-label">Moderate</div>
              </div>
              <div className="stat-card severity-minor">
                <div className="stat-value">
                  {summary.by_severity.minor || 0}
                </div>
                <div className="stat-label">Minor</div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Annotated Image */}
      <div className="annotated-image-container">
        <div className="image-panel">
          <h3>Detected Damage</h3>
          <img src={annotated_image_url} alt="Annotated roof with damage" />
        </div>
      </div>

      {/* Damage Details Table */}
      {damages && damages.length > 0 ? (
        <div className="damage-table-container">
          <h3>Damage Details</h3>
          <table className="damage-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Type</th>
                <th>Severity</th>
                <th>Confidence</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {damages.map((damage, index) => (
                <tr key={index}>
                  <td>{index + 1}</td>
                  <td>
                    {damage.type.replace(/_/g, ' ').replace(/\b\w/g, (l) =>
                      l.toUpperCase()
                    )}
                  </td>
                  <td>
                    <span className={`severity-badge severity-${damage.severity}`}>
                      {damage.severity.charAt(0).toUpperCase() +
                        damage.severity.slice(1)}
                    </span>
                  </td>
                  <td>{(damage.confidence * 100).toFixed(0)}%</td>
                  <td>{damage.description || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="no-damage">
          <h3>No Damage Detected</h3>
          <p>The analysis did not find any visible damage on this roof.</p>
        </div>
      )}

      {/* Generate Report Button */}
      <div className="actions">
        <button
          onClick={handleGenerateReport}
          disabled={isGeneratingReport}
          className="generate-report-button"
        >
          {isGeneratingReport ? 'Generating Report...' : 'Generate PDF Report'}
        </button>
      </div>
    </div>
  );
}
