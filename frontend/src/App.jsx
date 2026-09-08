import { useEffect, useRef, useState } from "react";
import "./App.css";

const API_URL ="http://127.0.0.1:8000";
const MAX_IMAGES = 6;

function StatusBadge({ status }) {
  const value = String(status || "UNKNOWN");
  const normalized = value.toLowerCase().replaceAll(" ", "_");

  return (
    <span className={`status-badge status-${normalized}`}>
      <span className="status-dot" />
      {value.replaceAll("_", " ")}
    </span>
  );
}

function Metric({ label, value, type = "" }) {
  return (
    <div className="metric">
      <span className="metric-label">{label}</span>
      <strong className={`metric-value ${type}`}>{value ?? 0}</strong>
    </div>
  );
}

function SectionTitle({ number, title, subtitle }) {
  return (
    <div className="section-title">
      <div>
        <span className="section-number">{number}</span>
        <h2>{title}</h2>
      </div>
      {subtitle && <span className="section-subtitle">{subtitle}</span>}
    </div>
  );
}

function App() {
  const inputRef = useRef(null);
  const cameraRef = useRef(null);

  const [files, setFiles] = useState([]);
  const [previews, setPreviews] = useState([]);

  const [dragging, setDragging] = useState(false);
  const [scanning, setScanning] = useState(false);

  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const [activeTab, setActiveTab] = useState("compliance");

  const [cameraOpen, setCameraOpen] = useState(false);
  const [cameraStream, setCameraStream] = useState(null);

  useEffect(() => {
    return () => {
      previews.forEach((url) => URL.revokeObjectURL(url));

      if (cameraStream) {
        cameraStream.getTracks().forEach((track) => track.stop());
      }
    };
  }, [previews, cameraStream]);

  function addFiles(selectedFiles) {
    const incoming = Array.from(selectedFiles || [])
      .filter((file) => file.type.startsWith("image/"));

    if (!incoming.length) {
      setError("Please select PNG, JPG, JPEG or WEBP images.");
      return;
    }

    const combined = [...files, ...incoming].slice(0, MAX_IMAGES);

    previews.forEach((url) => URL.revokeObjectURL(url));

    setFiles(combined);
    setPreviews(combined.map((file) => URL.createObjectURL(file)));

    setResult(null);
    setError("");
  }

  function replaceFiles(selectedFiles) {
    const incoming = Array.from(selectedFiles || [])
      .filter((file) => file.type.startsWith("image/"))
      .slice(0, MAX_IMAGES);

    if (!incoming.length) {
      setError("Please select a valid image file.");
      return;
    }

    previews.forEach((url) => URL.revokeObjectURL(url));

    setFiles(incoming);
    setPreviews(incoming.map((file) => URL.createObjectURL(file)));

    setResult(null);
    setError("");
  }

  function removeFile(index) {
    const next = files.filter((_, i) => i !== index);

    previews.forEach((url) => URL.revokeObjectURL(url));

    setFiles(next);
    setPreviews(next.map((file) => URL.createObjectURL(file)));

    setResult(null);
  }

  function onDrop(event) {
    event.preventDefault();
    setDragging(false);
    addFiles(event.dataTransfer.files);
  }

  async function openCamera() {
    setError("");

    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Camera access is not supported by this browser.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
        audio: false,
      });

      setCameraStream(stream);
      setCameraOpen(true);
    } catch (err) {
      setError(
        "Camera access was blocked. Allow camera permission and try again."
      );
    }
  }

  function closeCamera() {
    if (cameraStream) {
      cameraStream.getTracks().forEach((track) => track.stop());
    }

    setCameraStream(null);
    setCameraOpen(false);
  }

  function captureCameraImage() {
    const video = document.getElementById("camera-video");

    if (!video || video.readyState < 2) {
      setError("Camera is not ready yet.");
      return;
    }

    const canvas = document.createElement("canvas");

    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;

    const ctx = canvas.getContext("2d");

    if (!ctx) {
      setError("Could not capture camera frame.");
      return;
    }

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(
      (blob) => {
        if (!blob) {
          setError("Could not create image from camera.");
          return;
        }

        const file = new File(
          [blob],
          `camera-label-${Date.now()}.jpg`,
          { type: "image/jpeg" }
        );

        addFiles([file]);
        closeCamera();
      },
      "image/jpeg",
      0.92
    );
  }

  async function runInspection() {
    if (!files.length) {
      setError("Upload or capture at least one product-label image.");
      return;
    }

    setScanning(true);
    setResult(null);
    setError("");
    setActiveTab("compliance");

    try {
      const formData = new FormData();

      files.forEach((file) => {
        formData.append("files", file);
      });

      const controller = new AbortController();

      const timeout = setTimeout(() => {
        controller.abort();
      }, 120000);

      let response;

      try {
        response = await fetch(`${API_URL}/api/inspection`, {
          method: "POST",
          body: formData,
          signal: controller.signal,
        });
      } finally {
        clearTimeout(timeout);
      }

      let data = null;

      try {
        data = await response.json();
      } catch {
        throw new Error(
          `Backend returned an invalid response (${response.status}).`
        );
      }

      if (!response.ok) {
        let detail = data?.detail;

        if (Array.isArray(detail)) {
          detail = detail
            .map((item) => {
              const location = item?.loc?.join(".") || "request";
              return `${location}: ${item?.msg || "validation error"}`;
            })
            .join(" | ");
        }

        throw new Error(
          detail ||
            `Inspection failed with HTTP ${response.status}.`
        );
      }

      if (!data?.success) {
        throw new Error(
          data?.detail ||
            "The backend completed the request but did not return a successful inspection."
        );
      }

      setResult(data);
    } catch (err) {
      if (err?.name === "AbortError") {
        setError(
          "Inspection timed out after 120 seconds. The OCR/AI pipeline may still be processing."
        );
      } else if (err instanceof TypeError) {
        setError(
          `Cannot connect to LegalMetrix at ${API_URL}. Check that the backend is running on port 8000.`
        );
      } else {
        setError(err?.message || "Inspection failed.");
      }
    } finally {
      setScanning(false);
    }
  }

  function reset() {
    previews.forEach((url) => URL.revokeObjectURL(url));

    setFiles([]);
    setPreviews([]);
    setResult(null);
    setError("");
    setScanning(false);
    setActiveTab("compliance");
  }

  const compliance = result?.compliance;
  const ai = result?.ai;

  return (
    <div className="app">

      {/* ======================================================
          NAVIGATION
      ====================================================== */}

      <header className="nav">
        <div className="brand">
          <div className="brand-mark">L</div>

          <div>
            <div className="brand-name">LEGALMETRIX</div>
            <div className="brand-sub">
              PACKAGED COMMODITY INTELLIGENCE
            </div>
          </div>
        </div>

        <div className="nav-status">
          <span className="live" />
          LOCAL ENGINE
          <span className="nav-divider" />
          AI + RULES
        </div>
      </header>


      {/* ======================================================
          MAIN
      ====================================================== */}

      <main>

        {/* HERO */}

        <section className="hero">
          <div className="hero-eyebrow">
            <span />
            AI-ASSISTED LEGAL METROLOGY SCREENING
          </div>

          <h1>
            Turn packaging
            <br />
            into <em>evidence.</em>
          </h1>

          <p>
            Scan product labels, extract declarations with OCR,
            interpret the label using cloud AI, then validate the
            detected information against deterministic compliance rules.
          </p>

          <div className="hero-pipeline">
            <span>01 OCR</span>
            <i>&#8594;</i>
            <span>02 AI INTERPRETATION</span>
            <i>&#8594;</i>
            <span>03 RULE VALIDATION</span>
            <i>&#8594;</i>
            <span>04 REPORT</span>
          </div>
        </section>


        {/* WORKSPACE */}

        <section className="workspace">

          {/* INPUT PANEL */}

          <div className="card input-card">

            <SectionTitle
              number="01"
              title="Label input"
              subtitle={`${files.length}/${MAX_IMAGES} IMAGES`}
            />

            {!files.length ? (
              <div
                className={`dropzone ${dragging ? "dragging" : ""}`}
                onDragOver={(event) => {
                  event.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                onClick={() => inputRef.current?.click()}
              >
                <input
                  ref={inputRef}
                  type="file"
                  accept="image/png,image/jpeg,image/jpg,image/webp"
                  multiple
                  onChange={(event) => replaceFiles(event.target.files)}
                />

                <div className="drop-icon">
                  <div className="corner top-left" />
                  <div className="corner top-right" />
                  <div className="corner bottom-left" />
                  <div className="corner bottom-right" />
                  <span>&#8593;</span>
                </div>

                <h3>Upload product imagery</h3>

                <p>
                  Drag & drop your label images here
                  <br />
                  or click to browse
                </p>

                <small>JPG &#183; PNG &#183; WEBP &#183; UP TO 6 IMAGES</small>
              </div>
            ) : (
              <div className="preview-area">

                <div className="preview-grid">
                  {files.map((file, index) => (
                    <div className="preview" key={`${file.name}-${index}`}>
                      <img
                        src={previews[index]}
                        alt={`Product label ${index + 1}`}
                      />

                      <div className="preview-top">
                        <span>
                          {String(index + 1).padStart(2, "0")}
                        </span>

                        <button
                          onClick={() => removeFile(index)}
                          title="Remove image"
                        >
                          &#215;
                        </button>
                      </div>

                      <div className="preview-bottom">
                        {file.name}
                      </div>
                    </div>
                  ))}

                  {files.length < MAX_IMAGES && (
                    <button
                      className="add-card"
                      onClick={() => inputRef.current?.click()}
                    >
                      <strong>+</strong>
                      ADD IMAGE
                    </button>
                  )}
                </div>

                <div className="capture-row">
                  <button
                    className="secondary-button"
                    onClick={openCamera}
                  >
                    <span>&#9678;</span>
                    CAPTURE WITH CAMERA
                  </button>

                  <button
                    className="secondary-button"
                    onClick={() => inputRef.current?.click()}
                  >
                    <span>ï¼‹</span>
                    BROWSE FILES
                  </button>
                </div>

              </div>
            )}

            {!files.length && (
              <div className="capture-row initial">
                <button
                  className="secondary-button"
                  onClick={(event) => {
                    event.stopPropagation();
                    openCamera();
                  }}
                >
                  <span>&#9678;</span>
                  TAKE PHOTO WITH CAMERA
                </button>
              </div>
            )}

            <div className="input-tip">
              <span className="tip-icon">i</span>
              <span>
                Capture the complete declaration panel in good lighting
                for stronger OCR and evidence extraction.
              </span>
            </div>

            <button
              className="run-button"
              disabled={!files.length || scanning}
              onClick={runInspection}
            >
              <span>
                {scanning ? "PROCESSING LABEL..." : "RUN INSPECTION"}
              </span>

              <strong>
                {scanning ? <span className="spinner" /> : "\u2192"}
              </strong>
            </button>

            {files.length > 0 && !scanning && (
              <button className="clear-button" onClick={reset}>
                CLEAR SESSION
              </button>
            )}

            {error && (
              <div className="error">
                <div className="error-title">
                  INSPECTION ERROR
                </div>

                <div className="error-message">
                  {error}
                </div>
              </div>
            )}

          </div>


          {/* OUTPUT PANEL */}

          <div className="card output-card">

            {!result && !scanning && (
              <div className="waiting">
                <div className="waiting-number">02</div>

                <div className="waiting-grid">
                  <span />
                  <span />
                  <span />
                  <span />
                </div>

                <div className="waiting-label">
                  ANALYSIS OUTPUT
                </div>

                <h2>Awaiting inspection</h2>

                <p>
                  Upload a product label and run an inspection
                  to generate an explainable screening report.
                </p>

                <div className="waiting-flow">
                  <span>OCR</span>
                  <i>&#8594;</i>
                  <span>AI</span>
                  <i>&#8594;</i>
                  <span>RULES</span>
                </div>
              </div>
            )}


            {scanning && (
              <div className="scanning">

                <div className="scanner">
                  <div className="scanner-corners">
                    <span />
                    <span />
                    <span />
                    <span />
                  </div>

                  <div className="scanner-line" />
                </div>

                <div className="scanning-label">
                  ANALYSIS IN PROGRESS
                </div>

                <h2>Reading your label</h2>

                <p>
                  Extracting text &#8594; interpreting declarations
                  &#8594; validating compliance
                </p>

                <div className="progress-track">
                  <div className="progress-bar" />
                </div>
              </div>
            )}


            {result && compliance && (
              <div className="results">

                <div className="result-head">
                  <SectionTitle
                    number="02"
                    title="Inspection report"
                    subtitle="DETERMINISTIC RESULT"
                  />

                  <StatusBadge status={compliance.status} />
                </div>


                {/* SCORE */}

                <div className="score-section">

                  <div
                    className="score-circle"
                    style={{
                      "--score": `${Math.max(
                        0,
                        Math.min(100, Number(compliance.score) || 0)
                      ) * 3.6}deg`,
                    }}
                  >
                    <div className="score-inner">
                      <strong>{compliance.score}</strong>
                      <span>/100</span>
                    </div>
                  </div>

                  <div className="score-copy">
                    <span>SCREENING RESULT</span>

                    <h3>
                      {compliance.status === "COMPLIANT"
                        ? "No detected failures"
                        : compliance.status ===
                            "POTENTIAL NON-COMPLIANCE"
                          ? "Potential issue detected"
                          : "Manual review recommended"}
                    </h3>

                    <p>
                      The result reflects information detected
                      from the submitted product imagery.
                    </p>
                  </div>

                </div>


                {/* METRICS */}

                <div className="metrics">
                  <Metric
                    label="PASSED"
                    value={compliance.passed}
                    type="pass"
                  />

                  <Metric
                    label="FAILED"
                    value={compliance.failed}
                    type="fail"
                  />

                  <Metric
                    label="REVIEW"
                    value={compliance.review}
                    type="review"
                  />
                </div>


                {/* TABS */}

                <div className="tabs">

                  <button
                    className={
                      activeTab === "compliance" ? "active" : ""
                    }
                    onClick={() => setActiveTab("compliance")}
                  >
                    COMPLIANCE
                  </button>

                  <button
                    className={
                      activeTab === "extraction" ? "active" : ""
                    }
                    onClick={() => setActiveTab("extraction")}
                  >
                    AI EXTRACTION
                  </button>

                  <button
                    className={
                      activeTab === "ocr" ? "active" : ""
                    }
                    onClick={() => setActiveTab("ocr")}
                  >
                    OCR TEXT
                  </button>

                </div>


                {/* COMPLIANCE */}

                {activeTab === "compliance" && (
                  <div className="findings">

                    {compliance.issues?.length ? (
                      compliance.issues.map((issue, index) => (
                        <div className="finding" key={index}>

                          <div
                            className={`finding-status finding-${String(
                              issue.status || ""
                            ).toLowerCase()}`}
                          >
                            {issue.status === "PASS"
                              ? "\u2713"
                              : issue.status === "FAIL"
                                ? "\u00D7"
                                : "!"}
                          </div>

                          <div className="finding-body">

                            <div className="finding-head">
                              <strong>
                                {String(issue.field || "")
                                  .replaceAll("_", " ")}
                              </strong>

                              <span>{issue.rule}</span>
                            </div>

                            <p>{issue.reason}</p>

                          </div>

                        </div>
                      ))
                    ) : (
                      <div className="empty-findings">
                        No compliance findings were returned.
                      </div>
                    )}

                  </div>
                )}


                {/* AI EXTRACTION */}

                {activeTab === "extraction" && (
                  <div className="extraction">

                    <div className="product-grid">

                      <div>
                        <span>PRODUCT</span>
                        <strong>
                          {ai?.product?.name || "Not detected"}
                        </strong>
                      </div>

                      <div>
                        <span>BRAND</span>
                        <strong>
                          {ai?.product?.brand || "Not detected"}
                        </strong>
                      </div>

                      <div>
                        <span>CATEGORY</span>
                        <strong>
                          {ai?.product?.category || "Not detected"}
                        </strong>
                      </div>

                      <div>
                        <span>COUNTRY OF ORIGIN</span>
                        <strong>
                          {ai?.country_of_origin || "Not detected"}
                        </strong>
                      </div>

                    </div>


                    <div className="declarations">

                      {ai?.declarations?.length ? (
                        ai.declarations.map((item, index) => (
                          <div
                            className="declaration"
                            key={`${item.field}-${index}`}
                          >
                            <div>
                              <span>
                                {String(item.field || "")
                                  .replaceAll("_", " ")}
                              </span>

                              <strong>
                                {item.value || "Not detected"}
                              </strong>
                            </div>

                            <div className="confidence">
                              {Math.round(
                                (Number(item.confidence) || 0) * 100
                              )}
                              %
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="empty-findings">
                          No declarations were extracted.
                        </div>
                      )}

                    </div>


                    {ai?.ambiguities?.length > 0 && (
                      <div className="ambiguities">
                        <div className="ambiguity-title">
                          REVIEW FLAGS
                        </div>

                        {ai.ambiguities.map((item, index) => (
                          <div key={index}>
                            <span>!</span>
                            {item}
                          </div>
                        ))}
                      </div>
                    )}

                  </div>
                )}


                {/* OCR */}

                {activeTab === "ocr" && (
                  <div className="ocr">

                    <div className="ocr-head">
                      <span>RAW OCR OUTPUT</span>
                      <span>
                        {result.ocr_text?.length || 0} CHARACTERS
                      </span>
                    </div>

                    <pre>
                      {result.ocr_text ||
                        "No OCR text available."}
                    </pre>

                  </div>
                )}

              </div>
            )}

          </div>

        </section>


        {/* ARCHITECTURE */}

        <section className="architecture">

          <div className="architecture-head">
            <span>PROCESSING PIPELINE</span>
            <span>LEGALMETRIX ENGINE</span>
          </div>

          <div className="architecture-grid">

            <div className="architecture-step">
              <b>01</b>
              <div>
                <strong>OCR</strong>
                <span>PaddleOCR</span>
              </div>
            </div>

            <div className="architecture-arrow">&#8594;</div>

            <div className="architecture-step">
              <b>02</b>
              <div>
                <strong>INTERPRET</strong>
                <span>Groq Cloud AI</span>
              </div>
            </div>

            <div className="architecture-arrow">&#8594;</div>

            <div className="architecture-step">
              <b>03</b>
              <div>
                <strong>HARDEN</strong>
                <span>Evidence validation</span>
              </div>
            </div>

            <div className="architecture-arrow">&#8594;</div>

            <div className="architecture-step">
              <b>04</b>
              <div>
                <strong>VALIDATE</strong>
                <span>Deterministic rules</span>
              </div>
            </div>

            <div className="architecture-arrow">&#8594;</div>

            <div className="architecture-step">
              <b>05</b>
              <div>
                <strong>REPORT</strong>
                <span>Explainable findings</span>
              </div>
            </div>

          </div>

        </section>


        <div className="disclaimer">
          SCREENING TOOL &#183; RESULTS ARE BASED ON DETECTED LABEL INFORMATION
          AND SHOULD BE REVIEWED BY AN APPROPRIATE AUTHORITY.
        </div>

      </main>


      {/* FOOTER */}

      <footer>
        <span>LEGALMETRIX</span>
        <span>PACKAGED COMMODITY SCREENING</span>
        <span>2026</span>
      </footer>


      {/* CAMERA MODAL */}

      {cameraOpen && (
        <div className="camera-overlay">

          <div className="camera-modal">

            <div className="camera-head">
              <div>
                <span>CAMERA CAPTURE</span>
                <strong>Capture product label</strong>
              </div>

              <button onClick={closeCamera}>&#215;</button>
            </div>

            <div className="camera-view">
              <video
                id="camera-video"
                ref={cameraRef}
                autoPlay
                playsInline
                muted
                onLoadedMetadata={(event) => {
                  event.currentTarget.play().catch(() => {});
                }}
                srcObject={undefined}
              />

              {cameraStream && (
                <CameraStream stream={cameraStream} />
              )}

              <div className="camera-frame">
                <span />
                <span />
                <span />
                <span />
              </div>
            </div>

            <div className="camera-controls">
              <button
                className="secondary-button"
                onClick={closeCamera}
              >
                CANCEL
              </button>

              <button
                className="capture-button"
                onClick={captureCameraImage}
              >
                CAPTURE
              </button>
            </div>

          </div>

        </div>
      )}

    </div>
  );
}

function CameraStream({ stream }) {
  useEffect(() => {
    const video = document.getElementById("camera-video");

    if (!video) return;

    video.srcObject = stream;

    video.play().catch(() => {});

    return () => {
      video.srcObject = null;
    };
  }, [stream]);

  return null;
}

export default App;