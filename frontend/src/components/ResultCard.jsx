function ResultCard({ title, children, copyText }) {
    const copyToClipboard = async () => {
      await navigator.clipboard.writeText(copyText);
    };
  
    return (
      <div className="result-card">
        <div className="result-card-header">
          <h3>{title}</h3>
  
          {copyText && (
            <button
              type="button"
              onClick={copyToClipboard}
            >
              Copy
            </button>
          )}
        </div>
  
        <div className="result-card-body">
          {children}
        </div>
      </div>
    );
  }
  
  export default ResultCard;