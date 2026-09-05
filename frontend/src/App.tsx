import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Clock3,
  FileSearch,
  ImagePlus,
  Loader2,
  PackageSearch,
  RefreshCw,
  ScanLine,
  ShieldCheck,
  Sparkles,
  Upload,
  X,
  Zap,
} from "lucide-react";

const API_URL = "http://127.0.0.1:8000";
const MAX_IMAGES = 6;
const MAX_SIZE = 15 * 1024 * 1024;

type BackendDeclaration = {
  field?: string;
  value?: string | null;
  confidence?: number;
  evidence?: string[];
};

type AIResult = {
  product?: {
    name?: string | null;
    brand?: string | null;
    category?: string | null;
  };
  declarations?: BackendDeclaration[];
  country_of_origin?: string | null;
  label_type?: string | null;
  ambiguities?: string[];
};

type ComplianceIssue = {
  rule?: string;
  field?: string;
  status?: string;
  reason?: string;
};

type ComplianceResult = {
  status?: string;
  score?: number;
  passed?: number;
  failed?: number;
  review?: number;
  issues?: ComplianceIssue[];
};

type InspectionResponse = {
  success?: boolean;
  images_processed?: number;
  ocr_text?: string;
  ai?: AIResult;
  compliance?: ComplianceResult;
};

type ImagePreview = {
  file: File;
  url: string;
};

const stages = [
  {
    title: "Preparing evidence",
    detail: "Uploading package images",
  },
  {
    title: "Reading the label",
    detail: "Local OCR extraction",
  },
  {
    title: "Understanding declarations",
    detail: "Cloud AI interpretation",
  },
  {
    title: "Validating evidence",
    detail: "Cross-image consistency checks",
  },
  {
    title: "Applying legal rules",
    detail: "Deterministic compliance engine",
  },
  {
    title: "Building inspection",
    detail: "Preparing evidence report",
  },
];

function confidence(value?: number) {
  if (value === undefined || value === null) return null;
  return value <= 1 ? Math.round(value * 100) : Math.round(value);
}

