export type Notebook = {
  id: string;
  title: string;
  source: string;
  category: string;
  status: string;
  pages: number;
  updated_at: string;
};
export type Insight = {
  kind: string;
  text: string;
  evidence_quote: string;
  owner: string | null;
  due_date: string | null;
  confidence: number;
  page_id?: string;
  number?: number;
  notebook_id?: string;
  notebook_title?: string;
  review_status?: string;
};
export type Extraction = {
  transcript: string;
  category: string;
  purpose: string;
  blocks: {
    kind: string;
    text: string;
    evidence_quote: string;
    confidence: number;
    uncertain: boolean;
  }[];
  insights: Insight[];
  uncertainties: string[];
};
export type Page = {
  id: string;
  number: number;
  extraction: Extraction | null;
  review_status: string;
  review_note: string;
  model: string | null;
};
export type Detail = {
  id: string;
  title: string;
  source: string;
  category: string;
  latest_revision_id: string;
  revision: {
    id: string;
    status: string;
    warning: string | null;
    sha256: string;
    filename: string;
  };
  revisions: { id: string; created_at: string; status: string }[];
  pages: Page[];
};
export type Citation = { page_id: string; quote: string };
export type Content = {
  title: string;
  sections: {
    heading: string;
    paragraphs: {
      kind: "fact" | "interpretation" | "recommendation";
      text: string;
      citations: Citation[];
    }[];
  }[];
  missing_information: string[];
};
export type DocItem = {
  id: string;
  title: string;
  kind: string;
  reviewed: boolean;
  version: number;
  created_at: string;
  notebook_title: string;
  notebook_id: string;
  stale: boolean;
};
export type DocDetail = {
  id: string;
  notebook_id: string;
  revision_id: string;
  content: Content;
  kind: string;
  reviewed: boolean;
  version: number;
  model: string;
  stale: boolean;
  versions: {
    number: number;
    created_at: string;
    reviewed: boolean;
    content: Content;
  }[];
};
export type Job = {
  id: string;
  kind: string;
  status: string;
  attempts: number;
  progress: string;
  error: string | null;
  created_at: string;
  updated_at: string;
};
export type Status = {
  remarkable_paired: boolean;
  ai_configured: boolean;
  model: string;
  worker_online: boolean;
  sync_interval_seconds: number;
  auto_document_type: string;
  counts: {
    notebooks: number;
    documents: number;
    review: number;
    active_jobs: number;
  };
};
export type SearchResult = {
  page_id: string;
  notebook_id: string;
  notebook_title: string;
  revision_id: string;
  number: number;
  excerpt: string;
};
export type Audit = {
  id: string;
  action: string;
  target: string;
  detail: Record<string, unknown>;
  created_at: string;
};
