"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  BookOpen,
  Search,
  FileText,
  ListChecks,
  Settings,
  Plus,
  ArrowUpRight,
  ArrowLeft,
  RefreshCw,
  Upload,
  X,
  Check,
  CheckCheck,
  AlertCircle,
  ChevronRight,
  Sun,
  Moon,
  LogOut,
  Feather,
  Sparkles,
  Download,
  History,
  PanelLeftClose,
  Menu,
  Loader2,
  Quote,
  CircleHelp,
  ChevronDown,
  ShieldCheck,
  Layers,
  MoreHorizontal,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import type {
  Notebook,
  Detail,
  Page,
  DocItem,
  DocDetail,
  Job,
  Status,
  SearchResult,
  Insight,
  Audit,
  Content,
} from "@/lib/types";

type View =
  "notebooks" | "documents" | "insights" | "activity" | "settings" | "search";
const labels: Record<View, string> = {
  notebooks: "Notebooks",
  documents: "Documents",
  insights: "Actions & insights",
  activity: "Activity",
  settings: "Settings",
  search: "Search your knowledge",
};
const kinds = [
  { value: "meeting_minutes", label: "Meeting minutes" },
  { value: "brief", label: "Executive brief" },
  { value: "report", label: "Structured report" },
  { value: "action_plan", label: "Action plan" },
];
const readable = (s: string) => s.replaceAll("_", " ");
const date = (s: string) =>
  new Date(
    s.endsWith("Z") || /[+-]\d\d:\d\d$/.test(s) ? s : `${s}Z`,
  ).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
function Tag({
  children,
  tone = "",
}: {
  children: React.ReactNode;
  tone?: string;
}) {
  return <span className={`tag ${tone}`}>{children}</span>;
}
function Empty({
  icon: Icon = BookOpen,
  title,
  text,
  action,
}: {
  icon?: typeof BookOpen;
  title: string;
  text: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Icon size={30} strokeWidth={1.4} />
      </div>
      <h2>{title}</h2>
      <p>{text}</p>
      {action}
    </div>
  );
}
function Busy({ text = "Loading your workspace…" }: { text?: string }) {
  return (
    <div className="busy">
      <Loader2 size={20} className="spin" />
      {text}
    </div>
  );
}

