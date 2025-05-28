import { useState, useEffect } from "react";
import axios from "axios";
import "./App.css";

export default function App() {
  /* -------------------- state -------------------- */
  const [active, setActive] = useState("text");
  const [threshold, setThreshold] = useState(0.8);
  const [resumeText, setResumeText] = useState("");
  const [jobText, setJobText] = useState("");
  const [resumeFiles, setResumeFiles] = useState([]);
  const [jobFile, setJobFile] = useState(null);
  const [multiResumes, setMultiResumes] = useState([]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  /* pretty-print helper */
  const pretty = (obj) => JSON.stringify(obj, null, 2);

  /* -------------- helpers to reset status -------------- */
  const reset = () => {
    setResult(null);
    setError("");
  };

  /* ------------------- API calls ------------------- */
  const handleTextMatch = async () => {
    try {
      setLoading(true);
      const { data } = await axios.post("/match-text", {
        resume_text: resumeText,
        job_text: jobText,
        threshold: Number(threshold),
      });
      setResult(data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleImageMatch = async () => {
    try {
      if (!jobFile || resumeFiles.length === 0) {
        setError("Please choose both resume and job images.");
        return;
      }
      setLoading(true);
      const fd = new FormData();
      fd.append("resume_file", resumeFiles[0]);
      fd.append("job_file", jobFile);
      fd.append("threshold", threshold);
      const { data } = await axios.post("/match-image", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResult(data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleMultiTextMatch = async () => {
    try {
      setLoading(true);
      const { data } = await axios.post("/match-text-multiple", {
        resume_texts: multiResumes,
        job_text: jobText,
        threshold: Number(threshold),
      });
      setResult(data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleMultiImageMatch = async () => {
    try {
      if (!jobFile || resumeFiles.length === 0) {
        setError("Pick at least one resume image and one job image.");
        return;
      }
      setLoading(true);
      const fd = new FormData();
      resumeFiles.forEach((f) => fd.append("resume_files", f));
      fd.append("job_file", jobFile);
      fd.append("threshold", threshold);
      const { data } = await axios.post("/match-image-multiple", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResult(data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  /* ------------- automatic fade on section change ------------- */
  useEffect(() => {
    const card = document.querySelector(".panel");
    if (card) {
      card.classList.remove("fade");
      // trigger reflow so animation restarts
      void card.offsetWidth;
      card.classList.add("fade");
    }
  }, [active]);

  /* ----------------------- UI ----------------------- */
  return (
    <div className="container">
      <h1 className="title">Resume and JD Matching Service</h1>

      {/* navigation */}
      <nav className="tabs">
        {["text", "image", "multi-text", "multi-image"].map((id) => (
          <button
            key={id}
            className={`tab ${active === id ? "tab--active" : ""}`}
            onClick={() => {
              setActive(id);
              reset();
            }}
          >
            {id.replace(/-/g, " ")}
          </button>
        ))}
      </nav>

      {/* common threshold input */}
      <label className="threshold">
        Threshold&nbsp;
        <input
          type="number"
          min="0"
          max="1"
          step="0.01"
          value={threshold}
          onChange={(e) => setThreshold(e.target.value)}
        />
      </label>

      {/* ---------- panels ---------- */}
      <section className="panel fade">
        {/* TEXT → TEXT */}
        {active === "text" && (
          <>
            <textarea
              placeholder="Paste resume text…"
              value={resumeText}
              onChange={(e) => setResumeText(e.target.value)}
            />
            <textarea
              placeholder="Paste job description text…"
              value={jobText}
              onChange={(e) => setJobText(e.target.value)}
            />
            <button onClick={handleTextMatch} disabled={loading}>
              {loading ? <span className="spinner" /> : "Match text"}
            </button>
          </>
        )}

        {/* SINGLE IMAGE */}
        {active === "image" && (
          <>
            {/* RESUME IMAGE */}
            <label className="fileLabel resumeLabel">
              <span className="fileBtn">Choose <strong>RESUME</strong> image…</span>
              <input
                type="file"
                accept="image/*"
                onChange={(e) => {
                  setResumeFiles(e.target.files ? [e.target.files[0]] : []);
                }}
                hidden
              />
            </label>
            {resumeFiles.length === 1 && (
              <p className="fileName">{resumeFiles[0].name}</p>
            )}

            {/* JD IMAGE */}
            <label className="fileLabel jdLabel">
              <span className="fileBtn">Choose <strong>JD</strong> image…</span>
              <input
                type="file"
                accept="image/*"
                onChange={(e) => setJobFile(e.target.files[0])}
                hidden
              />
            </label>
            {jobFile && <p className="fileName">{jobFile.name}</p>}

            <button onClick={handleImageMatch} disabled={loading}>
              {loading ? <span className="spinner" /> : "Match image"}
            </button>
          </>
        )}


        {/* MULTI-TEXT → TEXT */}
        {active === "multi-text" && (
          <>
            <textarea
              placeholder="Paste a resume then click 'Add to list'"
              value={resumeText}
              onChange={(e) => setResumeText(e.target.value)}
            />
            <button
              onClick={() => {
                if (resumeText.trim()) {
                  setMultiResumes([...multiResumes, resumeText.trim()]);
                  setResumeText("");
                }
              }}
            >
              Add resume ({multiResumes.length})
            </button>
            <textarea
              placeholder="Job description text…"
              value={jobText}
              onChange={(e) => setJobText(e.target.value)}
            />
            <button onClick={handleMultiTextMatch} disabled={loading}>
              {loading ? <span className="spinner" /> : "Match ALL texts"}
            </button>
          </>
        )}

{active === "multi-image" && (
  <>
    {/* ---------- RESUME IMAGES ---------- */}
    <label className="fileLabel">
      <span className="fileBtn">Choose resume image(s)…</span>
      <input
        type="file"
        accept="image/*"
        multiple
        onChange={(e) => {
          // merge any new selections with previously chosen files
          const chosen = Array.from(e.target.files);
          setResumeFiles((prev) => [...prev, ...chosen]);
          e.target.value = ""; // reset so the same file can be chosen again
        }}
        hidden
      />
    </label>

    {/* show current list */}
    {resumeFiles.length > 0 && (
      <ul className="fileList">
        {resumeFiles.map((f, i) => (
          <li key={i}>{f.name}</li>
        ))}
      </ul>
    )}

    {/* ---------- JOB-DESC IMAGE ---------- */}
    <label className="fileLabel">
      <span className="fileBtn">Choose JD image…</span>
      <input
        type="file"
        accept="image/*"
        onChange={(e) => setJobFile(e.target.files[0])}
        hidden
      />
    </label>
    {jobFile && <p className="fileName">{jobFile.name}</p>}

    <button onClick={handleMultiImageMatch} disabled={loading}>
      {loading ? <span className="spinner" /> : "Match ALL images"}
    </button>
  </>
)}

      </section>

      {/* ---------- results ---------- */}
      {error && <pre className="error">{error}</pre>}
      {result && (
        <details open className="results fade">
          <summary>Result JSON</summary>
          <pre>{pretty(result)}</pre>
        </details>
      )}
    </div>
  );
}
