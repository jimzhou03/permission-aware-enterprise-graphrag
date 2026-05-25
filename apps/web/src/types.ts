export type AskMode = "auto" | "rag" | "graphrag";

export interface UserPublic {
  id: string;
  email: string;
  full_name: string;
  role: string;
  department: string | null;
  permissions: string[];
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserPublic;
}

export interface AuthMeResponse {
  user: UserPublic;
  permission_scope: {
    role: string;
    department: string | null;
  };
}

export interface KnowledgeBase {
  id: string;
  code: string;
  display_name: string;
  name: string;
  language: string;
  description: string;
  department: string | null;
  visibility: string;
  version: number;
}

export interface KnowledgeBaseDocument {
  id: string;
  knowledge_base_id: string;
  knowledge_base_code: string;
  title: string;
  source: string;
  created_at: string;
  chunk_count: number;
}

export interface DocumentChunk {
  id: string;
  document_id: string;
  knowledge_base_id: string;
  knowledge_base_code: string;
  chunk_index: number;
  content_preview: string;
  content: string;
  has_embedding: boolean;
  embedding_dimension: number;
}

export interface DocumentIngestionResult {
  action: "document_upload" | "document_reindex" | string;
  status: "success" | "failed" | string;
  knowledge_base_id: string;
  knowledge_base_code: string;
  knowledge_base_version: number;
  document_id: string;
  document_title: string;
  document_source: string;
  document_version: number;
  filename: string;
  chunk_count: number;
}

export interface DemoCase {
  id: string;
  role: string;
  question: string;
  expected: string;
}

export interface Citation {
  kb_id: string;
  kb_code: string;
  kb_name: string;
  document_id: string;
  document_title: string;
  chunk_id: string;
  score: number;
  excerpt: string;
}

export interface GraphPath {
  chunk_id: string;
  path: string[];
  explanation: string;
}

export type GraphNodeType =
  | "knowledge_base"
  | "document"
  | "chunk"
  | "entity"
  | "department"
  | "topic";

export type GraphEdgeType =
  | "CONTAINS"
  | "HAS_CHUNK"
  | "MENTIONS"
  | "BELONGS_TO"
  | "RELATED_TO"
  | "DERIVED_FROM";

export interface GraphNode {
  id: string;
  label: string;
  type: GraphNodeType;
  kb_id: string | null;
  kb_code: string | null;
  title: string | null;
  metadata_summary: string | null;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: GraphEdgeType;
  label: string;
}

export interface GraphStatus {
  neo4j_configured: boolean;
  neo4j_available: boolean;
  graph_sync_enabled: boolean;
  graph_sync_needed: boolean;
  pending_sync_kb_codes: string[];
  node_count: number | null;
  relationship_count: number | null;
  fallback_mode: string;
  last_sync_summary: Record<string, string | number | boolean | null>;
}

export interface GraphOverview {
  allowed_kb_ids: string[];
  allowed_kb_codes: string[];
  nodes: GraphNode[];
  edges: GraphEdge[];
  fallback_used: boolean;
  generated_at: string;
  security_notes: string[];
}

export interface QAGraphTrace {
  request_id: string;
  mode: string;
  viewer_email: string | null;
  viewer_role: string | null;
  viewer_department: string | null;
  allowed_kb_ids: string[];
  allowed_kb_codes: string[];
  graph_paths: GraphPath[];
  nodes: GraphNode[];
  edges: GraphEdge[];
  fallback_used: boolean;
  security_notes: string[];
}

export interface AskResponse {
  request_id: string;
  answer: string;
  denied: boolean;
  refusal_reason: string | null;
  cache_hit: boolean;
  mode: "direct" | "rag" | "graphrag" | "general";
  route: {
    target_department: string | null;
    mode: "direct" | "rag" | "graphrag" | "general";
    requires_rag: boolean;
    need_rag: boolean;
    confidence: number;
    reason: string;
    language: "zh" | "en" | "unknown";
    intent: "greeting" | "policy_question" | "knowledge_lookup" | "security_test" | "unsupported";
    router_mode: "rules" | "ollama";
    router_model: string;
    router_fallback_used: boolean;
    router_error: string | null;
  };
  router_mode: "rules" | "ollama";
  router_model: string;
  router_fallback_used: boolean;
  router_error: string | null;
  retrieved_chunks: Citation[];
  citations: Citation[];
  graph_paths: GraphPath[];
  function_trace_summary: string[];
}

export interface AuditLog {
  request_id: string;
  user_id: string | null;
  question: string;
  answer: string;
  denied: boolean;
  refusal_reason: string;
  hit_kb_ids: string[];
  hit_document_ids: string[];
  hit_chunk_ids: string[];
  mode: string;
  model: string;
  cache_hit: boolean;
  latency_ms: number;
}

export interface TraceRetrievedChunk {
  chunk_id: string;
  kb_id: string;
  kb_code: string;
  kb_name: string;
  document_id: string;
  document_title: string;
  chunk_index: number;
  content_preview: string;
  content: string;
  has_embedding: boolean;
  embedding_dimension: number;
}

export interface FunctionTraceStep {
  tool_name: string;
  status: "success" | "skipped" | "denied" | "error";
  input_summary: string;
  output_summary: string;
  duration_ms: number;
  security_note: string;
  error_code: string | null;
  order_index: number;
}

export interface RequestTrace {
  request_id: string;
  user_id: string | null;
  user_email: string | null;
  role: string | null;
  department: string | null;
  question: string;
  answer: string;
  mode: string;
  denied: boolean;
  refusal_reason: string;
  allowed_kb_ids: string[];
  allowed_kb_codes: string[];
  hit_kb_ids: string[];
  hit_document_ids: string[];
  hit_chunk_ids: string[];
  retrieved_chunks: TraceRetrievedChunk[];
  retrieval_engine: string;
  router_mode: "rules" | "ollama";
  router_model: string;
  router_availability: "available" | "unavailable" | "not_checked" | string;
  router_fallback_used: boolean;
  router_error: string | null;
  router_decision: AskResponse["route"] | null;
  cache_hit: boolean;
  model: string;
  latency_ms: number;
  function_trace: FunctionTraceStep[];
  trace_limits: string[];
}

export interface RetrievalConfig {
  embedding_provider: string;
  embedding_dimension: number;
  retrieval_engine: string;
  top_k: number;
  default_top_k: number;
  generator_mode: string;
  router_mode: string;
  router_model: string;
  router_availability: string;
  router_fallback_last: boolean;
  router_error_last: string | null;
  pgvector_available: boolean;
  sql_vector_search_enabled: boolean;
  pgvector_sql_retrieval_enabled: boolean;
  pgvector_field_available: boolean;
  cache_backend: string;
  model_mode: string;
  function_calling_mode: string;
  llm_autonomous_tool_calling: boolean;
  permission_authority: string;
  document_upload_enabled: boolean;
  upload_max_size_bytes: number;
  upload_supported_types: string[];
  indexing_mode: string;
  neo4j_configured: boolean;
  neo4j_available: boolean;
  graph_sync_enabled: boolean;
  graph_sync_needed: boolean;
  graph_pending_sync_kb_codes: string[];
  graph_visualization_enabled: boolean;
  graph_permission_scope: string;
  graph_fallback_mode: string;
  graph_node_count: number | null;
  graph_relationship_count: number | null;
  graph_last_sync_status: string | null;
}