function prettyField(field?: string) {
  if (!field) return "Declaration";

  return field
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function statusInfo(status?: string) {
  const normalized = String(status || "").toUpperCase();

  if (
    normalized === "COMPLIANT" ||
    normalized === "PASS" ||
    normalized === "PASSED"
  ) {
    return {
      label: "COMPLIANT",
      className: "good",
      icon: CheckCircle2,
      description: "No failed checks were returned.",
    };
  }

  if (
    normalized === "NON_COMPLIANT" ||
    normalized === "POTENTIAL NON-COMPLIANCE" ||
    normalized === "FAIL"
  ) {
    return {
      label: "POTENTIAL NON-COMPLIANCE",
      className: "danger",
      icon: AlertTriangle,
      description: "One or more checks require attention.",
    };
  }

  return {
    label: "REVIEW REQUIRED",
    className: "review",
    icon: CircleAlert,
    description: "Additional evidence or human review is recommended.",
  };
}

function App() {
  const [images, setImages] = useState<ImagePreview[]>([]);
  const [result, setResult] = useState<InspectionResponse | null>(null);
  const [scanning, setScanning] = useState(false);
  const [stage, setStage] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    return () => {
      images.forEach((image) => URL.revokeObjectURL(image.url));
    };
  }, [images]);

  const addFiles = useCallback((incoming: File[]) => {
    setError("");

    const valid: File[] = [];

    for (const file of incoming) {
      if (!file.type.startsWith("image/")) {
        setError("Only image files can be inspected.");
        continue;
      }

      if (file.size > MAX_SIZE) {
        setError(`${file.name} is larger than 15 MB.`);
        continue;
      }

      valid.push(file);
    }

    setImages((current) => {
      const remaining = MAX_IMAGES - current.length;

      if (remaining <= 0) {
        setError("A maximum of 6 images can be inspected at once.");
        return current;
      }

      if (valid.length > remaining) {
        setError("Only 6 images can be inspected at once.");
      }

      return [
        ...current,
        ...valid.slice(0, remaining).map((file) => ({
          file,
          url: URL.createObjectURL(file),
        })),
      ];
    });
  }, []);

  const removeImage = (index: number) => {
    setImages((current) => {
      const target = current[index];

      if (target) {
        URL.revokeObjectURL(target.url);
      }

      return current.filter((_, i) => i !== index);
    });
  };

  const inspect = async () => {
    if (!images.length) {
      setError("Add at least one product image first.");
      return;
    }

    setScanning(true);
    setResult(null);
    setError("");
    setStage(0);

    const timers = [
      window.setTimeout(() => setStage(1), 500),
      window.setTimeout(() => setStage(2), 1500),
      window.setTimeout(() => setStage(3), 2800),
      window.setTimeout(() => setStage(4), 4200),
      window.setTimeout(() => setStage(5), 5600),
    ];

    try {
      const formData = new FormData();

      images.forEach((image) => {
        formData.append("images", image.file);
      });

      const response = await fetch(`${API_URL}/api/inspection`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        let message = `Inspection failed with status ${response.status}.`;

        try {
          const body = await response.json();
          message = body.detail || body.message || message;
        } catch {
          // Keep fallback.
        }

        throw new Error(message);
      }

      const data: InspectionResponse = await response.json();

      setStage(5);
      setResult(data);
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : "Unable to complete the inspection.";

      setError(
        message.includes("Failed to fetch")
          ? "Cannot reach LegalMetrix. Make sure the FastAPI backend is running on port 8000."
          : message
      );
    } finally {
      timers.forEach((timer) => window.clearTimeout(timer));
      setScanning(false);
    }
  };

  const reset = () => {
    images.forEach((image) => URL.revokeObjectURL(image.url));
    setImages([]);
    setResult(null);
    setError("");
    setStage(0);
  };

  return (
    <div className="app">
      <div className="noise" />
      <div className="glow glow-one" />
      <div className="glow glow-two" />

      <header className="navbar">
        <div className="brand">
          <div className="brand-icon">
            <ShieldCheck size={22} />
          </div>

          <div>
            <div className="brand-title">
              LEGAL<span>METRIX</span>
            </div>
            <div className="brand-caption">
              PACKAGED COMMODITY INSPECTION
            </div>
          </div>
        </div>

        <div className="system-pill">
          <span className="status-dot" />
          SYSTEM ONLINE
        </div>
      </header>

      <main className="container">
        {!scanning && !result && (
          <>
            <section className="hero">
              <div className="hero-badge">
                <Sparkles size={14} />
                AI-ASSISTED LEGAL METROLOGY
              </div>

              <h1>
                Turn packaging
                <br />
                <span>into evidence.</span>
              </h1>

              <p>
                Inspect packaged commodity labels using OCR, cloud AI
                interpretation, evidence validation and deterministic
                compliance rules.
              </p>

              <div className="hero-stats">
                <div>
                  <strong>01</strong>
                  <span>UPLOAD</span>
                </div>
                <div className="stat-line" />
                <div>
                  <strong>02</strong>
                  <span>ANALYZE</span>
                </div>
                <div className="stat-line" />
                <div>
                  <strong>03</strong>
                  <span>VALIDATE</span>
                </div>
              </div>
            </section>

            <section className="workspace">
              <div
                className={`upload-zone ${dragging ? "dragging" : ""}`}
                onDragOver={(event) => {
                  event.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={(event) => {
                  event.preventDefault();
                  setDragging(false);
                  addFiles(Array.from(event.dataTransfer.files));
                }}
              >
                <input
                  ref={inputRef}
                  type="file"
                  accept="image/*"
                  multiple
                  hidden
                  onChange={(event) => {
                    if (event.target.files) {
                      addFiles(Array.from(event.target.files));
                    }
                    event.target.value = "";
                  }}
                />

                <div className="upload-symbol">
                  <Upload size={28} />
                </div>

                <div className="upload-copy">
                  <h2>Drop product images here</h2>
                  <p>
                    Capture the front, back, side panels, price area and
                    declaration surfaces for stronger evidence.
                  </p>
                </div>

                <button
                  className="primary-button"
                  onClick={() => inputRef.current?.click()}
                >
                  <ImagePlus size={18} />
                  Choose images
                </button>

                <div className="format-row">
                  <span>JPG</span>
                  <span>PNG</span>
                  <span>WEBP</span>
                  <span>≤ 15 MB</span>
                  <span>6 IMAGES</span>
                </div>
              </div>

              <div className="pipeline-card">
                <div className="card-label">
                  <ScanLine size={16} />
                  INSPECTION PIPELINE
                </div>

                <PipelineStep
                  number="01"
                  title="Extract"
                  text="Local OCR reads the label"
                  icon={<FileSearch size={17} />}
                />

                <PipelineStep
                  number="02"
                  title="Interpret"
                  text="Cloud AI structures declarations"
                  icon={<Sparkles size={17} />}
                />

                <PipelineStep
                  number="03"
                  title="Harden"
                  text="Evidence and image consistency"
                  icon={<RefreshCw size={17} />}
                />

                <PipelineStep
                  number="04"
                  title="Validate"
                  text="Deterministic legal checks"
                  icon={<ShieldCheck size={17} />}
                />
              </div>
            </section>

            {images.length > 0 && (
              <section className="evidence-section">
                <div className="section-header">
                  <div>
                    <div className="eyebrow-small">EVIDENCE QUEUE</div>
                    <h3>
                      {images.length} image{images.length !== 1 ? "s" : ""}{" "}
                      ready
                    </h3>
                  </div>

                  <button
                    className="ghost-button"
                    disabled={images.length >= MAX_IMAGES}
                    onClick={() => inputRef.current?.click()}
                  >
                    <ImagePlus size={16} />
                    Add more
                  </button>
                </div>

                <div className="image-grid">
                  {images.map((image, index) => (
                    <div className="image-card" key={image.url}>
                      <img
                        src={image.url}
                        alt={`Product evidence ${index + 1}`}
                      />

                      <div className="image-index">
                        EVIDENCE {String(index + 1).padStart(2, "0")}
                      </div>

                      <button
                        className="remove-image"
                        onClick={() => removeImage(index)}
                        aria-label={`Remove image ${index + 1}`}
                      >
                        <X size={15} />
                      </button>
                    </div>
                  ))}
                </div>

                <div className="action-bar">
                  <button className="ghost-button" onClick={reset}>
                    Clear
                  </button>

                  <button className="inspect-button" onClick={inspect}>
                    <Zap size={18} />
                    INSPECT PACKAGE
                    <ChevronRight size={18} />
                  </button>
                </div>
              </section>
            )}

            {error && <ErrorBox message={error} />}
          </>
        )}

        {scanning && (
          <section className="scanner-page">
            <div className="scanner-visual">
              <div className="scanner-orbit orbit-one" />
              <div className="scanner-orbit orbit-two" />
              <div className="scanner-orbit orbit-three" />

              <div className="scanner-core">
                <ShieldCheck size={40} />
              </div>
            </div>

            <div className="eyebrow-small">LEGALMETRIX ENGINE</div>
            <h2>Analyzing evidence</h2>
            <p className="scanner-subtitle">
              Reading, interpreting and validating the submitted package.
            </p>

            <div className="stage-panel">
              {stages.map((item, index) => {
                const complete = index < stage;
                const active = index === stage;

                return (
                  <div
                    className={`stage ${
                      complete ? "complete" : ""
                    } ${active ? "active" : ""}`}
                    key={item.title}
                  >
                    <div className="stage-icon">
                      {complete ? (
                        <CheckCircle2 size={17} />
                      ) : active ? (
                        <Loader2 className="spin" size={17} />
                      ) : (
                        String(index + 1).padStart(2, "0")
                      )}
                    </div>

                    <div className="stage-copy">
                      <strong>{item.title}</strong>
                      <span>{item.detail}</span>
                    </div>

                    {active && (
                      <span className="processing-label">PROCESSING</span>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {result && !scanning && (
          <Results result={result} onReset={reset} />
        )}
      </main>

      <footer className="footer">
        <span>LEGALMETRIX</span>
        <span>•</span>
        <span>Evidence-first packaged commodity screening</span>
        <span className="footer-right">
          OCR · CLOUD AI · EVIDENCE HARDENING · RULE ENGINE
        </span>
      </footer>
    </div>
  );
}

function PipelineStep({
  number,
  title,
  text,
  icon,
}: {
  number: string;
  title: string;
  text: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="pipeline-step">
      <div className="pipeline-number">{number}</div>
      <div className="pipeline-icon">{icon}</div>
      <div>
        <strong>{title}</strong>
        <span>{text}</span>
      </div>
    </div>
  );
}

function ErrorBox({ message }: { message: string }) {
  return (
    <div className="error-box">
      <AlertTriangle size={18} />
      <div>
        <strong>Inspection could not be completed</strong>
        <p>{message}</p>
      </div>
    </div>
  );
}

function Results({
  result,
  onReset,
}: {
  result: InspectionResponse;
  onReset: () => void;
}) {
  const ai = result.ai || {};
  const compliance = result.compliance || {};
  const product = ai.product || {};
  const declarations = ai.declarations || [];
  const issues = compliance.issues || [];
  const ambiguities = ai.ambiguities || [];
  const ocr = result.ocr_text || "";

  const info = statusInfo(compliance.status);
  const StatusIcon = info.icon;

  const score = compliance.score ?? 0;
  const passed = compliance.passed ?? 0;
  const failed = compliance.failed ?? 0;
  const review = compliance.review ?? 0;

  return (
    <>
      <div className="results-nav">
        <button className="back-button" onClick={onReset}>
          <ArrowLeft size={17} />
          New inspection
        </button>

        <div className="result-chip">
          <span className="status-dot" />
          INSPECTION COMPLETE
        </div>
      </div>

      <section className="result-heading">
        <div>
          <div className="eyebrow-small">INSPECTION RESULT</div>
          <h1>{product.name || product.brand || "Package inspection"}</h1>

          <p>
            Structured declarations were extracted from the submitted package
            and evaluated against the configured screening rules.
          </p>
        </div>

        <div className={`final-status ${info.className}`}>
          <StatusIcon size={25} />
          <div>
            <span>FINAL ASSESSMENT</span>
            <strong>{info.label}</strong>
          </div>
        </div>
      </section>

      <section className="score-layout">
        <div className={`score-card ${info.className}`}>
          <div
            className="score-ring"
            style={
              {
                "--score": `${Math.max(0, Math.min(100, score))}%`,
              } as React.CSSProperties
            }
          >
            <div className="score-inner">
              <strong>{score}</strong>
              <span>SCORE</span>
            </div>
          </div>

          <div className="score-copy">
            <div className="eyebrow-small">SCREENING OUTCOME</div>
            <h2>{info.label}</h2>
            <p>{info.description}</p>
          </div>
        </div>

        <div className="summary-grid">
          <SummaryCard
            value={passed}
            label="Passed"
            className="good"
            icon={<CheckCircle2 size={18} />}
          />

          <SummaryCard
            value={failed}
            label="Failed"
            className="danger"
            icon={<AlertTriangle size={18} />}
          />

          <SummaryCard
            value={review}
            label="Review"
            className="review"
            icon={<CircleAlert size={18} />}
          />

          <SummaryCard
            value={declarations.length}
            label="Declarations"
            className="neutral"
            icon={<FileSearch size={18} />}
          />
        </div>
      </section>

      <div className="result-grid">
        <div className="result-main">
          <Panel
            title="Product identity"
            icon={<PackageSearch size={17} />}
          >
            <div className="identity-grid">
              <Info label="Product" value={product.name} />
              <Info label="Brand" value={product.brand} />
              <Info label="Category" value={product.category} />
              <Info label="Label type" value={ai.label_type} />
              <Info
                label="Country of origin"
                value={ai.country_of_origin}
              />
              <Info
                label="Images processed"
                value={String(result.images_processed ?? "—")}
              />
            </div>
          </Panel>

          <Panel
            title="Declarations extracted"
            icon={<FileSearch size={17} />}
            badge={String(declarations.length)}
          >
            {declarations.length === 0 ? (
              <Empty text="No structured declarations were detected." />
            ) : (
              <div className="declaration-table">
                {declarations.map((item, index) => {
                  const conf = confidence(item.confidence);

                  return (
                    <div
                      className="declaration-item"
                      key={`${item.field}-${index}`}
                    >
                      <div className="declaration-left">
                        <span>{prettyField(item.field)}</span>
                        <strong>
                          {item.value === null ||
                          item.value === undefined ||
                          item.value === ""
                            ? "Not detected"
                            : String(item.value)}
                        </strong>

                        {item.evidence && item.evidence.length > 0 && (
                          <div className="evidence-snippet">
                            <span>EVIDENCE</span>
                            “{item.evidence[0]}”
                          </div>
                        )}
                      </div>

                      <div className="confidence-badge">
                        {conf === null ? "—" : `${conf}%`}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Panel>

          <Panel
            title="Compliance findings"
            icon={<ShieldCheck size={17} />}
            badge={String(issues.length)}
          >
            {issues.length === 0 ? (
              <Empty text="No compliance issues were returned." />
            ) : (
              <div className="issues">
                {issues.map((issue, index) => {
                  const issueStatus = String(
                    issue.status || "REVIEW"
                  ).toUpperCase();

                  const cls =
                    issueStatus.includes("FAIL") ||
                    issueStatus.includes("NON")
                      ? "danger"
                      : issueStatus.includes("PASS")
                        ? "good"
                        : "review";

                  return (
                    <div className={`issue ${cls}`} key={index}>
                      <div className="issue-top">
                        <span className="rule-badge">
                          {issue.rule || "RULE"}
                        </span>
                        <span className="issue-status">
                          {issue.status || "REVIEW"}
                        </span>
                      </div>

                      <h4>{prettyField(issue.field)}</h4>
                      <p>{issue.reason || "Additional review is required."}</p>
                    </div>
                  );
                })}
              </div>
            )}
          </Panel>

          {ambiguities.length > 0 && (
            <Panel
              title="Evidence warnings"
              icon={<CircleAlert size={17} />}
              badge={String(ambiguities.length)}
            >
              <div className="warning-list">
                {ambiguities.map((item, index) => (
                  <div className="warning-item" key={index}>
                    <CircleAlert size={16} />
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </Panel>
          )}
        </div>

        <aside className="result-side">
          <Panel
            title="Inspection overview"
            icon={<ScanLine size={17} />}
          >
            <div className="overview-stack">
              <OverviewRow
                icon={<ShieldCheck size={17} />}
                label="Decision"
                value={info.label}
              />

              <OverviewRow
                icon={<FileSearch size={17} />}
                label="Declarations"
                value={String(declarations.length)}
              />

              <OverviewRow
                icon={<CheckCircle2 size={17} />}
                label="Passed"
                value={String(passed)}
              />

              <OverviewRow
                icon={<AlertTriangle size={17} />}
                label="Failed"
                value={String(failed)}
              />

              <OverviewRow
                icon={<CircleAlert size={17} />}
                label="Review"
                value={String(review)}
              />
            </div>
          </Panel>

          <Panel
            title="OCR evidence"
            icon={<FileSearch size={17} />}
          >
            <div className="ocr-box">
              {ocr ? ocr : "No OCR text returned."}
            </div>
          </Panel>

          <div className="disclaimer">
            <ShieldCheck size={17} />
            <div>
              <strong>Screening aid</strong>
              <p>
                Results are based on submitted image evidence and the
                configured screening rules. They are not a legal certification
                or substitute for official inspection.
              </p>
            </div>
          </div>
        </aside>
      </div>

      <button className="floating-new" onClick={onReset}>
        <RefreshCw size={16} />
        NEW INSPECTION
      </button>
    </>
  );
}

function SummaryCard({
  value,
  label,
  className,
  icon,
}: {
  value: number;
  label: string;
  className: string;
  icon: React.ReactNode;
}) {
  return (
    <div className={`summary-card ${className}`}>
      <div className="summary-icon">{icon}</div>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function Panel({
  title,
  icon,
  badge,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  badge?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          {icon}
          <span>{title}</span>
        </div>

        {badge !== undefined && <b>{badge}</b>}
      </div>

      <div className="panel-body">{children}</div>
    </section>
  );
}

function Info({
  label,
  value,
}: {
  label: string;
  value?: string | null;
}) {
  return (
    <div className="info">
      <span>{label}</span>
      <strong>{value || "Not detected"}</strong>
    </div>
  );
}

function OverviewRow({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="overview-row">
      <div>
        {icon}
        <span>{label}</span>
      </div>
      <strong>{value}</strong>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return (
    <div className="empty">
      <CircleAlert size={18} />
      {text}
    </div>
  );
}

export default App;
