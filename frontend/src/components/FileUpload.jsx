import { useRef, useState } from "react";

export function FileUpload({ onUpload, loading = false }) {
  const inputRef = useRef(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [error, setError] = useState(null);

  const handleBrowse = () => {
    inputRef.current?.click();
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    setError(null);
    if (!file) {
      setSelectedFile(null);
      return;
    }
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Please select a .csv file.");
      setSelectedFile(null);
      return;
    }
    setSelectedFile(file);
  };

  return (
    <div
      style={{
        background: "#161b22",
        border: "1px solid #30363d",
        borderRadius: 8,
        padding: "0.85rem 1rem",
      }}
    >
      <input ref={inputRef} type="file" accept=".csv" style={{ display: "none" }} onChange={handleFileChange} />
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
        <button type="button" style={browseBtnStyle} onClick={handleBrowse} disabled={loading}>
          Upload Sales CSV
        </button>
        {selectedFile ? (
          <span style={{ color: "#8b949e", fontSize: "0.9rem" }}>{selectedFile.name}</span>
        ) : (
          <span style={{ color: "#8b949e", fontSize: "0.9rem" }}>No file selected</span>
        )}
        {selectedFile && (
          <button type="button" style={uploadBtnStyle} onClick={() => onUpload(selectedFile)} disabled={loading}>
            {loading ? "Uploading..." : "Upload"}
          </button>
        )}
      </div>
      {error && <div style={{ color: "#f85149", marginTop: "0.5rem" }}>{error}</div>}
    </div>
  );
}

const browseBtnStyle = {
  background: "#1f6feb",
  border: "1px solid #388bfd",
  color: "white",
  borderRadius: 6,
  padding: "0.5rem 0.8rem",
  cursor: "pointer",
};

const uploadBtnStyle = {
  background: "#238636",
  border: "1px solid #2ea043",
  color: "white",
  borderRadius: 6,
  padding: "0.5rem 0.8rem",
  cursor: "pointer",
};
