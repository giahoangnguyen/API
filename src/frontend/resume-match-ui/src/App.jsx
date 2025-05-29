/* src/App.jsx */
import { useState, useEffect } from "react";
import axios from "axios";
import "./App.css";

/* ---------- animated background component ---------- */
function AnimatedBG() {
  return (
    <div className="bg-wrap">
      <span className="blob blob-1" />
      <span className="blob blob-2" />
      <span className="blob blob-3" />
    </div>
  );
}

export default function App() {
  /* ---------- stage & UI state ---------- */
  const [stage, setStage] = useState("welcome");           // welcome | main
  const [active, setActive] = useState("Text");            // active tab
  const [threshold, setThreshold] = useState(0.8);

  /* ---------- matching payload state ---------- */
  const [resumeText, setResumeText] = useState("");
  const [jobText, setJobText]       = useState("");
  const [resumeFiles, setResumeFiles] = useState([]);
  const [jobFile, setJobFile]         = useState(null);
  const [multiResumes, setMultiResumes] = useState([]);

  /* ---------- result & UX flags ---------- */
  const [result, setResult]   = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState("");

  const pretty = (o) => JSON.stringify(o, null, 2);
  const reset  = () => { setResult(null); setError(""); };

  /* ---------- drag helpers ---------- */
  const stopDefaults = (e) => { e.preventDefault(); e.stopPropagation(); };
  const handleDrop = (e, single=false, isResume=true) => {
    stopDefaults(e);
    const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith("image/"));
    if(!files.length) return;
    if(single){
      isResume ? setResumeFiles([files[0]]) : setJobFile(files[0]);
    } else {
      setResumeFiles(prev => [...prev, ...files]);
    }
  };

  /* ---------- API CALLS ---------- */
  const handleTextMatch = async () => {
    try {
      setLoading(true);
      const { data } = await axios.post("/match-text", {
        resume_text: resumeText,
        job_text:    jobText,
        threshold:   Number(threshold),
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
        setError("Please choose both resume and JD images.");
        return;
      }
      setLoading(true);
      const fd = new FormData();
      fd.append("resume_file", resumeFiles[0]);
      fd.append("job_file",    jobFile);
      fd.append("threshold",   threshold);
      const { data } = await axios.post("/match-image", fd, {
        headers: { "Content-Type": "multipart/form-data" }
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
      if (multiResumes.length === 0) {
        setError("Add at least one resume text.");
        return;
      }
      setLoading(true);
      const { data } = await axios.post("/match-text-multiple", {
        resume_texts: multiResumes,
        job_text:     jobText,
        threshold:    Number(threshold),
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
        setError("Pick at least one resume image and one JD image.");
        return;
      }
      setLoading(true);
      const fd = new FormData();
      resumeFiles.forEach(f => fd.append("resume_files", f));
      fd.append("job_file",  jobFile);
      fd.append("threshold", threshold);
      const { data } = await axios.post("/match-image-multiple", fd, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      setResult(data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  /* ---------- panel fade re-trigger ---------- */
  useEffect(() => {
    const card = document.querySelector(".panel");
    if (card) { card.classList.remove("fade"); void card.offsetWidth; card.classList.add("fade"); }
  }, [active]);

  /* ---------- tiny file list ---------- */
  const FileDisplay = ({ files, onRemove }) => (
    <ul className="fileList">
      {files.map((f, i) => (
        <li key={i}>
          {f.name}
          <button className="removeBtn" onClick={() => onRemove(i)}>✕</button>
        </li>
      ))}
    </ul>
  );

  /* ---------- WELCOME SCREEN ---------- */
  if (stage === "welcome") {
    return (
      <>
        <AnimatedBG />
        <div className="welcome">
          <h1 className="welcome__title">
            <span>ATS Resume Matcher</span> – get your CV close to&nbsp;
            <span className="dream">JDreams</span>
          </h1>
          <p className="welcome__tag">
            Our service is the bridge that brings every resume to its ideal job description instantly!
          </p>
          <button className="welcome__btn" onClick={() => setStage("main")}>
            Get Started
          </button>
        </div>
      </>
    );
  }

  /* ---------- MAIN UI ---------- */
  return (
    <>
      <AnimatedBG />
      <div className="container">
        <h1 className="title">ATS Resume Checker</h1>

        {/* navigation */}
        <nav className="tabs">
          {["Text","Image","Multi-Text","Multi-Image"].map(id => (
            <button key={id}
              className={`tab ${active===id ? "tab--active":""}`}
              onClick={() => { setActive(id); reset(); }}>
              {id.replace(/-/g," ")}
            </button>
          ))}
        </nav>

        {/* threshold input */}
        <label className="threshold">
          Threshold&nbsp;
          <input type="number" min="0" max="1" step="0.01"
                 value={threshold} onChange={e=>setThreshold(e.target.value)} />
        </label>

        {/* panels */}
        <section className="panel fade">
          {/* TEXT */}
          {active==="Text" && (
            <>
              <textarea placeholder="Paste resume text…"
                        value={resumeText} onChange={e=>setResumeText(e.target.value)} />
              <textarea placeholder="Paste JD text…"
                        value={jobText} onChange={e=>setJobText(e.target.value)} />
              <button onClick={handleTextMatch} disabled={loading}>
                {loading ? <span className="spinner" /> : "Match text"}
              </button>
            </>
          )}

          {/* SINGLE IMAGE */}
          {active==="Image" && (
            <>
              <div className="dropZone" onDragOver={stopDefaults}
                   onDrop={e=>handleDrop(e,true,true)}>
                <p>📄 Drop or Browse <strong>RESUME</strong> image here</p>
                <input type="file" accept="image/*"
                       onChange={e=>setResumeFiles(e.target.files?[e.target.files[0]]:[])} />
              </div>
              {resumeFiles.length===1 &&
                <FileDisplay files={resumeFiles} onRemove={()=>setResumeFiles([])} />
              }

              <div className="dropZone jd" onDragOver={stopDefaults}
                   onDrop={e=>handleDrop(e,true,false)}>
                <p>📝 Drop or Browse <strong>JD</strong> image here</p>
                <input type="file" accept="image/*"
                       onChange={e=>setJobFile(e.target.files[0])} />
              </div>
              {jobFile && <p className="fileName">{jobFile.name}</p>}

              <button onClick={handleImageMatch} disabled={loading}>
                {loading ? <span className="spinner" /> : "Match image"}
              </button>
            </>
          )}

          {/* MULTI TEXT */}
          {active==="Multi-Text" && (
            <>
              <textarea placeholder="Paste resume then Add…"
                        value={resumeText} onChange={e=>setResumeText(e.target.value)} />
              <button onClick={()=>{
                if(resumeText.trim()){
                  setMultiResumes([...multiResumes,resumeText.trim()]);
                  setResumeText("");
                }
              }}>
                Add ({multiResumes.length})
              </button>
              <textarea placeholder="JD text…"
                        value={jobText} onChange={e=>setJobText(e.target.value)} />
              <button onClick={handleMultiTextMatch} disabled={loading}>
                {loading ? <span className="spinner" /> : "Match ALL"}
              </button>
            </>
          )}

          {/* MULTI IMAGE */}
          {active==="Multi-Image" && (
            <>
              <div className="dropZone" onDragOver={stopDefaults}
                   onDrop={e=>handleDrop(e,false,true)}>
                <p>📄 Drop or Browse <strong>RESUME image(s)</strong></p>
                <input type="file" accept="image/*" multiple
                       onChange={e=>setResumeFiles(prev=>[...prev,...e.target.files])} />
              </div>
              {resumeFiles.length>0 &&
                <FileDisplay files={resumeFiles}
                             onRemove={i=>setResumeFiles(resumeFiles.filter((_,idx)=>idx!==i))} />
              }

              <div className="dropZone jd" onDragOver={stopDefaults}
                   onDrop={e=>handleDrop(e,true,false)}>
                <p>📝 Drop or Browse <strong>JD</strong> image</p>
                <input type="file" accept="image/*"
                       onChange={e=>setJobFile(e.target.files[0])} />
              </div>
              {jobFile && <p className="fileName">{jobFile.name}</p>}

              <button onClick={handleMultiImageMatch} disabled={loading}>
                {loading ? <span className="spinner" /> : "Match ALL"}
              </button>
            </>
          )}
        </section>

        {error && <pre className="error">{error}</pre>}
        {result && (
          <details open className="results fade">
            <summary>Result JSON</summary>
            <pre>{pretty(result)}</pre>
          </details>
        )}
      </div>
    </>
  );
}

