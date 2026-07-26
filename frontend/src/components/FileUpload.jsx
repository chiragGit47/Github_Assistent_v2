import { useState } from "react";

import api from "../services/api";


function FileUpload({ sessionId, onPrepared }) {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const prepareUpload = async () => {
    if (!file) {
      setMessage("Please select a file.");
      return;
    }

    const formData = new FormData();

    formData.append("session_id", sessionId);
    formData.append("file", file);

    setLoading(true);
    setMessage("");

    try {
      const response = await api.post(
        "/github/prepare-upload",
        formData
      );

      const result = response.data;

      onPrepared({
        uploadId: result.upload_id,
        filename: result.filename,
        isZip: file.name.toLowerCase().endsWith(".zip"),
      });

      setMessage(
        `${result.filename} is ready to upload.`
      );
    } catch (error) {
      setMessage(
        error.response?.data?.detail ||
        error.response?.data?.message ||
        "Could not prepare the file."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <section>
      <input
        type="file"
        onChange={(event) =>
          setFile(event.target.files?.[0] || null)
        }
      />

      <button
        type="button"
        onClick={prepareUpload}
        disabled={!file || loading}
      >
        {loading ? "Preparing..." : "Prepare file"}
      </button>

      {message && <p>{message}</p>}
    </section>
  );
}

export default FileUpload;