export default function Home() {
  const [auth, setAuth] = useState<boolean | null>(null),
    [password, setPassword] = useState(""),
    [loggingIn, setLoggingIn] = useState(false);
  const [view, setView] = useState<View>("notebooks"),
    [dark, setDark] = useState(false),
    [mobile, setMobile] = useState(false);
  const [notebooks, setNotebooks] = useState<Notebook[]>([]),
    [docs, setDocs] = useState<DocItem[]>([]),
    [jobs, setJobs] = useState<Job[]>([]),
    [status, setStatus] = useState<Status | null>(null);
  const [insights, setInsights] = useState<Insight[]>([]),
    [audit, setAudit] = useState<Audit[]>([]);
  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [loading, setLoading] = useState(true),
    [mutation, setMutation] = useState(false);
  const [filter, setFilter] = useState("All notebooks"),
    [localSearch, setLocalSearch] = useState(""),
    [searchQuery, setSearchQuery] = useState(""),
    [results, setResults] = useState<SearchResult[]>([]),
    [searching, setSearching] = useState(false),
    [hasSearched, setHasSearched] = useState(false);
  const [detail, setDetail] = useState<Detail | null>(null),
    [selectedPage, setSelectedPage] = useState<string | null>(null),
    [detailLoading, setDetailLoading] = useState(false),
    [detailTab, setDetailTab] = useState("transcript");
  const [doc, setDoc] = useState<DocDetail | null>(null),
    [draft, setDraft] = useState<Content | null>(null),
    [editing, setEditing] = useState(false),
    [docHistory, setDocHistory] = useState(false),
    [reviewed, setReviewed] = useState(false);
  const [documentKind, setDocumentKind] = useState("meeting_minutes");
  const [source, setSource] = useState<{
    pageId: string;
    quote?: string;
  } | null>(null);
  const [reviewNote, setReviewNote] = useState("");
  const importDialog = useRef<HTMLDialogElement>(null),
    sourceDialog = useRef<HTMLDialogElement>(null),
    fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null),
    [uploading, setUploading] = useState(false);
  const sourcePage =
    detail?.pages.find((p) => p.id === selectedPage) || detail?.pages[0];
  const activeJobs = jobs.filter(
    (j) => j.status === "queued" || j.status === "running",
  );
  const filters = [
    "All notebooks",
    "Meeting",
    "Planning",
    "Research",
    "Ideas",
    "Personal",
    "Other",
  ];
  const fail = useCallback((e: unknown) => {
    if (e instanceof ApiError && e.status === 401) {
      setAuth(false);
      setPassword("");
    } else
      setError(
        e instanceof Error
          ? e.message
          : "Something went wrong. Please try again.",
      );
  }, []);

  useEffect(() => {
    const theme = localStorage.getItem("noteforge-theme");
    setDark(
      theme === "dark" ||
        (!theme && window.matchMedia("(prefers-color-scheme: dark)").matches),
    );
    api("/auth/me")
      .then(() => setAuth(true))
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) setAuth(false);
        else {
          setAuth(false);
          setError(
            "Unable to reach the NoteForge API. Check the server connection.",
          );
        }
      });
  }, []);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);
  const refresh = useCallback(async () => {
    try {
      const [n, d, j, s] = await Promise.all([
        api<Notebook[]>("/notebooks"),
        api<DocItem[]>("/documents"),
        api<Job[]>("/jobs"),
        api<Status>("/status"),
      ]);
      setNotebooks(n);
      setDocs(d);
      setJobs(j);
      setStatus(s);
    } catch (e) {
      fail(e);
    } finally {
      setLoading(false);
    }
  }, [fail]);
  useEffect(() => {
    if (!auth) return;
    refresh();
    const interval = setInterval(refresh, 6000);
    return () => clearInterval(interval);
  }, [auth, refresh]);
  useEffect(() => {
    if (auth && view === "insights")
      api<Insight[]>("/insights").then(setInsights).catch(fail);
    if (auth && view === "activity")
      api<Audit[]>("/audit").then(setAudit).catch(fail);
  }, [auth, view, jobs, fail]);
  useEffect(() => {
    if (
      !auth ||
      !detail ||
      ["ready", "failed"].includes(detail.revision.status)
    )
      return;
    const timer = setInterval(
      () =>
        api<Detail>(`/notebooks/${detail.id}?revision_id=${detail.revision.id}`)
          .then(setDetail)
          .catch(fail),
      4000,
    );
    return () => clearInterval(timer);
  }, [auth, detail, fail]);
  useEffect(() => {
    setReviewNote(sourcePage?.review_note || "");
  }, [sourcePage?.id, sourcePage?.review_note]);
  useEffect(() => {
    if (source) sourceDialog.current?.showModal();
  }, [source]);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 5000);
    return () => clearTimeout(timer);
  }, [notice]);
  function navigate(next: View) {
    setView(next);
    setDetail(null);
    setDoc(null);
    setEditing(false);
    setMobile(false);
    setError("");
  }
  async function signIn(e: React.FormEvent) {
    e.preventDefault();
    setLoggingIn(true);
    setError("");
    try {
      await api("/auth/login", {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      setPassword("");
      setAuth(true);
      setLoading(true);
    } catch (e) {
      fail(e);
    } finally {
      setLoggingIn(false);
    }
  }
  async function signOut() {
    try {
      await api("/auth/logout", { method: "POST" });
      setAuth(false);
      setNotebooks([]);
      setDocs([]);
      setDetail(null);
      setDoc(null);
      setResults([]);
      setInsights([]);
    } catch (e) {
      fail(e);
    }
  }
  async function openNotebook(
    id: string,
    pageId?: string,
    revisionId?: string,
  ) {
    setDoc(null);
    setEditing(false);
    setView("notebooks");
    setDetailLoading(true);
    setSelectedPage(pageId || null);
    setError("");
    try {
      const d = await api<Detail>(
        `/notebooks/${id}${revisionId ? `?revision_id=${revisionId}` : ""}`,
      );
      setDetail(d);
      setDetailTab("transcript");
    } catch (e) {
      fail(e);
    } finally {
      setDetailLoading(false);
    }
  }
  async function openDoc(id: string) {
    setDetail(null);
    setView("documents");
    setDetailLoading(true);
    setEditing(false);
    setDocHistory(false);
    try {
      const d = await api<DocDetail>(`/documents/${id}`);
      setDoc(d);
      setDraft(d.content);
      setReviewed(d.reviewed);
    } catch (e) {
      fail(e);
    } finally {
      setDetailLoading(false);
    }
  }
  async function run(
    path: string,
    body?: unknown,
    message = "Added to the processing queue",
  ) {
    setMutation(true);
    setError("");
    try {
      await api(path, {
        method: "POST",
        body: body ? JSON.stringify(body) : undefined,
      });
      setNotice(message);
      await refresh();
    } catch (e) {
      fail(e);
    } finally {
      setMutation(false);
    }
  }
  function showImport() {
    setFile(null);
    if (fileInput.current) fileInput.current.value = "";
    importDialog.current?.showModal();
  }
  async function upload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    setError("");
    const data = new FormData();
    data.append("file", file);
    try {
      const r = await api<{ notebook_id: string }>("/notebooks/import", {
        method: "POST",
        body: data,
      });
      importDialog.current?.close();
      setNotice("Original preserved. Handwriting extraction is queued.");
      await refresh();
      await openNotebook(r.notebook_id);
    } catch (e) {
      fail(e);
    } finally {
      setUploading(false);
    }
  }
  const searchSequence = useRef(0);
  async function search(e: React.FormEvent) {
    e.preventDefault();
    if (searchQuery.trim().length < 2) return;
    const sequence = ++searchSequence.current;
    setSearching(true);
    setHasSearched(true);
    navigate("search");
    try {
      const found = await api<SearchResult[]>(
        `/search?q=${encodeURIComponent(searchQuery.trim())}`,
      );
      if (sequence === searchSequence.current) setResults(found);
    } catch (e) {
      fail(e);
    } finally {
      if (sequence === searchSequence.current) setSearching(false);
    }
  }
  async function saveDoc() {
    if (!doc || !draft) return;
    setMutation(true);
    try {
      await api(`/documents/${doc.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          expected_version: doc.version,
          content: draft,
          reviewed,
        }),
      });
      setNotice("Document saved with a new version.");
      setEditing(false);
      await openDoc(doc.id);
      await refresh();
    } catch (e) {
      fail(e);
    } finally {
      setMutation(false);
    }
  }
  async function reviewPage(state: string) {
    if (!sourcePage || !detail) return;
    setMutation(true);
    try {
      await api(`/pages/${sourcePage.id}/review`, {
        method: "PATCH",
        body: JSON.stringify({ status: state, note: reviewNote }),
      });
      setDetail(
        await api<Detail>(
          `/notebooks/${detail.id}?revision_id=${detail.revision.id}`,
        ),
      );
      setNotice("Page review saved.");
    } catch (e) {
      fail(e);
    } finally {
      setMutation(false);
    }
  }
  function editParagraph(section: number, paragraph: number, text: string) {
    if (!draft) return;
    const next = structuredClone(draft);
    next.sections[section].paragraphs[paragraph].text = text;
    setDraft(next);
    setReviewed(false);
  }

  if (auth === null)
    return (
      <main className="boot">
        <div className="brand-icon">
          <Feather size={25} />
        </div>
        <Busy />
      </main>
    );
  if (!auth)
    return (
      <main className="login-page">
        <div className="login-art">
          <div className="wordmark">
            <div className="brand-icon">
              <Feather />
            </div>
            NoteForge<span className="beta">SELF-HOSTED</span>
          </div>
          <div>
            <span className="eyebrow">GOOD IDEAS START ON PAPER</span>
            <h1>
              Your thinking.
              <br />A little more
              <br />
              <em>remarkable.</em>
            </h1>
            <p>
              Turn the notes you write into the knowledge
              <br />
              and documents you need.
            </p>
            <div className="login-proof">
              <ShieldCheck size={18} /> Your originals preserved. Every insight
              traceable.
            </div>
          </div>
          <span className="small muted">FROM INK TO INSIGHT</span>
        </div>
        <div className="login-side">
          <form onSubmit={signIn} className="login-form">
            <div className="mobile-wordmark wordmark">
              <Feather /> NoteForge
            </div>
            <span className="eyebrow">YOUR PRIVATE WORKSPACE</span>
            <h2>Welcome to NoteForge</h2>
            <p className="muted">Sign in to bring your notebooks to life.</p>
            <label htmlFor="password">Workspace password</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              autoFocus
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="Enter your password"
            />
            {error && (
              <div className="inline-error" role="alert">
                <AlertCircle size={16} />
                {error}
              </div>
            )}
            <Button disabled={loggingIn} type="submit">
              {loggingIn ? (
                <Loader2 size={17} className="spin" />
              ) : (
                <>
                  Open workspace <ArrowUpRight size={17} />
                </>
              )}
            </Button>
            <p className="login-foot">
              Your self-hosted notebook intelligence platform.
            </p>
          </form>
        </div>
      </main>
    );

  return (
    <div className="app-shell">
      {mobile && (
        <button
          className="mobile-backdrop"
          aria-label="Close navigation"
          onClick={() => setMobile(false)}
        />
      )}
      <aside className={`sidebar ${mobile ? "mobile-open" : ""}`}>
        <a
          className="wordmark"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            navigate("notebooks");
          }}
        >
          <span className="brand-icon">
            <Feather size={23} />
          </span>
          NoteForge
        </a>
        <div className="workspace-selector">
          <span className="workspace-avatar">A</span>
          <div>
            <strong>Personal workspace</strong>
            <span>My knowledge, connected</span>
          </div>
          <ChevronDown size={14} />
        </div>
        <span className="nav-label">WORKSPACE</span>
        <nav aria-label="Main navigation">
          {(
            [
              { key: "notebooks", icon: BookOpen },
              { key: "documents", icon: FileText },
              { key: "insights", icon: ListChecks },
            ] as const
          ).map(({ key, icon: Icon }) => (
            <button
              key={key}
              onClick={() => navigate(key)}
              className={`nav-item ${view === key ? "active" : ""}`}
            >
              <Icon size={19} />
              <span>{labels[key]}</span>
              {key === "notebooks" && (
                <span className="nav-count">
                  {status?.counts.notebooks || 0}
                </span>
              )}
              {key === "documents" && !!status?.counts.review && (
                <span className="nav-count">{status.counts.review}</span>
              )}
            </button>
          ))}
        </nav>
        <span className="nav-label system-label">SYSTEM</span>
        <nav aria-label="System navigation">
          {(
            [
              { key: "activity", icon: History },
              { key: "settings", icon: Settings },
            ] as const
          ).map(({ key, icon: Icon }) => (
            <button
              key={key}
              className={`nav-item ${view === key ? "active" : ""}`}
              onClick={() => navigate(key)}
            >
              <Icon size={19} />
              <span>{labels[key]}</span>
              {key === "activity" && activeJobs.length > 0 && (
                <span className="activity-dot" />
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sync-card">
            <div className="sync-card-top">
              <span
                className={`status-dot ${status?.remarkable_paired ? "online" : ""}`}
              />
              <strong>reMarkable Cloud</strong>
            </div>
            <p>
              {status?.remarkable_paired
                ? `Syncing every ${Math.round(status.sync_interval_seconds / 60)} minutes`
                : "Connect your handwritten world"}
            </p>
            <button
              onClick={() =>
                status?.remarkable_paired ? run("/sync") : navigate("settings")
              }
              disabled={mutation}
            >
              <RefreshCw size={13} />
              {status?.remarkable_paired ? "Sync now" : "Set up connection"}
              <ArrowUpRight size={13} />
            </button>
          </div>
          <div className="profile">
            <div className="profile-avatar">A</div>
            <div>
              <strong>My workspace</strong>
              <span>Private & self-hosted</span>
            </div>
            <button
              className="icon-btn"
              aria-label={dark ? "Use light theme" : "Use dark theme"}
              onClick={() => {
                localStorage.setItem(
                  "noteforge-theme",
                  dark ? "light" : "dark",
                );
                setDark(!dark);
              }}
            >
              {dark ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <button
              className="icon-btn"
              aria-label="Sign out"
              onClick={signOut}
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumbs">
            <button
              className="icon-btn mobile-menu"
              aria-label="Open navigation"
              onClick={() => setMobile(true)}
            >
              <Menu size={20} />
            </button>
            <span>Workspace</span>
            <ChevronRight size={13} />
            <strong>{labels[view]}</strong>
            {(detail || doc) && (
              <>
                <ChevronRight size={13} />
                <span className="crumb-title">
                  {detail?.title || doc?.content.title}
                </span>
              </>
            )}
          </div>
          <form className="global-search" onSubmit={search}>
            <Search size={16} />
            <input
              aria-label="Search all notes"
              placeholder="Search your notes…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <kbd>↵</kbd>
          </form>
          <div className="top-status">
            <span
              className={`status-dot ${status?.worker_online ? "online" : ""}`}
            />
            {status?.worker_online ? "Workspace online" : "Worker offline"}
          </div>
        </header>
        <main className="main-content">
          {error && (
            <div className="banner error" role="alert">
              <AlertCircle size={18} />
              <span>{error}</span>
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {!status?.ai_configured && status && view !== "settings" && (
            <div className="banner setup">
              <Sparkles size={17} />
              <span>
                One last connection: add your AI provider to start reading
                handwriting.
              </span>
              <button onClick={() => navigate("settings")}>
                Open settings <ArrowUpRight size={14} />
              </button>
            </div>
          )}
          {detailLoading ? (
            <Busy text="Opening your source…" />
          ) : detail ? (
            <>
              <button
                className="back-link"
                onClick={() => {
                  setDetail(null);
                  setSelectedPage(null);
                }}
              >
                <ArrowLeft size={15} />
                All notebooks
              </button>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">SOURCE NOTEBOOK</div>
                  <h1>{detail.title}</h1>
                  <p>
                    {detail.source === "remarkable"
                      ? "reMarkable Cloud"
                      : "Manual import"}{" "}
                    <span>·</span> {detail.pages.length} pages <span>·</span>{" "}
                    <Tag
                      tone={detail.revision.status === "ready" ? "green" : ""}
                    >
                      {detail.revision.status}
                    </Tag>
                  </p>
                </div>
                <div className="heading-actions">
                  <Button variant="outline" asChild>
                    <a href={`/api/revisions/${detail.revision.id}/original`}>
                      <Download size={16} />
                      Original
                    </a>
                  </Button>
                  <select
                    aria-label="Document type"
                    value={documentKind}
                    onChange={(e) => setDocumentKind(e.target.value)}
                  >
                    {kinds.map((k) => (
                      <option key={k.value} value={k.value}>
                        {k.label}
                      </option>
                    ))}
                  </select>
                  <Button
                    disabled={mutation || detail.revision.status !== "ready"}
                    onClick={() =>
                      run(`/revisions/${detail.revision.id}/generate`, {
                        kind: documentKind,
                      })
                    }
                  >
                    <Sparkles size={16} />
                    Generate document
                  </Button>
                </div>
              </div>
              {detail.revision.warning && (
                <div className="banner warning">
                  <AlertCircle size={17} />
                  <span>{detail.revision.warning}</span>
                </div>
              )}
              <div className="revision-bar">
                <Layers size={15} />
                <span>Source revision</span>
                <select
                  aria-label="Source revision"
                  value={detail.revision.id}
                  onChange={(e) =>
                    openNotebook(detail.id, undefined, e.target.value)
                  }
                >
                  {detail.revisions.map((r, i) => (
                    <option key={r.id} value={r.id}>
                      {date(r.created_at)} · {r.id.slice(0, 8)}{" "}
                      {r.id === detail.latest_revision_id ? "(latest)" : ""}
                    </option>
                  ))}
                </select>
                <span className="muted small">
                  Original fingerprint {detail.revision.sha256.slice(0, 12)}…
                </span>
              </div>
              {detail.pages.length === 0 ? (
                <Empty
                  icon={RefreshCw}
                  title={
                    detail.revision.status === "failed"
                      ? "This notebook needs attention"
                      : "Your notes are on their way"
                  }
                  text="The original is safely preserved. The worker will render each page and extract its content. You can follow progress in Activity."
                  action={
                    <Button
                      variant="outline"
                      onClick={() => navigate("activity")}
                    >
                      View activity <ArrowUpRight size={15} />
                    </Button>
                  }
                />
              ) : (
                <div className="notebook-reader">
                  <section className="source-panel">
                    <div className="panel-header">
                      <span>
                        <BookOpen size={17} />
                        Original page
                      </span>
                      <select
                        aria-label="Page"
                        value={sourcePage?.id}
                        onChange={(e) => setSelectedPage(e.target.value)}
                      >
                        {detail.pages.map((p) => (
                          <option key={p.id} value={p.id}>
                            Page {p.number}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="paper-preview">
                      {sourcePage && (
                        <img
                          src={`/api/pages/${sourcePage.id}/image`}
                          alt={`Original handwriting on page ${sourcePage.number}`}
                          onClick={() => setSource({ pageId: sourcePage.id })}
                        />
                      )}
                    </div>
                    <div className="source-foot">
                      <ShieldCheck size={14} />
                      Original preserved · click page to enlarge
                    </div>
                  </section>
                  <section className="extraction-panel">
                    <div className="reader-tabs">
                      {["transcript", "structure", "insights", "review"].map(
                        (t) => (
                          <button
                            className={detailTab === t ? "selected" : ""}
                            key={t}
                            onClick={() => setDetailTab(t)}
                          >
                            {t}
                          </button>
                        ),
                      )}
                    </div>
                    {!sourcePage?.extraction ? (
                      <Busy text="Waiting for handwriting extraction…" />
                    ) : (
                      <div className="extraction-content">
                        {detailTab === "transcript" && (
                          <>
                            <div className="section-kicker">
                              <Tag tone="purple">AI transcription</Tag>
                              <Tag
                                tone={
                                  sourcePage.review_status === "verified"
                                    ? "green"
                                    : ""
                                }
                              >
                                {readable(sourcePage.review_status)}
                              </Tag>
                            </div>
                            <p className="purpose">
                              <span>Likely purpose</span>
                              {sourcePage.extraction.purpose ||
                                "Not identified"}
                            </p>
                            <div className="transcript">
                              {sourcePage.extraction.transcript ||
                                "No legible content found on this page."}
                            </div>
                            {sourcePage.extraction.uncertainties.length > 0 && (
                              <div className="uncertainties">
                                <h3>
                                  <CircleHelp size={16} />
                                  Needs a closer look
                                </h3>
                                {sourcePage.extraction.uncertainties.map(
                                  (s, i) => (
                                    <p key={i}>{s}</p>
                                  ),
                                )}
                              </div>
                            )}
                            <p className="small muted">
                              AI transcription can contain errors. Verify it
                              against the source before relying on it.
                            </p>
                          </>
                        )}
                        {detailTab === "structure" && (
                          <>
                            {sourcePage.extraction.blocks.length === 0 ? (
                              <p className="muted">
                                No structured blocks extracted.
                              </p>
                            ) : (
                              sourcePage.extraction.blocks.map((b, i) => (
                                <div className="block-card" key={i}>
                                  <div>
                                    <Tag
                                      tone={
                                        b.kind === "diagram" ? "purple" : ""
                                      }
                                    >
                                      {b.kind}
                                    </Tag>
                                    {b.uncertain && (
                                      <Tag tone="amber">Uncertain</Tag>
                                    )}
                                    <span className="small muted">
                                      Model estimate{" "}
                                      {Math.round(b.confidence * 100)}%
                                    </span>
                                  </div>
                                  <p>{b.text}</p>
                                  <button
                                    className="citation"
                                    onClick={() =>
                                      setSource({
                                        pageId: sourcePage.id,
                                        quote: b.evidence_quote,
                                      })
                                    }
                                  >
                                    <Quote size={13} />
                                    {b.evidence_quote}
                                  </button>
                                </div>
                              ))
                            )}
                          </>
                        )}
                        {detailTab === "insights" && (
                          <>
                            {sourcePage.extraction.insights.length === 0 ? (
                              <p className="muted">
                                No explicit actions, decisions or questions
                                found.
                              </p>
                            ) : (
                              sourcePage.extraction.insights.map((i, index) => (
                                <InsightCard
                                  key={index}
                                  item={i}
                                  onSource={() =>
                                    setSource({
                                      pageId: sourcePage.id,
                                      quote: i.evidence_quote,
                                    })
                                  }
                                />
                              ))
                            )}
                          </>
                        )}
                        {detailTab === "review" && (
                          <div className="review-form">
                            <h2>Review this page</h2>
                            <p className="muted">
                              Compare the transcription with your original. Flag
                              any corrections for your review record.
                            </p>
                            <label htmlFor="review-note">Review notes</label>
                            <textarea
                              id="review-note"
                              rows={7}
                              value={reviewNote}
                              onChange={(e) => setReviewNote(e.target.value)}
                              placeholder="Record unclear words, corrections or missing context…"
                            />
                            <p className="small muted">
                              Review notes are preserved separately. They do not
                              overwrite the AI extraction or enter generated
                              documents.
                            </p>
                            <div className="flex-wrap">
                              <Button
                                disabled={mutation}
                                onClick={() => reviewPage("verified")}
                              >
                                <CheckCheck size={16} />
                                Mark verified
                              </Button>
                              <Button
                                variant="outline"
                                disabled={mutation}
                                onClick={() => reviewPage("needs_correction")}
                              >
                                Flag correction
                              </Button>
                              <Button
                                variant="ghost"
                                disabled={mutation}
                                onClick={() => reviewPage("unreviewed")}
                              >
                                Reset review
                              </Button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </section>
                </div>
              )}
            </>
          ) : doc ? (
            <>
              <button
                className="back-link"
                onClick={() => {
                  setDoc(null);
                  setEditing(false);
                }}
              >
                <ArrowLeft size={15} />
                All documents
              </button>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">
                    {readable(doc.kind).toUpperCase()}
                  </div>
                  <h1>{doc.content.title}</h1>
                  <p>
                    Version {doc.version} <span>·</span>{" "}
                    <Tag tone={doc.reviewed ? "green" : "amber"}>
                      {doc.reviewed ? "Reviewed" : "Draft · review required"}
                    </Tag>
                    {doc.stale && (
                      <Tag tone="amber">Newer source available</Tag>
                    )}
                  </p>
                </div>
                <div className="heading-actions">
                  <Button
                    variant="outline"
                    onClick={() => setDocHistory(!docHistory)}
                  >
                    <History size={16} />
                    History
                  </Button>
                  <Button variant="outline" asChild>
                    <a href={`/api/documents/${doc.id}/export`}>
                      <Download size={16} />
                      Export Markdown
                    </a>
                  </Button>
                  <Button
                    onClick={() => {
                      setEditing(!editing);
                      setDraft(structuredClone(doc.content));
                      setReviewed(doc.reviewed);
                    }}
                  >
                    {editing ? "Cancel editing" : "Review & edit"}
                  </Button>
                </div>
              </div>
              <div className="document-layout">
                <article className="document-paper">
                  {editing && draft ? (
                    <>
                      <label className="eyebrow" htmlFor="document-title">
                        DOCUMENT TITLE
                      </label>
                      <input
                        id="document-title"
                        className="document-title-input"
                        value={draft.title}
                        onChange={(e) => {
                          setDraft({ ...draft, title: e.target.value });
                          setReviewed(false);
                        }}
                      />
                      {draft.sections.map((s, si) => (
                        <section className="document-section" key={si}>
                          <label
                            className="small muted"
                            htmlFor={`heading-${si}`}
                          >
                            Section heading
                          </label>
                          <input
                            id={`heading-${si}`}
                            value={s.heading}
                            onChange={(e) => {
                              const next = structuredClone(draft);
                              next.sections[si].heading = e.target.value;
                              setDraft(next);
                              setReviewed(false);
                            }}
                          />
                          {s.paragraphs.map((p, pi) => (
                            <div className="edit-paragraph" key={pi}>
                              <Tag
                                tone={
                                  p.kind === "fact"
                                    ? "green"
                                    : p.kind === "interpretation"
                                      ? "purple"
                                      : "amber"
                                }
                              >
                                {p.kind === "fact" ? "Extracted fact" : p.kind}
                              </Tag>
                              <textarea
                                aria-label={`Paragraph ${pi + 1} of ${s.heading}`}
                                rows={4}
                                value={p.text}
                                onChange={(e) =>
                                  editParagraph(si, pi, e.target.value)
                                }
                              />
                              {p.citations.map((c, ci) => (
                                <button
                                  className="citation"
                                  key={ci}
                                  onClick={() =>
                                    setSource({
                                      pageId: c.page_id,
                                      quote: c.quote,
                                    })
                                  }
                                >
                                  <Quote size={13} />
                                  {c.quote}
                                </button>
                              ))}
                            </div>
                          ))}
                        </section>
                      ))}
                      <label htmlFor="missing-information" className="eyebrow">
                        MISSING INFORMATION · ONE ITEM PER LINE
                      </label>
                      <textarea
                        id="missing-information"
                        value={draft.missing_information.join("\n")}
                        rows={4}
                        onChange={(e) => {
                          setDraft({
                            ...draft,
                            missing_information: e.target.value
                              .split("\n")
                              .filter(Boolean),
                          });
                          setReviewed(false);
                        }}
                      />
                      <label className="checkbox-row">
                        <input
                          type="checkbox"
                          checked={reviewed}
                          onChange={(e) => setReviewed(e.target.checked)}
                        />
                        I have checked this document against the original notes.
                      </label>
                      <Button
                        disabled={mutation || !draft.title.trim()}
                        onClick={saveDoc}
                      >
                        {mutation ? (
                          <Loader2 size={16} className="spin" />
                        ) : (
                          <Check size={16} />
                        )}
                        Save version {doc.version + 1}
                      </Button>
                    </>
                  ) : (
                    <>
                      <div className="document-meta">
                        NOTEFORGE{" "}
                        <span>
                          {doc.reviewed
                            ? "REVIEWED DOCUMENT"
                            : "UNVERIFIED DRAFT"}
                        </span>
                      </div>
                      <h1>{doc.content.title}</h1>
                      {doc.content.sections.map((s, si) => (
                        <section className="document-section" key={si}>
                          <h2>{s.heading}</h2>
                          {s.paragraphs.map((p, pi) => (
                            <div className="document-paragraph" key={pi}>
                              <span className={`claim-label ${p.kind}`}>
                                {p.kind === "fact" ? "Extracted fact" : p.kind}
                              </span>
                              <p>{p.text}</p>
                              <div className="citations">
                                {p.citations.map((c, ci) => (
                                  <button
                                    className="citation"
                                    key={ci}
                                    onClick={() =>
                                      setSource({
                                        pageId: c.page_id,
                                        quote: c.quote,
                                      })
                                    }
                                  >
                                    <Quote size={12} />
                                    Source {ci + 1}
                                    <ArrowUpRight size={12} />
                                  </button>
                                ))}
                              </div>
                            </div>
                          ))}
                        </section>
                      ))}
                      {doc.content.missing_information.length > 0 && (
                        <div className="missing-info">
                          <h3>
                            <CircleHelp size={17} />
                            Missing information
                          </h3>
                          <ul>
                            {doc.content.missing_information.map((s, i) => (
                              <li key={i}>{s}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      <footer className="document-footer">
                        Generated from source revision{" "}
                        {doc.revision_id.slice(0, 8)} · {doc.model}
                        <br />
                        AI-generated output requires verification. A matching
                        quote is not proof that an interpretation is correct.
                      </footer>
                    </>
                  )}
                </article>
                <aside className="document-context">
                  <div className="context-card">
                    <div className="section-kicker">
                      <ShieldCheck size={19} />
                      <strong>Connected to the source</strong>
                    </div>
                    <p>
                      Every factual paragraph and interpretation links back to a
                      page in the original notebook.
                    </p>
                    <button
                      className="text-link"
                      onClick={() =>
                        openNotebook(
                          doc.notebook_id,
                          undefined,
                          doc.revision_id,
                        )
                      }
                    >
                      Open source notebook <ArrowUpRight size={15} />
                    </button>
                    <a
                      className="text-link"
                      href={`/api/documents/${doc.id}/export?format=json`}
                    >
                      Download structured JSON <Download size={14} />
                    </a>
                  </div>
                  <div className="context-card">
                    <h3>Read with confidence</h3>
                    <p>
                      <span className="legend-dot fact" />
                      Extracted facts are grounded in the notes.
                    </p>
                    <p>
                      <span className="legend-dot interpretation" />
                      Interpretations explain possible meaning.
                    </p>
                    <p>
                      <span className="legend-dot recommendation" />
                      Recommendations are AI suggestions.
                    </p>
                  </div>
                  {docHistory && (
                    <div className="context-card">
                      <h3>Version history</h3>
                      {doc.versions.map((v) => (
                        <details className="version-item" key={v.number}>
                          <summary>
                            Version {v.number}
                            <span>{date(v.created_at)}</span>
                          </summary>
                          <p>{v.reviewed ? "Reviewed" : "Draft"}</p>
                          <pre>{JSON.stringify(v.content, null, 2)}</pre>
                        </details>
                      ))}
                    </div>
                  )}
                </aside>
              </div>
            </>
          ) : view === "notebooks" ? (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">YOUR THINKING, CONNECTED</div>
                  <h1>
                    Notebooks<span className="title-dot">.</span>
                  </h1>
                  <p>
                    A home for your handwritten ideas. A starting point for what
                    comes next.
                  </p>
                </div>
                <Button onClick={showImport}>
                  <Plus size={17} />
                  Import notebook
                </Button>
              </div>
              <div className="overview-grid">
                <div className="overview-card">
                  <span className="stat-icon lavender">
                    <BookOpen size={20} />
                  </span>
                  <div>
                    <span className="stat-label">In your library</span>
                    <strong>
                      {status?.counts.notebooks ?? "—"}
                      <small>notebooks</small>
                    </strong>
                  </div>
                  <BookOpen className="stat-watermark" />
                </div>
                <div className="overview-card">
                  <span className="stat-icon mint">
                    <FileText size={20} />
                  </span>
                  <div>
                    <span className="stat-label">From ink to output</span>
                    <strong>
                      {status?.counts.documents ?? "—"}
                      <small>documents</small>
                    </strong>
                  </div>
                  <ArrowUpRight className="stat-watermark" />
                </div>
                <button
                  className="overview-card review-stat"
                  onClick={() => navigate("documents")}
                >
                  <span className="stat-icon peach">
                    <CheckCheck size={20} />
                  </span>
                  <div>
                    <span className="stat-label">Ready for your eyes</span>
                    <strong>
                      {status?.counts.review ?? "—"}
                      <small>to review</small>
                    </strong>
                  </div>
                  <ArrowUpRight size={18} className="stat-arrow" />
                </button>
              </div>
              <section className="library-section">
                <div className="section-heading">
                  <h2>
                    Your library <span>{notebooks.length}</span>
                  </h2>
                  <div className="library-tools">
                    <div className="mini-search">
                      <Search size={15} />
                      <input
                        aria-label="Filter notebooks by title"
                        value={localSearch}
                        onChange={(e) => setLocalSearch(e.target.value)}
                        placeholder="Find a notebook…"
                      />
                    </div>
                    <span className="sort-label">
                      Recently updated <ChevronDown size={14} />
                    </span>
                  </div>
                </div>
                <div className="filter-row">
                  {filters.map((f) => (
                    <button
                      key={f}
                      onClick={() => setFilter(f)}
                      className={filter === f ? "selected" : ""}
                    >
                      {f}
                    </button>
                  ))}
                </div>
                {loading ? (
                  <Busy />
                ) : notebooks.length === 0 ? (
                  <div className="first-notebook">
                    <div className="first-illustration">
                      <div className="illustrated-book">
                        <Feather size={38} strokeWidth={1} />
                        <span>
                          an idea
                          <br />
                          starts here.
                        </span>
                      </div>
                      <span className="little-spark">
                        <Sparkles size={21} />
                      </span>
                    </div>
                    <div className="first-text">
                      <span className="eyebrow">A FRESH PAGE</span>
                      <h2>Make room for your next idea.</h2>
                      <p>
                        Connect your reMarkable or import a notebook.
                        <br />
                        We’ll turn the handwriting into something you can work
                        with.
                      </p>
                      <div className="flex-wrap">
                        <Button onClick={showImport}>
                          <Upload size={16} />
                          Import your first notebook
                        </Button>
                        <Button
                          variant="ghost"
                          onClick={() => navigate("settings")}
                        >
                          Connect reMarkable <ArrowUpRight size={16} />
                        </Button>
                      </div>
                      <span className="formats">
                        PDF, PNG, JPEG and RMDOC · originals always preserved
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="notebook-grid">
                    {notebooks
                      .filter(
                        (n) =>
                          (filter === "All notebooks" ||
                            n.category === filter) &&
                          n.title
                            .toLowerCase()
                            .includes(localSearch.toLowerCase()),
                      )
                      .map((n, i) => (
                        <button
                          className="notebook-card"
                          key={n.id}
                          onClick={() => openNotebook(n.id)}
                        >
                          <div className={`notebook-cover cover-${i % 4}`}>
                            <div className="cover-top">
                              <Feather size={16} />
                              <span>
                                {n.source === "remarkable"
                                  ? "reMarkable"
                                  : "IMPORTED"}
                              </span>
                            </div>
                            <div className="cover-title">{n.title}</div>
                            <div className="cover-bottom">
                              <span>
                                NOTEFORGE / {String(i + 1).padStart(2, "0")}
                              </span>
                              <ArrowUpRight size={20} />
                            </div>
                          </div>
                          <div className="notebook-info">
                            <div>
                              <h3>{n.title}</h3>
                              <Tag
                                tone={
                                  n.status === "ready"
                                    ? "green"
                                    : n.status === "failed"
                                      ? "amber"
                                      : ""
                                }
                              >
                                {n.status === "ready"
                                  ? "Ready"
                                  : n.status === "failed"
                                    ? "Needs attention"
                                    : "Processing"}
                              </Tag>
                            </div>
                            <p>
                              {n.pages} {n.pages === 1 ? "page" : "pages"}
                              <span>·</span>
                              {date(n.updated_at)}
                            </p>
                            <span className="category-label">{n.category}</span>
                          </div>
                        </button>
                      ))}
                    <button className="import-tile" onClick={showImport}>
                      <span>
                        <Plus size={24} />
                      </span>
                      <strong>A little more thinking?</strong>
                      <p>Import another notebook</p>
                    </button>
                  </div>
                )}
                {notebooks.length > 0 &&
                  !notebooks.some(
                    (n) =>
                      (filter === "All notebooks" || n.category === filter) &&
                      n.title.toLowerCase().includes(localSearch.toLowerCase()),
                  ) && (
                    <p className="muted">No notebooks match these filters.</p>
                  )}
              </section>
              <div className="library-bottom">
                <ShieldCheck size={15} />
                <span>
                  Your original notes stay yours. Every generated insight stays
                  connected to its source.
                </span>
                <span className="bottom-signature">
                  THINK ON PAPER. BUILD FROM THERE.
                </span>
              </div>
            </>
          ) : view === "documents" ? (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">IDEAS, READY TO SHARE</div>
                  <h1>
                    Documents<span className="title-dot">.</span>
                  </h1>
                  <p>
                    Professional drafts from your notes, with the evidence a
                    click away.
                  </p>
                </div>
              </div>
              {docs.length === 0 ? (
                <Empty
                  icon={FileText}
                  title="Your notes have more to say"
                  text="Documents appear here after a notebook is processed. You can also generate a brief, report, meeting minutes or action plan from any ready notebook."
                  action={
                    <Button
                      variant="outline"
                      onClick={() => navigate("notebooks")}
                    >
                      Open notebooks <ArrowUpRight size={15} />
                    </Button>
                  }
                />
              ) : (
                <div className="document-list">
                  {docs.map((d) => (
                    <button
                      className="document-row"
                      key={d.id}
                      onClick={() => openDoc(d.id)}
                    >
                      <span className="doc-icon">
                        <FileText size={23} />
                      </span>
                      <div className="doc-row-title">
                        <h3>{d.title}</h3>
                        <p>
                          {d.notebook_title}
                          <span>·</span>
                          {readable(d.kind)}
                          <span>·</span>Version {d.version}
                        </p>
                      </div>
                      {d.stale && <Tag tone="amber">Newer notes</Tag>}
                      <Tag tone={d.reviewed ? "green" : "amber"}>
                        {d.reviewed ? "Reviewed" : "Needs review"}
                      </Tag>
                      <span className="muted small">{date(d.created_at)}</span>
                      <ArrowUpRight size={18} />
                    </button>
                  ))}
                </div>
              )}
            </>
          ) : view === "insights" ? (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">THE THINGS THAT MATTER</div>
                  <h1>
                    Actions & insights<span className="title-dot">.</span>
                  </h1>
                  <p>
                    Actions, decisions and open questions explicitly written in
                    your latest notes.
                  </p>
                </div>
                <Tag tone="purple">Extracted · verify against source</Tag>
              </div>
              {insights.length === 0 ? (
                <Empty
                  icon={ListChecks}
                  title="Clarity is on its way"
                  text="Once your notebooks are read, explicit actions, decisions, questions and responsibilities will appear here. Missing owners and dates stay marked as not specified."
                />
              ) : (
                <div className="insights-grid">
                  {insights.map((i, index) => (
                    <InsightCard
                      key={index}
                      item={i}
                      onSource={() =>
                        setSource({
                          pageId: i.page_id!,
                          quote: i.evidence_quote,
                        })
                      }
                      onNotebook={() => openNotebook(i.notebook_id!, i.page_id)}
                    />
                  ))}
                </div>
              )}
            </>
          ) : view === "activity" ? (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">BEHIND THE PAGES</div>
                  <h1>
                    Activity<span className="title-dot">.</span>
                  </h1>
                  <p>
                    Follow synchronisation, handwriting extraction and document
                    generation.
                  </p>
                </div>
                <Button variant="outline" onClick={refresh}>
                  <RefreshCw size={15} />
                  Refresh
                </Button>
              </div>
              {jobs.length === 0 ? (
                <Empty
                  icon={History}
                  title="A clean slate"
                  text="Import or sync a notebook to start. Processing jobs, retries and errors will appear here."
                />
              ) : (
                <div className="jobs-list">
                  {jobs.map((j) => (
                    <div className="job-row" key={j.id}>
                      <span className={`job-icon ${j.status}`}>
                        {j.status === "running" ? (
                          <Loader2 className="spin" size={20} />
                        ) : j.status === "completed" ? (
                          <Check size={20} />
                        ) : j.status === "failed" ? (
                          <AlertCircle size={20} />
                        ) : (
                          <History size={20} />
                        )}
                      </span>
                      <div>
                        <strong>
                          {j.kind === "process"
                            ? "Handwriting extraction"
                            : j.kind === "generate"
                              ? "Document generation"
                              : "reMarkable sync"}
                        </strong>
                        <p>{j.progress}</p>
                        {j.error && <p className="job-error">{j.error}</p>}
                        <span className="small muted">
                          {date(j.created_at)} · Attempt {j.attempts} of 3 ·{" "}
                          {j.id.slice(0, 8)}
                        </span>
                      </div>
                      <Tag
                        tone={
                          j.status === "completed"
                            ? "green"
                            : j.status === "failed"
                              ? "amber"
                              : ""
                        }
                      >
                        {j.status}
                      </Tag>
                      {j.status === "failed" && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={mutation}
                          onClick={() => run(`/jobs/${j.id}/retry`)}
                        >
                          Retry <RefreshCw size={13} />
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              )}
              <section className="audit-section">
                <h2>Audit trail</h2>
                {audit.length === 0 ? (
                  <p className="muted">No events recorded yet.</p>
                ) : (
                  audit.map((a) => (
                    <div className="audit-row" key={a.id}>
                      <span className="status-dot online" />
                      <strong>{readable(a.action.replaceAll(".", " "))}</strong>
                      <code>{a.target.slice(0, 12)}</code>
                      <span>{date(a.created_at)}</span>
                    </div>
                  ))
                )}
              </section>
            </>
          ) : view === "settings" ? (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">YOUR WORKSPACE, YOUR WAY</div>
                  <h1>
                    Connections & settings<span className="title-dot">.</span>
                  </h1>
                  <p>
                    Connect your notebooks and choose how your thinking is
                    processed.
                  </p>
                </div>
              </div>
              <div className="settings-grid">
                <section className="settings-card">
                  <div className="settings-card-header">
                    <span className="stat-icon lavender">
                      <BookOpen size={23} />
                    </span>
                    <div>
                      <h2>reMarkable Cloud</h2>
                      <p>Read-only automatic synchronisation</p>
                    </div>
                    <Tag tone={status?.remarkable_paired ? "green" : "amber"}>
                      {status?.remarkable_paired ? "Paired" : "Not paired"}
                    </Tag>
                  </div>
                  <p>
                    Pair on your Ubuntu server so cloud credentials never pass
                    through your browser. The connection uses the
                    community-maintained rmapi client.
                  </p>
                  <ol>
                    <li>
                      Open{" "}
                      <a
                        href="https://my.remarkable.com/device/desktop/connect"
                        target="_blank"
                        rel="noreferrer"
                      >
                        reMarkable device connection <ArrowUpRight size={12} />
                      </a>{" "}
                      to get a one-time code.
                    </li>
                    <li>
                      In the project directory on your server, run:
                      <pre>docker compose run --rm -it api rmapi</pre>
                    </li>
                    <li>
                      Enter the code, then exit the rmapi shell with Ctrl+D. The
                      worker detects the pairing automatically.
                    </li>
                  </ol>
                  <div className="settings-fact">
                    <span>Automatic sync</span>
                    <strong>
                      Every{" "}
                      {Math.round((status?.sync_interval_seconds || 300) / 60)}{" "}
                      minutes
                    </strong>
                  </div>
                  <div className="settings-fact">
                    <span>Access</span>
                    <strong>Download only</strong>
                  </div>
                  <Button
                    disabled={!status?.remarkable_paired || mutation}
                    onClick={() => run("/sync")}
                  >
                    <RefreshCw size={15} />
                    Sync notebooks now
                  </Button>
                  <p className="small muted">
                    Cloud formats can change. If an archive cannot be rendered,
                    export a PDF from reMarkable and import it.
                  </p>
                </section>
                <section className="settings-card">
                  <div className="settings-card-header">
                    <span className="stat-icon mint">
                      <Sparkles size={23} />
                    </span>
                    <div>
                      <h2>AI intelligence</h2>
                      <p>Vision extraction & structured generation</p>
                    </div>
                    <Tag tone={status?.ai_configured ? "green" : "amber"}>
                      {status?.ai_configured ? "Configured" : "Not configured"}
                    </Tag>
                  </div>
                  <p>
                    Set these values in Coolify’s environment variables, then
                    redeploy the API and worker.
                  </p>
                  <div className="env-list">
                    <code>OPENAI_API_KEY</code>
                    <span>Your provider API key</span>
                    <code>OPENAI_MODEL</code>
                    <span>A vision-capable model with structured outputs</span>
                    <code>OPENAI_BASE_URL</code>
                    <span>Optional compatible Responses API endpoint</span>
                  </div>
                  <div className="settings-fact">
                    <span>Selected model</span>
                    <strong>{status?.model || "—"}</strong>
                  </div>
                  <div className="settings-fact">
                    <span>Automatic output</span>
                    <strong>
                      {readable(status?.auto_document_type || "Disabled")}
                    </strong>
                  </div>
                  <div className="privacy-note">
                    <ShieldCheck size={19} />
                    <p>
                      When configured, rendered page images and transcripts are
                      sent to your AI provider. OpenAI response storage is
                      disabled. Review your provider’s data policy before
                      processing sensitive notes.
                    </p>
                  </div>
                </section>
                <section className="settings-card">
                  <div className="settings-card-header">
                    <span className="stat-icon peach">
                      <Settings size={23} />
                    </span>
                    <div>
                      <h2>Workspace health</h2>
                      <p>Persistent processing, clear status</p>
                    </div>
                  </div>
                  <div className="settings-fact">
                    <span>Background worker</span>
                    <Tag tone={status?.worker_online ? "green" : "amber"}>
                      {status?.worker_online ? "Online" : "Offline"}
                    </Tag>
                  </div>
                  <div className="settings-fact">
                    <span>Active jobs</span>
                    <strong>{status?.counts.active_jobs || 0}</strong>
                  </div>
                  <div className="settings-fact">
                    <span>Search</span>
                    <strong>Literal text search · latest revisions</strong>
                  </div>
                  <div className="settings-fact">
                    <span>Interface</span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        localStorage.setItem(
                          "noteforge-theme",
                          dark ? "light" : "dark",
                        );
                        setDark(!dark);
                      }}
                    >
                      {dark ? <Sun size={14} /> : <Moon size={14} />}Use{" "}
                      {dark ? "light" : "dark"} theme
                    </Button>
                  </div>
                  <p className="small muted">
                    Back up the PostgreSQL database and the data volume
                    together. Your source archives, page renders, document
                    versions and audit trail are all retained.
                  </p>
                </section>
                <section className="settings-card principle-card">
                  <Feather size={26} />
                  <h2>
                    Good thinking needs
                    <br />a trustworthy foundation.
                  </h2>
                  <p>
                    Facts, interpretations and recommendations stay distinct.
                    Missing information stays missing. Your handwriting remains
                    the source of truth.
                  </p>
                  <span className="eyebrow">THE NOTEFORGE PRINCIPLE</span>
                </section>
              </div>
            </>
          ) : view === "search" ? (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">FIND THE THREAD</div>
                  <h1>
                    Search your knowledge<span className="title-dot">.</span>
                  </h1>
                  <p>
                    Find exact text in the latest extracted version of each
                    notebook.
                  </p>
                </div>
              </div>
              <form onSubmit={search} className="full-search">
                <Search size={21} />
                <input
                  aria-label="Search notebook contents"
                  placeholder="A name, an idea, a decision…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  minLength={2}
                  required
                />
                <Button type="submit" disabled={searching}>
                  Search
                </Button>
              </form>
              {searching ? (
                <Busy text="Searching your notes…" />
              ) : results.length > 0 ? (
                <div className="search-results">
                  {results.map((r) => (
                    <button
                      className="search-result"
                      key={r.page_id}
                      onClick={() =>
                        openNotebook(r.notebook_id, r.page_id, r.revision_id)
                      }
                    >
                      <div>
                        <BookOpen size={17} />
                        <strong>{r.notebook_title}</strong>
                        <Tag>Page {r.number}</Tag>
                        <ArrowUpRight size={17} />
                      </div>
                      <p>{r.excerpt}</p>
                    </button>
                  ))}
                </div>
              ) : (
                <Empty
                  icon={Search}
                  title={
                    hasSearched
                      ? "No matching notes"
                      : "Follow an idea back to the page"
                  }
                  text={
                    hasSearched
                      ? "Try a shorter phrase or check that your notebooks have finished processing."
                      : "Search names, phrases and topics across your extracted notebooks."
                  }
                />
              )}
            </>
          ) : null}
        </main>
      </div>
      {notice && (
        <div className="toast" role="status">
          <Check size={17} />
          {notice}
          <button
            aria-label="Dismiss notification"
            onClick={() => setNotice("")}
          >
            <X size={15} />
          </button>
        </div>
      )}
      <dialog
        ref={importDialog}
        className="import-dialog"
        onCancel={(e) => {
          if (uploading) e.preventDefault();
        }}
      >
        <form onSubmit={upload}>
          <div className="modal-heading">
            <div>
              <span className="eyebrow">FROM PAPER TO POSSIBILITY</span>
              <h2>Import a notebook</h2>
            </div>
            <button
              type="button"
              className="icon-btn"
              aria-label="Close import"
              disabled={uploading}
              onClick={() => importDialog.current?.close()}
            >
              <X size={20} />
            </button>
          </div>
          <p className="muted">
            Your original is kept exactly as it is. We’ll take care of the rest.
          </p>
          <label
            className={`dropzone ${file ? "has-file" : ""}`}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              setFile(e.dataTransfer.files[0] || null);
            }}
          >
            <Upload size={27} />
            <strong>
              {file ? file.name : "Choose a notebook or drop it here"}
            </strong>
            <span>
              {file
                ? `${(file.size / 1024 / 1024).toFixed(1)} MB`
                : "PDF, PNG, JPEG or RMDOC · up to 40 MB by default"}
            </span>
            <input
              ref={fileInput}
              type="file"
              aria-label="Choose notebook file"
              accept=".pdf,.png,.jpg,.jpeg,.rmdoc"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              disabled={uploading}
            />
          </label>
          <div className="import-note">
            <ShieldCheck size={17} />
            <span>
              Original preserved · Page-level sources · No invented details
            </span>
          </div>
          {error && (
            <div className="inline-error" role="alert">
              {error}
            </div>
          )}
          <div className="modal-footer">
            <Button
              type="button"
              variant="outline"
              disabled={uploading}
              onClick={() => importDialog.current?.close()}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={!file || uploading}>
              {uploading ? (
                <Loader2 size={16} className="spin" />
              ) : (
                <Plus size={16} />
              )}{" "}
              {uploading ? "Preserving notebook…" : "Import notebook"}
            </Button>
          </div>
        </form>
      </dialog>
      <dialog
        ref={sourceDialog}
        className="source-dialog"
        onClose={() => setSource(null)}
      >
        <div className="modal-heading">
          <h2>
            <BookOpen size={20} />
            Original source page
          </h2>
          <button
            className="icon-btn"
            aria-label="Close source preview"
            onClick={() => sourceDialog.current?.close()}
          >
            <X size={20} />
          </button>
        </div>
        {source?.quote && (
          <blockquote>
            <Quote size={18} />
            {source.quote}
          </blockquote>
        )}
        {source && (
          <div className="source-modal-image">
            <img
              src={`/api/pages/${source.pageId}/image`}
              alt="Original handwritten source page"
            />
          </div>
        )}
        <p className="small muted">
          Check the cited text and its context against the original page.
        </p>
      </dialog>
    </div>
  );
}

function InsightCard({
  item,
  onSource,
  onNotebook,
}: {
  item: Insight;
  onSource: () => void;
  onNotebook?: () => void;
}) {
  return (
    <article className="insight-card">
      <div className="insight-top">
        <Tag
          tone={
            item.kind === "action"
              ? "purple"
              : item.kind === "decision"
                ? "green"
                : ""
          }
        >
          {item.kind}
        </Tag>
        <span className="small muted">
          {Math.round(item.confidence * 100)}% model estimate
        </span>
      </div>
      <h3>{item.text}</h3>
      {["action", "responsibility"].includes(item.kind) && (
        <div className="insight-fields">
          <span>
            Owner <strong>{item.owner || "Not specified"}</strong>
          </span>
          <span>
            Due <strong>{item.due_date || "Not specified"}</strong>
          </span>
        </div>
      )}
      <button className="citation" onClick={onSource}>
        <Quote size={13} />
        {item.evidence_quote}
      </button>
      {item.notebook_title && (
        <button className="insight-source" onClick={onNotebook}>
          <BookOpen size={13} />
          {item.notebook_title}
          <span>· page {item.number}</span>
          <ArrowUpRight size={13} />
        </button>
      )}
    </article>
  );
}
