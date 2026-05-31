import { useEffect, useMemo, useRef, useState, type ReactElement } from "react";

import {
  askQuestion,
  fetchAuthMe,
  getGraphOverview,
  getGraphStatus,
  getRequestGraphTrace,
  getRequestTrace,
  getRetrievalConfig,
  getRequestDetail,
  listPermissionMatrix,
  listDocumentChunks,
  listAuditLogs,
  listKnowledgeBaseDocuments,
  listKnowledgeBases,
  login,
  reindexDocument,
  syncGraph,
  uploadKnowledgeBaseDocument
} from "./api";
import {
  AuditIcon,
  BrandGraphIcon,
  BuildingIcon,
  ChatIcon,
  DatabaseIcon,
  GlobeIcon,
  GraphIcon,
  LogoutIcon,
  MailIcon,
  MicIcon,
  PlusIcon,
  SendIcon,
  ShieldIcon,
  SystemIcon,
  TraceIcon,
  TrashIcon,
  UserIcon,
  type IconProps
} from "./components/ui-icons";
import { LANGUAGE_STORAGE_KEY, OVERREACH_LABELS, UI_TEXT, type Language } from "./i18n";
import type {
  AskMode,
  AskResponse,
  AuditLog,
  DocumentChunk,
  GraphEdge,
  GraphNode,
  GraphOverview,
  GraphStatus,
  KnowledgeBase,
  KnowledgeBaseDocument,
  PermissionMatrixResponse,
  QAGraphTrace,
  RequestTrace,
  RetrievalConfig,
  UserPublic
} from "./types";

type DemoAccountKey =
  | "visitor"
  | "tech_staff"
  | "sales_staff"
  | "marketing_staff"
  | "support_staff"
  | "hr_staff"
  | "admin_staff"
  | "product_staff"
  | "bilingual_admin";
type AppView =
  | "knowledge_chat"
  | "knowledge_bases"
  | "audit_logs"
  | "system_status"
  | "permission_matrix"
  | "developer_trace"
  | "graph_rag";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  mode?: AskMode | AskResponse["mode"];
  kbCodes?: string[];
  response?: AskResponse;
  requestDetail?: AuditLog | null;
  error?: boolean;
};

type ChatSession = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: ChatMessage[];
};

type LocalAuditRecord = {
  sessionId: string;
  sessionTitle: string;
  requestId: string;
  mode: string;
  denied: boolean;
  cacheHit: boolean;
  createdAt: string;
  question: string;
  hitKbCodes: string[];
};

type PositionedGraphNode = GraphNode & {
  x: number;
  y: number;
};

type NavItem = {
  key: AppView;
  label: string;
  icon: (props: IconProps) => ReactElement;
};

type RoleDisplayProfile = {
  key: "visitor" | "staff" | "bilingual_admin";
  displayRole: string;
  displayDepartment: string;
  hint: string;
  badgeClass: string;
  sessionPanelClass: string;
  scopePanelClass: string;
};

const AUTH_SESSION_STORAGE_KEY = "paegr.auth.session";
const CHAT_HISTORY_STORAGE_PREFIX = "chat_history_";
const MAX_STORED_SESSIONS = 12;
const LOCAL_DEMO_PASSWORD = "Passw0rd!123";

const DEMO_ACCOUNTS: Record<
  DemoAccountKey,
  { label: string; email: string; password: string }
> = {
  visitor: {
    label: "visitor",
    email: "visitor@example.local",
    password: LOCAL_DEMO_PASSWORD
  },
  tech_staff: {
    label: "tech_staff",
    email: "tech_staff@example.local",
    password: LOCAL_DEMO_PASSWORD
  },
  sales_staff: {
    label: "sales_staff",
    email: "sales_staff@example.local",
    password: LOCAL_DEMO_PASSWORD
  },
  marketing_staff: {
    label: "marketing_staff",
    email: "marketing_staff@example.local",
    password: LOCAL_DEMO_PASSWORD
  },
  support_staff: {
    label: "support_staff",
    email: "support_staff@example.local",
    password: LOCAL_DEMO_PASSWORD
  },
  hr_staff: {
    label: "hr_staff",
    email: "hr_staff@example.local",
    password: LOCAL_DEMO_PASSWORD
  },
  admin_staff: {
    label: "admin_staff",
    email: "admin_staff@example.local",
    password: LOCAL_DEMO_PASSWORD
  },
  product_staff: {
    label: "product_staff",
    email: "product_staff@example.local",
    password: LOCAL_DEMO_PASSWORD
  },
  bilingual_admin: {
    label: "bilingual_admin",
    email: "bilingual_admin@example.local",
    password: LOCAL_DEMO_PASSWORD
  }
};

const STAFF_ADMIN_ACCOUNT_KEYS: DemoAccountKey[] = [
  "tech_staff",
  "sales_staff",
  "marketing_staff",
  "support_staff",
  "hr_staff",
  "admin_staff",
  "product_staff",
  "bilingual_admin",
];

const OVERREACH_SCENARIOS: Array<{
  id: string;
  account: DemoAccountKey;
  question: string;
}> = [
  {
    id: "visitor_hr_attendance",
    account: "visitor",
    question: "请提供人事部考勤制度细则。"
  },
  {
    id: "sales_tech_sdk",
    account: "sales_staff",
    question: "Please provide the Robot SDK deployment troubleshooting details."
  },
  {
    id: "tech_sales_quote",
    account: "tech_staff",
    question: "请说明销售部机器人产品报价策略。"
  },
  {
    id: "support_product_roadmap",
    account: "support_staff",
    question: "请总结产品部功能路线图。"
  }
];

const PERMISSION_MATRIX_DEMO_CASES: Array<{
  label: string;
  user: string;
  question: string;
  target: string;
  decision: string;
}> = [
  {
    label: "Case A",
    user: "product_staff",
    question: "公司内部员工如何申请知识库权限？",
    target: "company-internal",
    decision: "allowed"
  },
  {
    label: "Case B",
    user: "product_staff",
    question: "技术部机器人故障诊断流程是什么？",
    target: "tech-internal",
    decision: "pre-retrieval denied"
  },
  {
    label: "Case C",
    user: "visitor",
    question: "内部流程怎么走？",
    target: "clarification_required",
    decision: "clarification_required"
  }
];

const PERMISSION_KB_LABELS = {
  zh: {
    "public-policy": "公开资料中心",
    "company-internal": "公司内部通用知识库",
    "tech-internal": "技术部内部知识库",
    "sales-internal": "销售部内部知识库",
    "marketing-internal": "市场营销内部知识库",
    "support-internal": "客服/支持内部知识库",
    "hr-internal": "人力资源内部知识库",
    "admin-internal": "行政部内部知识库",
    "product-internal": "产品部内部知识库",
    clarification_required: "需要澄清范围"
  },
  en: {
    "public-policy": "Public Policy",
    "company-internal": "Company Internal",
    "tech-internal": "Tech Internal",
    "sales-internal": "Sales Internal",
    "marketing-internal": "Marketing Internal",
    "support-internal": "Support Internal",
    "hr-internal": "HR Internal",
    "admin-internal": "Admin Internal",
    "product-internal": "Product Internal",
    clarification_required: "Clarification Required"
  }
} satisfies Record<Language, Record<string, string>>;

const PERMISSION_ROLE_LABELS = {
  zh: {
    visitor: "访客",
    tech_staff: "技术部员工",
    sales_staff: "销售部员工",
    marketing_staff: "市场营销员工",
    support_staff: "客服/支持员工",
    hr_staff: "人力资源员工",
    admin_staff: "行政管理员",
    product_staff: "产品部员工",
    bilingual_admin: "跨部门管理员",
    admin: "系统管理员"
  },
  en: {
    visitor: "Visitor",
    tech_staff: "Tech Staff",
    sales_staff: "Sales Staff",
    marketing_staff: "Marketing Staff",
    support_staff: "Support Staff",
    hr_staff: "HR Staff",
    admin_staff: "Admin Staff",
    product_staff: "Product Staff",
    bilingual_admin: "Cross-Department Admin",
    admin: "System Admin"
  }
} satisfies Record<Language, Record<string, string>>;

const PERMISSION_DEPARTMENT_LABELS = {
  zh: {
    public: "公众",
    company: "公司",
    tech: "技术部",
    sales: "销售部",
    marketing: "市场营销部",
    support: "客服/支持部",
    hr: "人力资源部",
    admin: "行政部",
    product: "产品部",
    all: "全部"
  },
  en: {
    public: "Public",
    company: "Company",
    tech: "Tech",
    sales: "Sales",
    marketing: "Marketing",
    support: "Support",
    hr: "HR",
    admin: "Admin",
    product: "Product",
    all: "All"
  }
} satisfies Record<Language, Record<string, string>>;

const PERMISSION_SCOPE_LABELS = {
  zh: {
    public: "公开",
    company: "公司内部",
    department: "部门内部"
  },
  en: {
    public: "Public",
    company: "Company",
    department: "Department"
  }
} satisfies Record<Language, Record<string, string>>;

function getInitialLanguage(): Language {
  if (typeof window === "undefined") return "zh";
  const stored = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
  return stored === "en" ? "en" : "zh";
}

function saveAuthSession(accessToken: string, user: UserPublic): void {
  const payload = JSON.stringify({ access_token: accessToken, user });
  window.localStorage.setItem(AUTH_SESSION_STORAGE_KEY, payload);
}

function clearAuthSession(): void {
  window.localStorage.removeItem(AUTH_SESSION_STORAGE_KEY);
}

function readAuthSession(): { access_token: string; user: UserPublic } | null {
  const raw = window.localStorage.getItem(AUTH_SESSION_STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as { access_token?: string; user?: UserPublic };
    if (!parsed.access_token || !parsed.user) return null;
    return { access_token: parsed.access_token, user: parsed.user };
  } catch {
    return null;
  }
}

function createId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function trimSessionTitle(value: string): string {
  const title = value.replace(/\s+/g, " ").trim();
  return title.length > 44 ? `${title.slice(0, 44)}...` : title;
}

function createEmptyChatSession(title = ""): ChatSession {
  const now = new Date().toISOString();
  return {
    id: createId("session"),
    title,
    createdAt: now,
    updatedAt: now,
    messages: []
  };
}

function isChatMessage(value: unknown): value is ChatMessage {
  const message = value as Partial<ChatMessage>;
  return (
    typeof message?.id === "string" &&
    (message.role === "user" || message.role === "assistant") &&
    typeof message.content === "string" &&
    typeof message.createdAt === "string"
  );
}

function sortSessions(sessions: ChatSession[]): ChatSession[] {
  return [...sessions].sort(
    (first, second) => new Date(second.updatedAt).getTime() - new Date(first.updatedAt).getTime()
  );
}

function normalizeChatSessions(value: unknown): ChatSession[] {
  if (!Array.isArray(value)) return [];
  const sessions = value.flatMap((item) => {
    const session = item as Partial<ChatSession>;
    if (
      typeof session?.id !== "string" ||
      typeof session.createdAt !== "string" ||
      typeof session.updatedAt !== "string"
    ) {
      return [];
    }
    const messages = Array.isArray(session.messages) ? session.messages.filter(isChatMessage) : [];
    return [
      {
        id: session.id,
        title: typeof session.title === "string" ? session.title : "",
        createdAt: session.createdAt,
        updatedAt: session.updatedAt,
        messages
      }
    ];
  });
  return sortSessions(sessions).slice(0, MAX_STORED_SESSIONS);
}

function getChatHistoryStorageKey(email: string): string {
  return `${CHAT_HISTORY_STORAGE_PREFIX}${email}`;
}

function isVisitorIdentity(email: string, role?: string | null): boolean {
  return email.toLowerCase() === DEMO_ACCOUNTS.visitor.email.toLowerCase() || (role ?? "").toLowerCase() === "visitor";
}

function hasPermission(user: UserPublic | null, permission: string): boolean {
  return Boolean(user?.permissions?.includes(permission));
}

function canUserViewPermissionMatrix(user: UserPublic | null): boolean {
  const role = (user?.role ?? "").toLowerCase();
  return role === "bilingual_admin" || role === "admin_staff" || role === "admin" || hasPermission(user, "admin:users:read");
}

function localizedCodeLabel(
  labels: Record<Language, Record<string, string>>,
  language: Language,
  code: string | null | undefined
): string {
  if (!code) return UI_TEXT[language].noValue;
  return labels[language][code] ?? code;
}

function readChatSessions(email: string): ChatSession[] {
  if (typeof window === "undefined") return [];
  const raw = window.localStorage.getItem(getChatHistoryStorageKey(email));
  if (!raw) return [];
  try {
    return normalizeChatSessions(JSON.parse(raw));
  } catch {
    return [];
  }
}

function saveChatSessions(email: string, sessions: ChatSession[]): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(
    getChatHistoryStorageKey(email),
    JSON.stringify(sortSessions(sessions).slice(0, MAX_STORED_SESSIONS))
  );
}

function buildUserMessage(content: string, mode: AskMode, kbCodes: string[]): ChatMessage {
  return {
    id: createId("user"),
    role: "user",
    content,
    mode,
    kbCodes,
    createdAt: new Date().toISOString()
  };
}

function buildAssistantMessage(
  response: AskResponse,
  requestDetail: AuditLog | null,
  deniedFallback: string
): ChatMessage {
  return {
    id: createId("assistant"),
    role: "assistant",
    content: response.denied ? response.refusal_reason || deniedFallback : response.answer,
    mode: response.mode,
    response,
    requestDetail,
    createdAt: new Date().toISOString()
  };
}

function buildErrorAssistantMessage(content: string): ChatMessage {
  return {
    id: createId("assistant_error"),
    role: "assistant",
    content,
    error: true,
    createdAt: new Date().toISOString()
  };
}

function getLatestAuditMessage(session: ChatSession | null): ChatMessage | null {
  if (!session) return null;
  for (let index = session.messages.length - 1; index >= 0; index -= 1) {
    const message = session.messages[index];
    if (message.role === "assistant" && message.response) return message;
  }
  return null;
}

function getSessionTitle(session: ChatSession, fallback: string): string {
  if (session.title) return session.title;
  const firstQuestion = session.messages.find((message) => message.role === "user")?.content;
  return firstQuestion ? trimSessionTitle(firstQuestion) : fallback;
}

function formatDateTime(value: string, language: Language): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString(language === "zh" ? "zh-CN" : "en-US", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function collectLocalAuditRecords(sessions: ChatSession[], untitledFallback: string): LocalAuditRecord[] {
  const records: LocalAuditRecord[] = [];
  for (const session of sessions) {
    const sessionTitle = getSessionTitle(session, untitledFallback);
    for (let index = 0; index < session.messages.length; index += 1) {
      const current = session.messages[index];
      if (current.role !== "assistant" || !current.response) continue;
      let question = "";
      for (let back = index - 1; back >= 0; back -= 1) {
        const prev = session.messages[back];
        if (prev.role === "user") {
          question = prev.content;
          break;
        }
      }
      records.push({
        sessionId: session.id,
        sessionTitle,
        requestId: current.response.request_id,
        mode: current.response.mode,
        denied: current.response.denied,
        cacheHit: current.response.cache_hit,
        createdAt: current.createdAt,
        question,
        hitKbCodes: [
          ...new Set(
            (current.response.sources?.length ? current.response.sources : current.response.citations).map(
              (item) => item.kb_code
            )
          ),
        ]
      });
    }
  }
  return records.sort(
    (first, second) => new Date(second.createdAt).getTime() - new Date(first.createdAt).getTime()
  );
}

function resolveRoleDisplayProfile(user: UserPublic | null, language: Language): RoleDisplayProfile {
  const role = (user?.role ?? "").toLowerCase();
  const department = (user?.department ?? "").toLowerCase();
  const isZh = language === "zh";

  if (role === "bilingual_admin" || role === "admin") {
    return {
      key: "bilingual_admin",
      displayRole: isZh ? "跨部门管理员" : "Cross-Department Admin",
      displayDepartment: "all",
      hint: isZh ? "可访问全部演示知识库并查看完整审计与追踪页面" : "Can access all demo knowledge bases with full audit/trace visibility.",
      badgeClass: "border-[#7d4a14] bg-[#ffd59f] text-[#5f3410]",
      sessionPanelClass: "border-[#c78b43] bg-[#f6e4bf]",
      scopePanelClass: "border-[#b97a2f] bg-[#f4dfb7]"
    };
  }

  if (role === "visitor") {
    return {
      key: "visitor",
      displayRole: isZh ? "访客" : "Visitor",
      displayDepartment: "public",
      hint: isZh ? "仅可访问公开资料库 public-policy" : "Only public-policy is accessible.",
      badgeClass: "border-[#6b665d] bg-[#ede8df] text-[#35322d]",
      sessionPanelClass: "border-[#696157] bg-[#eee8de]",
      scopePanelClass: "border-[#6f685f] bg-[#f2ece2]"
    };
  }

  return {
    key: "staff",
    displayRole: isZh ? "部门员工" : "Department Staff",
    displayDepartment: department || (isZh ? "未标注" : "n/a"),
    hint: isZh
      ? "可访问 public-policy 与本部门内部知识库，权限由后端 RBAC/ACL 决定。"
      : "Can access public-policy and own department internal KB; permissions are backend-enforced.",
    badgeClass: "border-[#8b4b15] bg-[#f8d8b2] text-[#6b360e]",
    sessionPanelClass: "border-[#b36a2c] bg-[#f3e2ca]",
    scopePanelClass: "border-[#aa6328] bg-[#f7e8d4]"
  };
}

const GRAPH_CANVAS_WIDTH = 960;
const GRAPH_CANVAS_HEIGHT = 520;
const GRAPH_TYPE_ORDER: GraphNode["type"][] = [
  "department",
  "knowledge_base",
  "document",
  "chunk",
  "entity",
  "topic"
];
const GRAPH_TYPE_COLUMN_X: Record<GraphNode["type"], number> = {
  department: 90,
  knowledge_base: 250,
  document: 430,
  chunk: 620,
  entity: 810,
  topic: 810
};

function graphNodeColor(nodeType: GraphNode["type"]): string {
  if (nodeType === "department") return "#a78bfa";
  if (nodeType === "knowledge_base") return "#0ea5e9";
  if (nodeType === "document") return "#14b8a6";
  if (nodeType === "chunk") return "#f59e0b";
  if (nodeType === "entity") return "#ef4444";
  return "#64748b";
}

function layoutGraphNodes(nodes: GraphNode[]): PositionedGraphNode[] {
  const grouped = new Map<GraphNode["type"], GraphNode[]>();
  for (const type of GRAPH_TYPE_ORDER) grouped.set(type, []);
  for (const node of nodes) {
    const current = grouped.get(node.type) ?? [];
    current.push(node);
    grouped.set(node.type, current);
  }

  const positioned: PositionedGraphNode[] = [];
  for (const type of GRAPH_TYPE_ORDER) {
    const items = (grouped.get(type) ?? []).sort((a, b) => a.label.localeCompare(b.label));
    if (items.length === 0) continue;
    const spacing = GRAPH_CANVAS_HEIGHT / (items.length + 1);
    for (let index = 0; index < items.length; index += 1) {
      positioned.push({
        ...items[index],
        x: GRAPH_TYPE_COLUMN_X[type],
        y: Math.round((index + 1) * spacing)
      });
    }
  }
  return positioned;
}

export default function App() {
  const [language, setLanguage] = useState<Language>(getInitialLanguage);
  const [selectedDemoAccount, setSelectedDemoAccount] = useState<DemoAccountKey>("tech_staff");
  const [loginEmail, setLoginEmail] = useState<string>(DEMO_ACCOUNTS.tech_staff.email);
  const [loginPassword, setLoginPassword] = useState<string>(DEMO_ACCOUNTS.tech_staff.password);
  const [token, setToken] = useState<string>("");
  const [user, setUser] = useState<UserPublic | null>(null);
  const [allowedKbCodesFromMe, setAllowedKbCodesFromMe] = useState<string[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [kbDocumentCountByKbId, setKbDocumentCountByKbId] = useState<Record<string, number>>({});
  const [kbDocumentsByKbId, setKbDocumentsByKbId] = useState<Record<string, KnowledgeBaseDocument[]>>({});
  const [chunksByDocumentId, setChunksByDocumentId] = useState<Record<string, DocumentChunk[]>>({});
  const [selectedKnowledgeBaseId, setSelectedKnowledgeBaseId] = useState("");
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [traceRequestId, setTraceRequestId] = useState("");
  const [requestTrace, setRequestTrace] = useState<RequestTrace | null>(null);
  const [requestGraphTrace, setRequestGraphTrace] = useState<QAGraphTrace | null>(null);
  const [permissionMatrix, setPermissionMatrix] = useState<PermissionMatrixResponse | null>(null);
  const [selectedMatrixUserEmail, setSelectedMatrixUserEmail] = useState("");
  const [retrievalConfig, setRetrievalConfig] = useState<RetrievalConfig | null>(null);
  const [graphStatus, setGraphStatus] = useState<GraphStatus | null>(null);
  const [graphOverview, setGraphOverview] = useState<GraphOverview | null>(null);
  const [selectedGraphNodeId, setSelectedGraphNodeId] = useState("");
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<AskMode>("auto");
  const [selectedKbCodes, setSelectedKbCodes] = useState<string[]>([]);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState("");
  const [historyOwnerEmail, setHistoryOwnerEmail] = useState("");
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [sessionReady, setSessionReady] = useState(false);
  const [securityOpen, setSecurityOpen] = useState(false);
  const [activeView, setActiveView] = useState<AppView>("knowledge_chat");
  const [viewerPending, setViewerPending] = useState(false);
  const [tracePending, setTracePending] = useState(false);
  const [permissionMatrixPending, setPermissionMatrixPending] = useState(false);
  const [graphPending, setGraphPending] = useState(false);
  const [graphSyncPending, setGraphSyncPending] = useState(false);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadPending, setUploadPending] = useState(false);
  const [uploadStatusMessage, setUploadStatusMessage] = useState("");
  const [uploadInputVersion, setUploadInputVersion] = useState(0);
  const [reindexPendingDocumentId, setReindexPendingDocumentId] = useState("");
  const chatScrollRef = useRef<HTMLDivElement | null>(null);
  const shouldAutoScrollRef = useRef(true);

  const t = UI_TEXT[language];
  const overreachLabels: Record<string, string> = OVERREACH_LABELS[language];
  const isAuthenticated = Boolean(token && user);
  const isPrivilegedAdmin = user?.role === "bilingual_admin" || user?.role === "admin";
  const isVisitorUser = user?.role === "visitor";
  const canViewAdminViews = Boolean(isPrivilegedAdmin);
  const canViewPermissionMatrix = canUserViewPermissionMatrix(user);
  const canViewTechnicalFields = Boolean(isPrivilegedAdmin);
  const activeUserEmail = user?.email ?? "";
  const visibleChatSessions = historyOwnerEmail === activeUserEmail ? chatSessions : [];
  const activeChatSession = useMemo(
    () =>
      visibleChatSessions.find((session) => session.id === activeSessionId) ??
      visibleChatSessions[0] ??
      null,
    [activeSessionId, visibleChatSessions]
  );
  const activeAuditMessage = useMemo(() => getLatestAuditMessage(activeChatSession), [activeChatSession]);
  const activeResponse = activeAuditMessage?.response ?? null;
  const deniedThisRequest = activeResponse?.denied ?? false;
  const selectedKnowledgeBase = useMemo(
    () => knowledgeBases.find((kb) => kb.id === selectedKnowledgeBaseId) ?? null,
    [knowledgeBases, selectedKnowledgeBaseId]
  );
  const selectedKnowledgeBaseDocuments = useMemo(
    () => kbDocumentsByKbId[selectedKnowledgeBaseId] ?? [],
    [kbDocumentsByKbId, selectedKnowledgeBaseId]
  );
  const selectedDocument = useMemo(
    () => selectedKnowledgeBaseDocuments.find((item) => item.id === selectedDocumentId) ?? null,
    [selectedDocumentId, selectedKnowledgeBaseDocuments]
  );
  const selectedDocumentChunks = useMemo(
    () => chunksByDocumentId[selectedDocumentId] ?? [],
    [chunksByDocumentId, selectedDocumentId]
  );
  const canUploadDocuments = Boolean(user?.permissions?.includes("admin:kb:write"));
  const latestHitKbCodes = useMemo(() => {
    if (!activeResponse) return [];
    return [...new Set((activeResponse.sources?.length ? activeResponse.sources : activeResponse.citations).map((item) => item.kb_code))];
  }, [activeResponse]);
  const effectiveAllowedKbCodes = useMemo(
    () => (allowedKbCodesFromMe.length > 0 ? allowedKbCodesFromMe : knowledgeBases.map((kb) => kb.code)),
    [allowedKbCodesFromMe, knowledgeBases]
  );
  const localAuditRecords = useMemo(
    () => collectLocalAuditRecords(visibleChatSessions, t.untitledSession),
    [t.untitledSession, visibleChatSessions]
  );
  const activeGraphNodes = useMemo(
    () => graphOverview?.nodes ?? requestGraphTrace?.nodes ?? [],
    [graphOverview?.nodes, requestGraphTrace?.nodes]
  );
  const activeGraphEdges = useMemo(
    () => graphOverview?.edges ?? requestGraphTrace?.edges ?? [],
    [graphOverview?.edges, requestGraphTrace?.edges]
  );
  const positionedGraphNodes = useMemo(() => layoutGraphNodes(activeGraphNodes), [activeGraphNodes]);
  const graphNodeById = useMemo(() => {
    const next = new Map<string, PositionedGraphNode>();
    for (const node of positionedGraphNodes) {
      next.set(node.id, node);
    }
    return next;
  }, [positionedGraphNodes]);
  const selectedGraphNode = selectedGraphNodeId ? graphNodeById.get(selectedGraphNodeId) ?? null : null;
  const permissionMatrixUsers = permissionMatrix?.users ?? [];
  const permissionMatrixKnowledgeBases = permissionMatrix?.knowledge_bases ?? [];
  const selectedMatrixUser = useMemo(
    () =>
      permissionMatrixUsers.find((item) => item.email === selectedMatrixUserEmail) ??
      permissionMatrixUsers[0] ??
      null,
    [permissionMatrixUsers, selectedMatrixUserEmail]
  );
  const blockedMatrixKbCodes = useMemo(() => {
    if (!selectedMatrixUser) return [];
    const allowedCodes = new Set(selectedMatrixUser.allowed_kb_codes);
    return permissionMatrixKnowledgeBases
      .map((item) => item.code)
      .filter((code) => !allowedCodes.has(code));
  }, [permissionMatrixKnowledgeBases, selectedMatrixUser]);
  const formatPermissionKb = (code: string | null | undefined) =>
    localizedCodeLabel(PERMISSION_KB_LABELS, language, code);
  const formatPermissionRole = (code: string | null | undefined) =>
    localizedCodeLabel(PERMISSION_ROLE_LABELS, language, code);
  const formatPermissionDepartment = (code: string | null | undefined) =>
    localizedCodeLabel(PERMISSION_DEPARTMENT_LABELS, language, code);
  const formatPermissionScope = (code: string | null | undefined) =>
    localizedCodeLabel(PERMISSION_SCOPE_LABELS, language, code);

  useEffect(() => {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  }, [language]);

  useEffect(() => {
    let cancelled = false;
    async function restoreSession() {
      const stored = readAuthSession();
      if (!stored) {
        if (!cancelled) setSessionReady(true);
        return;
      }
      if (!cancelled) {
        setPending(true);
        setMessage(UI_TEXT[getInitialLanguage()].restoringSession);
      }
      try {
        const me = await fetchAuthMe(stored.access_token);
        const kbs = await listKnowledgeBases(stored.access_token);
        if (cancelled) return;
        setToken(stored.access_token);
        setUser(me.user);
        setAllowedKbCodesFromMe(me.permission_scope.allowed_kb_codes ?? []);
        setKnowledgeBases(kbs);
        setMessage("");
      } catch {
        clearAuthSession();
        if (cancelled) return;
        setToken("");
        setUser(null);
        setAllowedKbCodesFromMe([]);
        setKnowledgeBases([]);
        setMessage(UI_TEXT[getInitialLanguage()].sessionRestoreFailed);
      } finally {
        if (!cancelled) {
          setPending(false);
          setSessionReady(true);
        }
      }
    }
    void restoreSession();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!user?.email) {
      setHistoryOwnerEmail("");
      setChatSessions([]);
      setActiveSessionId("");
      setKbDocumentCountByKbId({});
      setKbDocumentsByKbId({});
      setChunksByDocumentId({});
      setSelectedKnowledgeBaseId("");
      setSelectedDocumentId("");
      setTraceRequestId("");
      setRequestTrace(null);
      setRequestGraphTrace(null);
      setPermissionMatrix(null);
      setSelectedMatrixUserEmail("");
      setAllowedKbCodesFromMe([]);
      setRetrievalConfig(null);
      setGraphStatus(null);
      setGraphOverview(null);
      setSelectedGraphNodeId("");
      return;
    }
    if (isVisitorIdentity(user.email, user.role)) {
      window.localStorage.removeItem(getChatHistoryStorageKey(user.email));
      const visitorSession = createEmptyChatSession();
      setHistoryOwnerEmail(user.email);
      setChatSessions([visitorSession]);
      setActiveSessionId(visitorSession.id);
      return;
    }
    const storedSessions = readChatSessions(user.email);
    const nextSessions = storedSessions.length > 0 ? storedSessions : [createEmptyChatSession()];
    setHistoryOwnerEmail(user.email);
    setChatSessions(nextSessions);
    setActiveSessionId(nextSessions[0].id);
  }, [user?.email, user?.role]);

  useEffect(() => {
    if (!user?.email || historyOwnerEmail !== user.email) return;
    if (isVisitorIdentity(user.email, user.role)) return;
    saveChatSessions(user.email, chatSessions);
  }, [chatSessions, historyOwnerEmail, user?.email, user?.role]);

  useEffect(() => {
    if (!token) {
      setRetrievalConfig(null);
      return;
    }
    let cancelled = false;
    async function loadRetrievalConfig() {
      try {
        const config = await getRetrievalConfig(token);
        if (!cancelled) setRetrievalConfig(config);
      } catch {
        if (!cancelled) setRetrievalConfig(null);
      }
    }
    void loadRetrievalConfig();
    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    setTraceRequestId(activeResponse?.request_id ?? "");
  }, [activeResponse?.request_id]);

  useEffect(() => {
    if (!token || !traceRequestId) {
      setRequestTrace(null);
      setRequestGraphTrace(null);
      setTracePending(false);
      return;
    }
    let cancelled = false;
    setTracePending(true);
    async function loadTrace() {
      try {
        const [tracePayload, graphPayload] = await Promise.all([
          getRequestTrace(token, traceRequestId),
          getRequestGraphTrace(token, traceRequestId)
        ]);
        if (!cancelled) {
          setRequestTrace(tracePayload);
          setRequestGraphTrace(graphPayload);
        }
      } catch {
        if (!cancelled) {
          setRequestTrace(null);
          setRequestGraphTrace(null);
        }
      } finally {
        if (!cancelled) setTracePending(false);
      }
    }
    void loadTrace();
    return () => {
      cancelled = true;
    };
  }, [token, traceRequestId]);

  useEffect(() => {
    if (!token || !canViewPermissionMatrix || activeView !== "permission_matrix") {
      if (!token || !canViewPermissionMatrix) resetPermissionMatrixState();
      setPermissionMatrixPending(false);
      return;
    }
    let cancelled = false;
    setPermissionMatrixPending(true);
    async function loadPermissionMatrix() {
      try {
        const payload = await listPermissionMatrix(token);
        if (cancelled) return;
        setPermissionMatrix(payload);
        setSelectedMatrixUserEmail((prev) => {
          if (prev && payload.users.some((item) => item.email === prev)) return prev;
          return payload.users[0]?.email ?? "";
        });
      } catch {
        if (cancelled) return;
        setPermissionMatrix(null);
        setSelectedMatrixUserEmail("");
        setMessage(t.permissionMatrixNoPermission);
      } finally {
        if (!cancelled) setPermissionMatrixPending(false);
      }
    }
    void loadPermissionMatrix();
    return () => {
      cancelled = true;
    };
  }, [activeView, canViewPermissionMatrix, t.permissionMatrixNoPermission, token]);

  useEffect(() => {
    if (!token) {
      setGraphStatus(null);
      setGraphOverview(null);
      setGraphPending(false);
      return;
    }
    if (activeView !== "graph_rag") return;
    let cancelled = false;
    setGraphPending(true);
    async function loadGraphData() {
      try {
        const [statusPayload, overviewPayload] = await Promise.all([
          getGraphStatus(token),
          getGraphOverview(token)
        ]);
        if (cancelled) return;
        setGraphStatus(statusPayload);
        setGraphOverview(overviewPayload);
      } catch {
        if (cancelled) return;
        setGraphStatus(null);
        setGraphOverview(null);
      } finally {
        if (!cancelled) setGraphPending(false);
      }
    }
    void loadGraphData();
    return () => {
      cancelled = true;
    };
  }, [activeView, token]);

  useEffect(() => {
    if (!token || activeView !== "knowledge_bases" || knowledgeBases.length === 0) return;
    const missing = knowledgeBases.filter((kb) => kbDocumentCountByKbId[kb.id] === undefined);
    if (missing.length === 0) return;
    let cancelled = false;
    async function loadMissingDocumentCounts() {
      const entries = await Promise.all(
        missing.map(async (kb) => {
          const docs = await listKnowledgeBaseDocuments(token, kb.id);
          return { kbId: kb.id, count: docs.length };
        })
      );
      if (cancelled) return;
      setKbDocumentCountByKbId((prev) => {
        const next = { ...prev };
        for (const entry of entries) {
          next[entry.kbId] = entry.count;
        }
        return next;
      });
    }
    void loadMissingDocumentCounts();
    return () => {
      cancelled = true;
    };
  }, [activeView, kbDocumentCountByKbId, knowledgeBases, token]);

  useEffect(() => {
    if (!selectedGraphNodeId) return;
    if (!graphNodeById.has(selectedGraphNodeId)) {
      setSelectedGraphNodeId("");
    }
  }, [graphNodeById, selectedGraphNodeId]);

  function scrollChatToBottom(behavior: ScrollBehavior = "auto") {
    const container = chatScrollRef.current;
    if (!container) return;
    container.scrollTo({ top: container.scrollHeight, behavior });
  }

  function updateAutoScrollState() {
    const container = chatScrollRef.current;
    if (!container) return;
    const distanceToBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
    shouldAutoScrollRef.current = distanceToBottom < 72;
  }

  useEffect(() => {
    if (activeView !== "knowledge_chat") return;
    shouldAutoScrollRef.current = true;
    scrollChatToBottom("auto");
  }, [activeView, activeSessionId]);

  useEffect(() => {
    if (activeView !== "knowledge_chat") return;
    if (!activeChatSession) return;
    const behavior: ScrollBehavior = activeChatSession.messages.length > 0 ? "smooth" : "auto";
    if (shouldAutoScrollRef.current) {
      scrollChatToBottom(behavior);
    }
  }, [activeView, activeChatSession?.messages.length]);

  const roleProfile = useMemo(() => resolveRoleDisplayProfile(user, language), [language, user]);
  const roleBadgeClass = useMemo(() => roleProfile.badgeClass, [roleProfile.badgeClass]);
  const knowledgeBaseNavLabel = isVisitorUser
    ? language === "zh"
      ? "公开知识库"
      : "Public Knowledge"
    : t.navKnowledgeBases;

  const navItems: NavItem[] = [
    { key: "knowledge_chat", label: t.navKnowledgeChat, icon: ChatIcon },
    { key: "knowledge_bases", label: knowledgeBaseNavLabel, icon: DatabaseIcon },
    ...(canViewAdminViews
      ? [
          { key: "audit_logs" as const, label: t.navAuditLogs, icon: AuditIcon },
          { key: "system_status" as const, label: t.navSystemStatus, icon: SystemIcon },
        ]
      : []),
    ...(canViewPermissionMatrix
      ? [
          { key: "permission_matrix" as const, label: t.navPermissionMatrix, icon: ShieldIcon },
        ]
      : []),
    ...(canViewAdminViews
      ? [
          { key: "developer_trace" as const, label: t.navDeveloperTrace, icon: TraceIcon },
          { key: "graph_rag" as const, label: t.navGraphRag, icon: GraphIcon },
        ]
      : []),
  ];

  useEffect(() => {
    if (activeView === "permission_matrix" && !canViewPermissionMatrix) return;
    if (navItems.some((item) => item.key === activeView)) return;
    setActiveView("knowledge_chat");
  }, [activeView, canViewPermissionMatrix, navItems]);

  function formatBoolean(value: boolean | null | undefined): string {
    if (value === null || value === undefined) return t.noValue;
    return value ? t.yes : t.no;
  }

  function formatCacheState(response: AskResponse | null): string {
    if (!response) return t.cacheNotRequested;
    return response.cache_hit ? t.cacheHit : t.cacheMiss;
  }

  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  }

  function traceStatusClass(status: string): string {
    if (status === "success") return "border-emerald-200 bg-emerald-50 text-emerald-700";
    if (status === "denied") return "border-amber-200 bg-amber-50 text-amber-700";
    if (status === "error") return "border-red-200 bg-red-50 text-red-700";
    return "border-slate-200 bg-slate-100 text-slate-600";
  }

  function formatKbScope(codes: string[] | undefined): string {
    return codes && codes.length > 0 ? codes.join(", ") : t.defaultKbScope;
  }

  function graphTypeLabel(type: GraphNode["type"]): string {
    if (type === "knowledge_base") return t.graphTypeKnowledgeBase;
    if (type === "document") return t.graphTypeDocument;
    if (type === "chunk") return t.graphTypeChunk;
    if (type === "entity") return t.graphTypeEntity;
    if (type === "department") return t.graphTypeDepartment;
    return t.graphTypeTopic;
  }

  function resetAskState() {
    setAuditLogs([]);
    setQuestion("");
    setSelectedKbCodes([]);
  }

  function resetPermissionMatrixState() {
    setPermissionMatrix(null);
    setSelectedMatrixUserEmail("");
    setPermissionMatrixPending(false);
  }

  function applyDemoAccount(account: DemoAccountKey) {
    setSelectedDemoAccount(account);
    if (account === "visitor") return;
    setLoginEmail(DEMO_ACCOUNTS[account].email);
    setLoginPassword(DEMO_ACCOUNTS[account].password);
  }

  function applyAuthenticatedSession(
    accessToken: string,
    nextUser: UserPublic,
    kbs: KnowledgeBase[],
    allowedKbCodes: string[]
  ) {
    resetPermissionMatrixState();
    setToken(accessToken);
    setUser(nextUser);
    setAllowedKbCodesFromMe(allowedKbCodes);
    setKnowledgeBases(kbs);
    saveAuthSession(accessToken, nextUser);
  }

  async function loginByCredentials(loginEmail: string, loginPassword: string) {
    const response = await login(loginEmail, loginPassword);
    const me = await fetchAuthMe(response.access_token);
    const kbs = await listKnowledgeBases(response.access_token);
    const allowedKbCodes = me.permission_scope.allowed_kb_codes ?? [];
    applyAuthenticatedSession(response.access_token, me.user, kbs, allowedKbCodes);
    return { token: response.access_token, user: me.user, kbs, allowedKbCodes };
  }

  function logout() {
    clearAuthSession();
    setToken("");
    setUser(null);
    setAllowedKbCodesFromMe([]);
    setKnowledgeBases([]);
    setKbDocumentsByKbId({});
    setChunksByDocumentId({});
    setSelectedKnowledgeBaseId("");
    setSelectedDocumentId("");
    setTraceRequestId("");
    setRequestTrace(null);
    setRequestGraphTrace(null);
    setPermissionMatrix(null);
    setSelectedMatrixUserEmail("");
    setRetrievalConfig(null);
    setGraphStatus(null);
    setGraphOverview(null);
    setSelectedGraphNodeId("");
    setKbDocumentCountByKbId({});
    setUploadTitle("");
    setUploadFile(null);
    setUploadStatusMessage("");
    setUploadInputVersion(0);
    setReindexPendingDocumentId("");
    setMessage("");
    setHistoryOwnerEmail("");
    setChatSessions([]);
    setActiveSessionId("");
    setActiveView("knowledge_chat");
    if (selectedDemoAccount !== "visitor") {
      setLoginEmail(DEMO_ACCOUNTS[selectedDemoAccount].email);
      setLoginPassword(DEMO_ACCOUNTS[selectedDemoAccount].password);
    }
    resetAskState();
  }

  async function onSubmitLoginForm(event: React.FormEvent) {
    event.preventDefault();
    if (!loginEmail.trim() || !loginPassword.trim()) {
      setMessage(t.loginFailed);
      return;
    }
    setPending(true);
    setMessage("");
    try {
      await loginByCredentials(loginEmail.trim(), loginPassword);
      resetAskState();
      setMessage(t.loginSuccess);
    } catch (error) {
      setMessage(error instanceof Error ? `${t.loginFailed} ${error.message}` : t.loginFailed);
      clearAuthSession();
      setToken("");
      setUser(null);
      setAllowedKbCodesFromMe([]);
      setKnowledgeBases([]);
    } finally {
      setPending(false);
    }
  }

  async function loginWithDemoAccount(accountKey: DemoAccountKey) {
    const account = DEMO_ACCOUNTS[accountKey];
    setPending(true);
    setMessage("");
    setSelectedDemoAccount(accountKey);
    if (accountKey === "visitor") {
      window.localStorage.removeItem(getChatHistoryStorageKey(account.email));
      clearAuthSession();
    }
    try {
      await loginByCredentials(account.email, account.password);
      resetAskState();
      setMessage(t.loginSuccess);
    } catch (error) {
      setMessage(error instanceof Error ? `${t.loginFailed} ${error.message}` : t.loginFailed);
      clearAuthSession();
      setToken("");
      setUser(null);
      setAllowedKbCodesFromMe([]);
      setKnowledgeBases([]);
    } finally {
      setPending(false);
    }
  }

  function appendUserMessageToActiveSession(userMessage: ChatMessage): string {
    const existingSession = visibleChatSessions.find((session) => session.id === activeSessionId);
    const targetSession = existingSession ?? createEmptyChatSession(trimSessionTitle(userMessage.content));
    const targetId = targetSession.id;

    setActiveSessionId(targetId);
    setChatSessions((prev) => {
      const source = prev.some((session) => session.id === targetId) ? prev : [targetSession, ...prev];
      return sortSessions(
        source.map((session) =>
          session.id === targetId
            ? {
                ...session,
                title: session.title || trimSessionTitle(userMessage.content),
                updatedAt: userMessage.createdAt,
                messages: [...session.messages, userMessage]
              }
            : session
        )
      ).slice(0, MAX_STORED_SESSIONS);
    });
    return targetId;
  }

  function appendAssistantMessageToSession(sessionId: string, assistantMessage: ChatMessage) {
    setChatSessions((prev) =>
      sortSessions(
        prev.map((session) =>
          session.id === sessionId
            ? {
                ...session,
                updatedAt: assistantMessage.createdAt,
                messages: [...session.messages, assistantMessage]
              }
            : session
        )
      ).slice(0, MAX_STORED_SESSIONS)
    );
  }

  async function requestAnswer(
    nextToken: string,
    nextQuestion: string,
    nextMode: AskMode,
    kbCodes: string[]
  ): Promise<{ response: AskResponse; detail: AuditLog | null }> {
    const response = await askQuestion(nextToken, nextQuestion.trim(), nextMode, kbCodes);
    let detail: AuditLog | null = null;
    try {
      detail = await getRequestDetail(nextToken, response.request_id);
    } catch {
      setMessage(t.auditDetailLoadFailed);
    }
    return { response, detail };
  }

  function responseStatusMessage(response: AskResponse): string {
    if (response.denied) return `${t.requestDeniedPrefix}: ${response.refusal_reason ?? "forbidden"}`;
    return response.cache_hit ? t.answerServedFromCache : t.answerGenerated;
  }

  async function onAsk(event: React.FormEvent) {
    event.preventDefault();
    const nextQuestion = question.trim();
    if (!token || !nextQuestion || !user) return;

    const kbCodes = [...selectedKbCodes];
    const askMode = mode;
    const userMessage = buildUserMessage(nextQuestion, askMode, kbCodes);
    const targetSessionId = appendUserMessageToActiveSession(userMessage);

    setPending(true);
    setQuestion("");
    setMessage("");
    try {
      const { response, detail } = await requestAnswer(token, nextQuestion, askMode, kbCodes);
      appendAssistantMessageToSession(
        targetSessionId,
        buildAssistantMessage(response, detail, t.requestDeniedPrefix)
      );
      setMessage(responseStatusMessage(response));
    } catch (error) {
      const errorText = error instanceof Error ? `${t.askFailed} ${error.message}` : t.askFailed;
      appendAssistantMessageToSession(targetSessionId, buildErrorAssistantMessage(errorText));
      setMessage(errorText);
    } finally {
      setPending(false);
    }
  }

  function startNewSession() {
    const nextSession = createEmptyChatSession();
    setChatSessions((prev) =>
      [nextSession, ...prev.filter((session) => session.messages.length > 0)].slice(0, MAX_STORED_SESSIONS)
    );
    setActiveSessionId(nextSession.id);
    setQuestion("");
    setSelectedKbCodes([]);
    setMessage(t.newSessionReady);
  }

  function clearCurrentSession() {
    if (!activeChatSession) return;
    const now = new Date().toISOString();
    setChatSessions((prev) =>
      prev.map((session) =>
        session.id === activeChatSession.id
          ? {
              ...session,
              title: "",
              updatedAt: now,
              messages: []
            }
          : session
      )
    );
    setQuestion("");
    setSelectedKbCodes([]);
    setMessage(t.clearSessionDone);
  }

  function selectChatSession(sessionId: string) {
    setActiveSessionId(sessionId);
    setActiveView("knowledge_chat");
    setMessage("");
  }

  async function runOverreachScenario(scenario: (typeof OVERREACH_SCENARIOS)[number]) {
    setPending(true);
    setMessage("");
    try {
      applyDemoAccount(scenario.account);
      const account = DEMO_ACCOUNTS[scenario.account];
      const session = await loginByCredentials(account.email, account.password);
      const { response, detail } = await requestAnswer(session.token, scenario.question, "auto", []);
      const scenarioUserMessage = buildUserMessage(scenario.question, "auto", []);
      const scenarioAssistantMessage = buildAssistantMessage(response, detail, t.requestDeniedPrefix);
      const scenarioSession = createEmptyChatSession(trimSessionTitle(scenario.question));
      scenarioSession.updatedAt = scenarioAssistantMessage.createdAt;
      scenarioSession.messages = [scenarioUserMessage, scenarioAssistantMessage];

      const nextSessions = sortSessions([
        scenarioSession,
        ...readChatSessions(session.user.email).filter((item) => item.messages.length > 0)
      ]).slice(0, MAX_STORED_SESSIONS);

      saveChatSessions(session.user.email, nextSessions);
      setHistoryOwnerEmail(session.user.email);
      setChatSessions(nextSessions);
      setActiveSessionId(scenarioSession.id);
      setActiveView("developer_trace");
      setQuestion("");
      setMode("auto");
      setSelectedKbCodes([]);
      setMessage(`${t.scenarioExecutedPrefix}: ${overreachLabels[scenario.id] ?? scenario.id}`);
    } catch (error) {
      setMessage(
        error instanceof Error
          ? `${t.scenarioExecutionFailed} ${error.message}`
          : t.scenarioExecutionFailed
      );
    } finally {
      setPending(false);
    }
  }

  async function onLoadAdminAudit() {
    if (!token) return;
    setPending(true);
    setMessage("");
    try {
      const rows = await listAuditLogs(token);
      setAuditLogs(rows);
      setMessage(`${t.loadedAuditLogsPrefix}: ${rows.length}`);
    } catch (error) {
      setMessage(
        error instanceof Error ? `${t.loadAuditLogsFailed} ${error.message}` : t.loadAuditLogsFailed
      );
    } finally {
      setPending(false);
    }
  }

  async function refreshGraphData(nextToken: string) {
    const [statusPayload, overviewPayload] = await Promise.all([
      getGraphStatus(nextToken),
      getGraphOverview(nextToken)
    ]);
    setGraphStatus(statusPayload);
    setGraphOverview(overviewPayload);
  }

  function toggleKb(code: string) {
    setSelectedKbCodes((prev) =>
      prev.includes(code) ? prev.filter((item) => item !== code) : [...prev, code]
    );
  }

  async function refreshKnowledgeBaseDocuments(kbId: string) {
    if (!token) return [];
    const documents = await listKnowledgeBaseDocuments(token, kbId);
    setKbDocumentsByKbId((prev) => ({ ...prev, [kbId]: documents }));
    return documents;
  }

  async function onSelectKnowledgeBase(kbId: string) {
    if (!token) return;
    setSelectedKnowledgeBaseId(kbId);
    setSelectedDocumentId("");
    setUploadStatusMessage("");
    setUploadTitle("");
    setUploadFile(null);
    setReindexPendingDocumentId("");
    setUploadInputVersion((prev) => prev + 1);
    if (kbDocumentsByKbId[kbId]) return;
    setViewerPending(true);
    try {
      await refreshKnowledgeBaseDocuments(kbId);
    } catch (error) {
      setMessage(
        error instanceof Error ? `${t.askFailed} ${error.message}` : t.askFailed
      );
    } finally {
      setViewerPending(false);
    }
  }

  async function onSelectDocument(documentId: string) {
    if (!token) return;
    setSelectedDocumentId(documentId);
    if (chunksByDocumentId[documentId]) return;
    setViewerPending(true);
    try {
      const chunks = await listDocumentChunks(token, documentId);
      setChunksByDocumentId((prev) => ({ ...prev, [documentId]: chunks }));
    } catch (error) {
      setMessage(
        error instanceof Error ? `${t.askFailed} ${error.message}` : t.askFailed
      );
    } finally {
      setViewerPending(false);
    }
  }

  async function onUploadDocument(event: React.FormEvent) {
    event.preventDefault();
    if (!token || !selectedKnowledgeBase || !uploadFile) return;
    setUploadPending(true);
    setUploadStatusMessage("");
    try {
      const result = await uploadKnowledgeBaseDocument(
        token,
        selectedKnowledgeBase.id,
        uploadFile,
        uploadTitle
      );
      setUploadStatusMessage(
        `${t.uploadSuccessPrefix}: ${result.filename} (${result.chunk_count} chunks)`
      );
      setUploadTitle("");
      setUploadFile(null);
      setUploadInputVersion((prev) => prev + 1);
      const nextKnowledgeBases = await listKnowledgeBases(token);
      setKnowledgeBases(nextKnowledgeBases);
      await refreshKnowledgeBaseDocuments(selectedKnowledgeBase.id);
      if (activeView === "graph_rag") {
        await refreshGraphData(token);
      }
      setChunksByDocumentId((prev) => {
        const next = { ...prev };
        delete next[result.document_id];
        return next;
      });
      await onSelectDocument(result.document_id);
    } catch (error) {
      setUploadStatusMessage(
        error instanceof Error ? `${t.uploadFailedPrefix} ${error.message}` : t.uploadFailedPrefix
      );
    } finally {
      setUploadPending(false);
    }
  }

  async function onReindexDocument(documentId: string) {
    if (!token || !selectedKnowledgeBase) return;
    setReindexPendingDocumentId(documentId);
    setUploadStatusMessage("");
    try {
      const result = await reindexDocument(token, documentId);
      setUploadStatusMessage(
        `${t.reindexSuccessPrefix}: ${result.filename} (${result.chunk_count} chunks)`
      );
      const nextKnowledgeBases = await listKnowledgeBases(token);
      setKnowledgeBases(nextKnowledgeBases);
      await refreshKnowledgeBaseDocuments(selectedKnowledgeBase.id);
      if (activeView === "graph_rag") {
        await refreshGraphData(token);
      }
      setChunksByDocumentId((prev) => {
        const next = { ...prev };
        delete next[documentId];
        return next;
      });
      if (selectedDocumentId === documentId) {
        await onSelectDocument(documentId);
      }
    } catch (error) {
      setUploadStatusMessage(
        error instanceof Error ? `${t.reindexFailedPrefix} ${error.message}` : t.reindexFailedPrefix
      );
    } finally {
      setReindexPendingDocumentId("");
    }
  }

  function openTraceView(requestId: string) {
    setTraceRequestId(requestId);
    setActiveView("developer_trace");
  }

  function openGraphView(requestId: string) {
    setTraceRequestId(requestId);
    setActiveView("graph_rag");
  }

  async function onSyncGraph() {
    if (!token) return;
    setGraphSyncPending(true);
    setMessage("");
    try {
      await syncGraph(token);
      await refreshGraphData(token);
      setMessage(`${t.graphSyncStatus}: success`);
    } catch (error) {
      setMessage(error instanceof Error ? `${t.askFailed} ${error.message}` : t.askFailed);
    } finally {
      setGraphSyncPending(false);
    }
  }

  if (!sessionReady) {
    return (
      <div className="console-root min-h-screen bg-[#0f141b]">
        <div className="mx-auto flex min-h-screen max-w-5xl items-center justify-center px-6">
          <div className="console-shell w-full max-w-2xl p-3">
            <div className="console-statusbar mb-3">
              <div className="console-statusbar-left">GRAPHRAG OS v0.9.3</div>
              <div className="console-statusbar-mid">///////////////</div>
              <div className="console-statusbar-right">SYSTEM ONLINE</div>
            </div>
            <div className="glass-panel px-6 py-5 text-sm text-[#3b352d]">{message || t.restoringSession}</div>
          </div>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="console-root h-screen overflow-hidden bg-[#0f141b]">
        <div className="mx-auto flex h-full w-full max-w-[1260px] items-center px-3 py-3 md:px-6 md:py-4">
          <div className="console-shell flex h-full w-full flex-col p-3 md:p-4">
            <div className="console-statusbar mb-2">
              <div className="console-statusbar-left">GRAPHRAG OS v0.9.3</div>
              <div className="console-statusbar-mid">/////////////////////////</div>
              <div className="console-statusbar-right">SYSTEM ONLINE</div>
            </div>

            <div className="flex min-h-0 flex-1 flex-col">
              <div className="mb-2 flex items-center justify-end gap-2">
                <label className="text-xs text-slate-600" htmlFor="login-language-select">
                  {t.language}
                </label>
                <select
                  id="login-language-select"
                  className="h-8 rounded-sm border border-[#3e382f] bg-[#f7f0e4] px-2 text-xs text-[#25211c]"
                  value={language}
                  onChange={(event) => setLanguage(event.target.value as Language)}
                >
                  <option value="zh">{t.chinese}</option>
                  <option value="en">{t.english}</option>
                </select>
              </div>

              <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[1.06fr_0.94fr]">
                <section className="glass-panel flex min-h-0 flex-col p-5 md:p-6">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">
                    {t.consoleLabel}
                  </div>
                  <h1 className="mt-1 text-xl font-semibold tracking-tight text-slate-900 md:text-2xl">
                    {t.productName}
                  </h1>
                  <p className="mt-1.5 text-sm text-slate-600">{t.loginPageTagline}</p>
                  <div className="mt-3 rounded-sm border border-slate-200 bg-slate-50 p-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-600">
                      {t.capabilityTitle}
                    </p>
                    <ul className="mt-2 space-y-1.5 text-sm text-slate-700">
                      <li>{t.capabilityA}</li>
                      <li>{t.capabilityB}</li>
                      <li>{t.capabilityC}</li>
                    </ul>
                  </div>
                  <div className="mt-3 rounded-sm border border-[#4a4338] bg-[#f4ebdd] p-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#3b342d]">
                      {t.loginBoundaryTitle}
                    </p>
                    <ul className="mt-2 space-y-1.5 text-sm text-[#363029]">
                      <li>{t.loginBoundaryLine1}</li>
                      <li>{t.loginBoundaryLine2}</li>
                      <li>{t.loginBoundaryLine3}</li>
                    </ul>
                  </div>
                </section>

                <section className="glass-panel flex min-h-0 flex-col p-5 md:p-6">
                  <h2 className="panel-title">{t.signInPanelTitle}</h2>
                  <section className="mt-2 rounded-sm border border-[#474035] bg-[#f2e8d8] p-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-semibold text-[#2f2a23]">{t.employeeAdminDemoTitle}</span>
                      <span className="text-[11px] text-[#5a5247]">{t.employeeAdminDemoHint}</span>
                    </div>
                    <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-4">
                      {STAFF_ADMIN_ACCOUNT_KEYS.map((key) => {
                        const account = DEMO_ACCOUNTS[key];
                        const isSelected = selectedDemoAccount === key;
                        const fillLabel =
                          key === "tech_staff"
                            ? t.fillTechStaffDemo
                            : key === "sales_staff"
                              ? t.fillSalesStaffDemo
                              : key === "marketing_staff"
                                ? t.fillMarketingStaffDemo
                                : key === "support_staff"
                                  ? t.fillSupportStaffDemo
                                  : key === "hr_staff"
                                    ? t.fillHrStaffDemo
                                    : key === "admin_staff"
                                      ? t.fillAdminStaffDemo
                                      : key === "product_staff"
                                        ? t.fillProductStaffDemo
                                        : t.fillBilingualAdminDemo;
                        return (
                          <div
                            key={key}
                            className={`rounded-sm border px-2 py-2 ${
                              isSelected
                                ? "border-[#bf6925] bg-[#f3dec4]"
                                : "border-[#4a4338] bg-[#f6eee1]"
                            }`}
                          >
                            <button
                              type="button"
                              className="w-full text-left"
                              onClick={() => applyDemoAccount(key)}
                            >
                              <div className="font-mono text-[11px] font-semibold text-[#1f1c18]">{account.label}</div>
                            </button>
                            <button
                              type="button"
                              className="mt-1 w-full rounded-sm border border-[#6e6253] bg-[#f7efe2] px-2 py-1 text-[11px] text-[#3a332b] transition hover:border-[#bf6925] hover:text-[#6b360e]"
                              onClick={() => applyDemoAccount(key)}
                            >
                              {fillLabel}
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  </section>

                  <form
                    className="mt-2 rounded-sm border border-[#474035] bg-[#efe4d3] p-3 space-y-2"
                    onSubmit={onSubmitLoginForm}
                  >
                    <div className="grid gap-2 md:grid-cols-2">
                      <label className="block space-y-1">
                        <span className="text-xs text-[#4f483e]">{t.email}</span>
                        <input
                          className="field h-8"
                          autoComplete="username"
                          value={loginEmail}
                          onChange={(event) => setLoginEmail(event.target.value)}
                          placeholder="name@example.local"
                        />
                      </label>
                      <label className="block space-y-1">
                        <span className="text-xs text-[#4f483e]">{t.password}</span>
                        <input
                          className="field h-8"
                          type="password"
                          autoComplete="current-password"
                          value={loginPassword}
                          onChange={(event) => setLoginPassword(event.target.value)}
                        />
                      </label>
                    </div>
                    <button
                      className="btn-primary w-full"
                      type="submit"
                      disabled={pending || !loginEmail.trim() || !loginPassword.trim()}
                    >
                      {pending ? t.working : t.signIn}
                    </button>
                    <p className="text-xs text-[#4d463d]">{t.localDemoAccountNotice}</p>
                    <p className="text-xs text-[#4d463d]">{t.demoPasswordNotice}</p>
                  </form>

                  <section className="mt-2 rounded-sm border border-[#474035] bg-[#efe4d3] p-3">
                    <div className="text-xs font-semibold uppercase tracking-[0.1em] text-[#3b352e]">
                      {t.guestModeTitle}
                    </div>
                    <div className="mt-1 rounded-sm border border-[#61584d] bg-[#f7efe1] px-2.5 py-1.5 text-sm text-[#312c25]">
                      {t.guestModeBadge}
                    </div>
                    <p className="mt-1.5 text-xs text-[#4f483e]">{t.guestModeDescriptionLine1}</p>
                    <p className="mt-1 text-xs text-[#4f483e]">{t.guestModeDescriptionLine2}</p>
                    <button
                      className="btn-primary mt-2 w-full"
                      type="button"
                      disabled={pending}
                      onClick={() => loginWithDemoAccount("visitor")}
                    >
                      {pending && selectedDemoAccount === "visitor" ? t.working : t.enterGuestMode}
                    </button>
                  </section>

                  {message ? <div className="mt-2 notification-line">{message}</div> : <div className="mt-2 h-5" />}
                </section>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="console-root min-h-screen text-slate-900">
      <div className="console-shell mx-auto w-full max-w-[1880px] p-3 md:p-4">
        <div className="console-statusbar mb-2">
            <div className="console-statusbar-left">GRAPHRAG OS v0.9.3</div>
          <div className="console-statusbar-mid" aria-hidden="true">
            /////////////////////////
          </div>
          <div className="console-statusbar-right">SYSTEM ONLINE</div>
        </div>

        <header className="glass-panel mb-3 px-5 py-4 md:px-7">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex min-w-0 items-start gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-md border border-[#4d4438] bg-[#efe4d2] text-[#a35218]">
                <BrandGraphIcon className="h-6 w-6" />
              </div>
              <div className="min-w-0">
                <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#6a6358]">
                  {t.consoleLabel}
                </div>
                <h1 className="text-xl font-semibold tracking-[0.02em] text-[#171614] md:text-[2.05rem]">
                  {t.productName}
                </h1>
                <p className="mt-1 text-sm text-[#3e3a34]">{t.subtitle}</p>
              </div>
            </div>

            <div className="flex w-full min-w-0 flex-wrap items-center justify-start gap-2 sm:w-auto sm:justify-end">
              <label
                className="inline-flex items-center gap-2 rounded-md border border-[#3d3831] bg-[#f4ede0] px-3 py-2 text-xs font-semibold text-[#1f1d1a]"
                htmlFor="ui-language-select"
              >
                <GlobeIcon className="h-4 w-4 text-[#2e2b26]" />
                {t.language}
                <select
                  id="ui-language-select"
                  className="bg-transparent text-xs text-[#1f1d1a] outline-none"
                  value={language}
                  onChange={(event) => setLanguage(event.target.value as Language)}
                >
                  <option value="zh">{t.chinese}</option>
                  <option value="en">{t.english}</option>
                </select>
              </label>

              <div className={`status-pill inline-flex min-w-0 max-w-full items-center gap-1.5 truncate sm:max-w-[340px] ${roleBadgeClass}`}>
                <UserIcon className="h-4 w-4" />
                <span className="truncate">
                  {user ? `${user.email} · ${roleProfile.displayRole} · ${roleProfile.displayDepartment}` : t.accountState}
                </span>
              </div>

              <button className="btn-secondary gap-1.5" onClick={logout} type="button">
                <LogoutIcon className="h-4 w-4" />
                {t.logout}
              </button>
            </div>
          </div>
        </header>

        <div className="grid gap-3 xl:grid-cols-[290px_minmax(0,1fr)]">
          <aside className="space-y-4">
            <section className="glass-panel p-6">
              <h2 className="panel-title">{t.navTitle}</h2>
              <div className="space-y-2">
                {navItems.map((item) => {
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.key}
                      className={`group flex w-full items-center gap-2.5 rounded-sm border px-3 py-2.5 text-left text-[15px] font-semibold transition ${
                        activeView === item.key
                          ? "border-[#c56f24] bg-[#f3dcbf] text-[#7c3f0f]"
                          : "border-[#4a4338] bg-[#f4ede0] text-[#2a2722] hover:border-[#c56f24] hover:bg-[#f0dfca]"
                      }`}
                      onClick={() => setActiveView(item.key)}
                      type="button"
                    >
                      <Icon
                        className={`h-[18px] w-[18px] shrink-0 ${
                          activeView === item.key ? "text-accent-600" : "text-slate-500"
                        }`}
                      />
                      <span>{item.label}</span>
                    </button>
                  );
                })}
              </div>
            </section>

            <section className={`glass-panel p-6 ${roleProfile.sessionPanelClass}`}>
              <h2 className="panel-title">{t.currentSession}</h2>
              <div className="space-y-3 text-sm text-slate-700">
                <div className="flex items-start gap-2.5">
                  <MailIcon className="mt-0.5 h-[17px] w-[17px] shrink-0 text-slate-500" />
                  <div>
                    <div className="text-xs text-slate-500">{t.currentUser}</div>
                    <div className="font-mono text-xs text-slate-800">{user?.email ?? t.noValue}</div>
                  </div>
                </div>
                <div className="flex items-start gap-2.5">
                  <ShieldIcon className="mt-0.5 h-[17px] w-[17px] shrink-0 text-slate-500" />
                  <div>
                    <div className="text-xs text-slate-500">{t.currentRole}</div>
                    <div className="font-medium text-slate-800">{roleProfile.displayRole}</div>
                  </div>
                </div>
                <div className="flex items-start gap-2.5">
                  <BuildingIcon className="mt-0.5 h-[17px] w-[17px] shrink-0 text-slate-500" />
                  <div>
                    <div className="text-xs text-slate-500">{t.currentDepartment}</div>
                    <div className="font-medium text-slate-800">{roleProfile.displayDepartment}</div>
                  </div>
                </div>
                <div className="flex items-start gap-2.5">
                  <DatabaseIcon className="mt-0.5 h-[17px] w-[17px] shrink-0 text-slate-500" />
                  <div>
                    <div className="text-xs text-slate-500">{t.allowedScopeHint}</div>
                    <div className="font-mono text-xs text-slate-800">
                      {effectiveAllowedKbCodes.join(", ") || t.noValue}
                    </div>
                  </div>
                </div>
              </div>
              <div className="mt-3 rounded-sm border border-[#4a4338] bg-[#f9f4eb] px-2.5 py-2 text-xs text-[#44403a]">
                {roleProfile.hint}
              </div>
            </section>
          </aside>

          <main className="min-w-0 space-y-4">
            {activeView === "knowledge_chat" ? (
              <section className="glass-panel overflow-hidden">
                <div className="grid gap-0 xl:grid-cols-[340px_minmax(0,1fr)]">
                  <div className="border-b border-[#34312c] bg-[#f2ece2] p-4 xl:border-b-0 xl:border-r">
                    <div className="mb-3 flex items-center justify-between gap-2">
                      <h2 className="panel-title mb-0">{t.recentSessions}</h2>
                      <button className="btn-secondary px-2.5 py-1.5 text-xs" onClick={startNewSession} type="button">
                        <PlusIcon className="h-3.5 w-3.5" />
                        {t.newSession}
                      </button>
                    </div>

                    <div className="scroll-area max-h-[420px] space-y-2 overflow-y-auto pr-1">
                      {visibleChatSessions.length === 0 ? (
                        <p className="rounded-sm border border-dashed border-[#5f584f] bg-[#f7f1e5] px-3 py-4 text-sm text-[#4a443c]">
                          {t.noRecentSessions}
                        </p>
                      ) : (
                        visibleChatSessions.map((session) => {
                          const isActive = activeChatSession?.id === session.id;
                          return (
                            <button
                              key={session.id}
                              className={`w-full rounded-sm border px-3 py-3 text-left transition ${
                                isActive
                                  ? "border-[#c56f24] bg-[#f4dcc0]"
                                  : "border-[#4b4439] bg-[#f8f3e8] hover:border-[#c56f24] hover:bg-[#f2e7d6]"
                              }`}
                              onClick={() => selectChatSession(session.id)}
                              type="button"
                            >
                              <div className="truncate text-sm font-semibold text-slate-800">
                                {getSessionTitle(session, t.untitledSession)}
                              </div>
                              <div className="mt-1 text-[11px] text-slate-500">
                                {formatDateTime(session.updatedAt, language)} · {session.messages.length}
                              </div>
                            </button>
                          );
                        })
                      )}
                    </div>

                    <button
                      className="btn-secondary mt-3 w-full"
                      disabled={!activeChatSession || activeChatSession.messages.length === 0}
                      onClick={clearCurrentSession}
                      type="button"
                    >
                      <TrashIcon className="h-4 w-4" />
                      {t.clearCurrentSession}
                    </button>
                    <p className="mt-2 text-[11px] text-[#5e5850]">{t.historyStoredLocally}</p>

                    <div className={`mt-4 rounded-sm border p-3 ${roleProfile.scopePanelClass}`}>
                      <p className="mb-2 text-sm font-semibold text-[#211f1b]">{t.kbScopeOptional}</p>
                      <div className="flex flex-wrap gap-2">
                        {knowledgeBases.map((kb) => (
                          <label key={kb.id} className="tag-check">
                            <input
                              type="checkbox"
                              checked={selectedKbCodes.includes(kb.code)}
                              onChange={() => toggleKb(kb.code)}
                            />
                            <span className={`${canViewTechnicalFields ? "font-mono" : ""} text-xs`}>
                              {canViewTechnicalFields ? kb.code : kb.display_name || kb.name}
                            </span>
                          </label>
                        ))}
                      </div>
                      <div className="mt-2 rounded-sm border border-[#5a5348] bg-[#f9f4ea] px-2 py-1.5 text-[11px] text-[#4a463f]">
                        {roleProfile.hint}
                      </div>
                      <p className="mt-2 text-[11px] text-[#5c554c]">{t.allowedKbHint}</p>
                    </div>
                  </div>

                  <div className="flex h-[72vh] min-h-[580px] max-h-[860px] flex-col bg-[#f6f0e5] md:h-[calc(100vh-220px)]">
                    <div className="border-b border-[#34312c] px-5 py-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="flex items-start gap-2.5">
                          <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-sm border border-[#5a5146] bg-[#efd8b8] text-[#8a4a16]">
                            <ChatIcon className="h-[17px] w-[17px]" />
                          </div>
                          <div>
                            <h2 className="text-base font-semibold text-[#1b1916]">{t.askQuestionSection}</h2>
                            <p className="mt-1 text-xs text-[#5b544a]">{t.chatPageDescription}</p>
                          </div>
                        </div>
                        <div className={`risk-badge ${deniedThisRequest ? "is-risk" : "is-normal"}`}>
                          {deniedThisRequest ? t.riskAlert : t.normalState}
                        </div>
                      </div>
                    </div>

                    <div
                      ref={chatScrollRef}
                      onScroll={updateAutoScrollState}
                      className="scroll-area console-chat-scroll min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-5 md:px-6"
                    >
                      {!activeChatSession || activeChatSession.messages.length === 0 ? (
                        <div className="flex min-h-[350px] flex-col items-center justify-center gap-3 text-center">
                          <div className="flex h-16 w-16 items-center justify-center rounded-sm border border-[#5a5146] bg-[#efdcc1] text-[#8a4a16]">
                            <ChatIcon className="h-8 w-8" />
                          </div>
                          <div>
                            <p className="text-xl font-semibold text-[#1c1915]">开始向企业知识库提问吧</p>
                            <p className="mt-1 text-sm text-[#595249]">{t.emptyConversation}</p>
                          </div>
                        </div>
                      ) : (
                        activeChatSession.messages.map((chatMessage) => {
                          const isUserMessage = chatMessage.role === "user";
                          return (
                            <div key={chatMessage.id} className={`flex ${isUserMessage ? "justify-end" : "justify-start"}`}>
                              <article
                                className={`max-w-[90%] rounded-sm border px-4 py-3 md:max-w-[80%] ${
                                  isUserMessage
                                    ? "border-[#8a4a16] bg-[#e8aa5d] text-[#24150a]"
                                    : chatMessage.error
                                      ? "border-[#b33b2e] bg-[#f8d8d4] text-[#7e2018]"
                                      : "border-[#413b32] bg-[#f7f0e3] text-[#221f19]"
                                }`}
                              >
                                <div
                                  className={`mb-2 flex flex-wrap items-center gap-2 text-[11px] ${
                                    isUserMessage ? "text-[#47260a]" : "text-[#575047]"
                                  }`}
                                >
                                  <span className="font-semibold">
                                    {isUserMessage ? t.userMessageLabel : t.assistantMessageLabel}
                                  </span>
                                  <span>{formatDateTime(chatMessage.createdAt, language)}</span>
                                  {chatMessage.mode ? <span className="font-mono">{chatMessage.mode}</span> : null}
                                </div>
                                <div className="whitespace-pre-wrap break-words text-sm leading-6">{chatMessage.content}</div>

                                {isUserMessage ? (
                                  <div className="mt-2 text-[11px] text-accent-50">
                                    {t.selectedKbScope}: {formatKbScope(chatMessage.kbCodes)}
                                  </div>
                                ) : null}

                                {chatMessage.response?.denied ? (
                                  <div className="mt-3 rounded-sm border border-[#ba3f2f] bg-[#f7dbd8] px-3 py-2 text-sm text-[#7d271f]">
                                    <div className="text-[11px] font-semibold uppercase tracking-wide">{t.riskAlert}</div>
                                    <div className="mt-1">{chatMessage.response.refusal_reason ?? t.requestDeniedPrefix}</div>
                                  </div>
                                ) : null}

                                {chatMessage.response &&
                                (chatMessage.response.sources?.length > 0 || chatMessage.response.citations.length > 0) ? (
                                  <div className="mt-3 border-t border-[#494238] pt-3">
                                    <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-[#5b5448]">
                                      {t.citations}
                                    </p>
                                    <div className="space-y-2">
                                      {(chatMessage.response.sources?.length
                                        ? chatMessage.response.sources
                                        : chatMessage.response.citations
                                      ).map((item) => (
                                        <div
                                          key={`${item.kb_code}::${item.document_title}`}
                                          className="rounded-sm border border-[#5c5448] bg-[#f2e7d7] px-3 py-2"
                                        >
                                          <div className="text-[11px] text-[#302c26]">{`${item.kb_name} / ${item.document_title}`}</div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                ) : null}

                                {chatMessage.response ? (
                                  <div className="mt-3 space-y-2">
                                    {canViewAdminViews ? (
                                      <div className="flex flex-wrap gap-2">
                                        <button
                                          className="btn-secondary px-2 py-1 text-xs font-semibold"
                                          type="button"
                                          onClick={() => openTraceView(chatMessage.response!.request_id)}
                                        >
                                          {t.traceViewAction}
                                        </button>
                                        {chatMessage.response.graph_paths.length > 0 ? (
                                          <button
                                            className="btn-secondary px-2 py-1 text-xs font-semibold"
                                            type="button"
                                            onClick={() => openGraphView(chatMessage.response!.request_id)}
                                          >
                                            {t.traceViewGraphAction}
                                          </button>
                                        ) : null}
                                      </div>
                                    ) : null}
                                  </div>
                                ) : null}
                              </article>
                            </div>
                          );
                        })
                      )}
                    </div>

                    <form className="shrink-0 border-t border-[#34312c] bg-[#efe8db] p-4" onSubmit={onAsk}>
                      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_228px]">
                        <div className="relative">
                          <textarea
                            className="soft-textarea min-h-24 bg-white pr-12"
                            value={question}
                            onChange={(event) => setQuestion(event.target.value)}
                            placeholder={t.askQuestionPlaceholder}
                          />
                          <button
                            type="button"
                            className="absolute bottom-3 right-3 rounded-sm border border-transparent p-1.5 text-[#4f493f] transition hover:border-[#6a6256] hover:bg-[#f6edde] hover:text-[#2f2a23]"
                            aria-label="voice placeholder"
                          >
                            <MicIcon className="h-5 w-5" />
                          </button>
                        </div>
                        <div className="space-y-2">
                          <label className="block space-y-1">
                            <span className="text-xs font-semibold text-[#3f3a33]">{t.mode}</span>
                            <select
                              className="field"
                              value={mode}
                              onChange={(event) => setMode(event.target.value as AskMode)}
                            >
                              <option value="auto">auto</option>
                              <option value="rag">rag</option>
                              <option value="graphrag">graphrag</option>
                            </select>
                          </label>
                          <button className="btn-primary w-full" disabled={!token || pending || !question.trim()}>
                            <SendIcon className="h-4 w-4" />
                            {pending ? t.working : t.sendQuestion}
                          </button>
                        </div>
                      </div>
                    </form>

                    {message ? <div className="border-t border-[#34312c] px-4 py-3 notification-line">{message}</div> : null}
                  </div>
                </div>
              </section>
            ) : null}

            {activeView === "knowledge_bases" ? (
              <section className="glass-panel p-6">
                <h2 className="panel-title">{t.knowledgeBasesPageTitle}</h2>
                <p className="mb-4 text-sm text-slate-600">{t.knowledgeBasesPageHint}</p>
                <p className="mb-4 text-xs text-slate-500">{t.allowedScopeHint}</p>

                <div className="grid gap-4 xl:grid-cols-[minmax(0,520px)_minmax(0,1fr)]">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                    <div className="overflow-x-auto">
                      <table className="w-full border-collapse text-left text-sm">
                        <thead>
                          <tr className="border-b border-slate-200 text-slate-600">
                            {canViewTechnicalFields ? <th className="px-2 py-2">kb_id</th> : null}
                            {canViewTechnicalFields ? <th className="px-2 py-2">{t.knowledgeBaseCode}</th> : null}
                            <th className="px-2 py-2">{t.kbDisplayName}</th>
                            <th className="px-2 py-2">{t.kbDescription}</th>
                            <th className="px-2 py-2">{t.kbLanguage}</th>
                            <th className="px-2 py-2">{t.kbDepartment}</th>
                            <th className="px-2 py-2">{t.documentCountLabel}</th>
                            <th className="px-2 py-2"></th>
                          </tr>
                        </thead>
                        <tbody>
                          {knowledgeBases.map((kb) => {
                            const selected = selectedKnowledgeBaseId === kb.id;
                            return (
                              <tr key={kb.id} className={`border-b border-slate-100 ${selected ? "bg-white" : ""}`}>
                                {canViewTechnicalFields ? <td className="px-2 py-2 font-mono text-xs">{kb.id}</td> : null}
                                {canViewTechnicalFields ? <td className="px-2 py-2 font-mono text-xs">{kb.code}</td> : null}
                                <td className="px-2 py-2">{kb.display_name || kb.name}</td>
                                <td className="px-2 py-2 text-xs text-slate-600">{kb.description || t.noValue}</td>
                                <td className="px-2 py-2">
                                  {kb.language === "zh"
                                    ? t.languageChinese
                                    : kb.language === "en"
                                      ? t.languageEnglish
                                      : kb.language}
                                </td>
                                <td className={`px-2 py-2 text-xs ${canViewTechnicalFields ? "font-mono" : ""}`}>
                                  {kb.department ?? t.noValue}
                                </td>
                                <td className="px-2 py-2 text-xs">{kbDocumentCountByKbId[kb.id] ?? t.noValue}</td>
                                <td className="px-2 py-2">
                                  <button
                                    className="btn-secondary px-2 py-1 text-xs"
                                    type="button"
                                    onClick={() => onSelectKnowledgeBase(kb.id)}
                                  >
                                    {t.selectKnowledgeBase}
                                  </button>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                    {knowledgeBases.length === 0 ? (
                      <p className="mt-3 text-sm text-slate-500">{t.noKnowledgeBases}</p>
                    ) : null}
                  </div>

                  <div className="space-y-4">
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-medium text-slate-700">{t.uploadDocumentTitle}</p>
                        <div className="text-xs text-slate-500">
                          {t.uploadTargetKnowledgeBase}:{" "}
                          <span className={`${canViewTechnicalFields ? "font-mono" : ""} text-slate-700`}>
                            {selectedKnowledgeBase
                              ? canViewTechnicalFields
                                ? selectedKnowledgeBase.code
                                : selectedKnowledgeBase.display_name || selectedKnowledgeBase.name
                              : t.noValue}
                          </span>
                        </div>
                      </div>
                      {selectedKnowledgeBase ? (
                        canUploadDocuments ? (
                          <form className="space-y-3" onSubmit={onUploadDocument}>
                            <label className="block space-y-1">
                              <span className="text-xs text-slate-600">{t.uploadTitleOptional}</span>
                              <input
                                className="field h-9"
                                value={uploadTitle}
                                onChange={(event) => setUploadTitle(event.target.value)}
                                placeholder={selectedKnowledgeBase.display_name || selectedKnowledgeBase.name}
                              />
                            </label>
                            <label className="block space-y-1">
                              <span className="text-xs text-slate-600">{t.uploadChooseFile}</span>
                              <input
                                key={`${selectedKnowledgeBase.id}_${uploadInputVersion}`}
                                className="field h-10 p-1.5"
                                type="file"
                                accept=".md,.txt,text/markdown,text/plain"
                                onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
                              />
                            </label>
                            <div className="text-xs text-slate-500">{t.uploadConstraintHint}</div>
                            <div className="text-xs text-slate-600">
                              {t.uploadSelectedFile}: {uploadFile?.name ?? t.noValue}
                            </div>
                            <button
                              className="btn-primary w-full"
                              type="submit"
                              disabled={uploadPending || !uploadFile || !token}
                            >
                              {uploadPending ? t.working : t.uploadSubmit}
                            </button>
                            {uploadStatusMessage ? (
                              <div className="notification-line text-xs">{uploadStatusMessage}</div>
                            ) : null}
                          </form>
                        ) : (
                          <p className="text-sm text-slate-500">{t.uploadReadonlyHint}</p>
                        )
                      ) : (
                        <p className="text-sm text-slate-500">{t.noKnowledgeBaseSelected}</p>
                      )}
                    </div>

                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-medium text-slate-700">{t.documentsPanelTitle}</p>
                        <div className="text-xs text-slate-500">
                          {t.selectedKnowledgeBase}:{" "}
                          <span className={`${canViewTechnicalFields ? "font-mono" : ""} text-slate-700`}>
                            {selectedKnowledgeBase
                              ? canViewTechnicalFields
                                ? selectedKnowledgeBase.code
                                : selectedKnowledgeBase.display_name || selectedKnowledgeBase.name
                              : t.noValue}
                          </span>
                        </div>
                      </div>
                      {selectedKnowledgeBase ? (
                        selectedKnowledgeBaseDocuments.length > 0 ? (
                          <div className="overflow-x-auto">
                            <table className="w-full border-collapse text-left text-xs">
                              <thead>
                                <tr className="border-b border-slate-200 text-slate-600">
                                  <th className="px-2 py-2">{t.documentTitle}</th>
                                  <th className="px-2 py-2">{t.documentSource}</th>
                                  <th className="px-2 py-2">{t.chunkCount}</th>
                                  <th className="px-2 py-2">{t.createdAt}</th>
                                  <th className="px-2 py-2"></th>
                                </tr>
                              </thead>
                              <tbody>
                                {selectedKnowledgeBaseDocuments.map((doc) => (
                                  <tr key={doc.id} className="border-b border-slate-100">
                                    <td className="px-2 py-2">{doc.title}</td>
                                    <td className="px-2 py-2 font-mono">{doc.source}</td>
                                    <td className="px-2 py-2">{doc.chunk_count}</td>
                                    <td className="px-2 py-2">{formatDateTime(doc.created_at, language)}</td>
                                    <td className="px-2 py-2">
                                      <div className="flex items-center gap-2">
                                        <button
                                          className="btn-secondary px-2 py-1 text-xs"
                                          type="button"
                                          onClick={() => onSelectDocument(doc.id)}
                                        >
                                          {t.viewChunks}
                                        </button>
                                        {canUploadDocuments ? (
                                          <button
                                            className="btn-secondary px-2 py-1 text-xs"
                                            type="button"
                                            disabled={reindexPendingDocumentId === doc.id}
                                            onClick={() => onReindexDocument(doc.id)}
                                          >
                                            {reindexPendingDocumentId === doc.id ? t.working : t.reindexAction}
                                          </button>
                                        ) : null}
                                      </div>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        ) : (
                          <p className="text-sm text-slate-500">
                            {viewerPending ? t.working : t.noDocumentsInKnowledgeBase}
                          </p>
                        )
                      ) : (
                        <p className="text-sm text-slate-500">{t.noKnowledgeBaseSelected}</p>
                      )}
                    </div>

                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-medium text-slate-700">{t.chunkViewerTitle}</p>
                        <div className="text-xs text-slate-500">
                          {t.selectedDocument}:{" "}
                          <span className={`${canViewTechnicalFields ? "font-mono" : ""} text-slate-700`}>
                            {selectedDocument
                              ? canViewTechnicalFields
                                ? selectedDocument.id
                                : selectedDocument.title
                              : t.noValue}
                          </span>
                        </div>
                      </div>
                      {selectedDocument ? (
                        selectedDocumentChunks.length > 0 ? (
                          <div className="space-y-2">
                            {selectedDocumentChunks.map((chunk) => (
                              <details key={chunk.id} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                                <summary className="cursor-pointer">
                                  <div className="grid gap-1 text-xs md:grid-cols-[72px_minmax(0,1fr)_170px_150px]">
                                    <div className="font-mono text-slate-600">{t.chunkIndex}: {chunk.chunk_index}</div>
                                    <div className="font-mono text-slate-700">
                                      {canViewTechnicalFields ? `${t.chunkId}: ${chunk.id}` : t.contentPreview}
                                    </div>
                                    <div className="text-slate-600">
                                      {canViewTechnicalFields
                                        ? `${t.embeddingStatus}: ${chunk.has_embedding ? t.embeddingPresent : t.embeddingMissing}`
                                        : ""}
                                    </div>
                                    <div className="text-slate-600">
                                      {canViewTechnicalFields ? `${t.embeddingDimension}: ${chunk.embedding_dimension}` : ""}
                                    </div>
                                  </div>
                                  <p className="mt-1 text-sm text-slate-700">{chunk.content_preview}</p>
                                </summary>
                                <div className="mt-2 border-t border-slate-200 pt-2">
                                  <p className="mb-1 text-xs text-slate-500">{t.fullChunkContent}</p>
                                  <pre className="answer-block text-xs">{chunk.content}</pre>
                                </div>
                              </details>
                            ))}
                          </div>
                        ) : (
                          <p className="text-sm text-slate-500">{viewerPending ? t.working : t.noChunksInDocument}</p>
                        )
                      ) : (
                        <p className="text-sm text-slate-500">{t.noDocumentSelected}</p>
                      )}
                    </div>
                  </div>
                </div>
              </section>
            ) : null}

            {activeView === "audit_logs" ? (
              <section className="glass-panel p-6">
                <h2 className="panel-title">{t.auditLogsPageTitle}</h2>
                <div className="mb-4 rounded-2xl border border-slate-200 bg-slate-50 p-3">
                  <p className="text-sm font-medium text-slate-700">{t.localAuditRecords}</p>
                  <p className="mt-1 text-xs text-slate-500">{t.localAuditRecordsHint}</p>
                </div>
                {localAuditRecords.length > 0 ? (
                  <div className="max-h-[320px] overflow-y-auto overflow-x-auto">
                    <table className="w-full border-collapse text-left text-xs">
                      <thead>
                        <tr className="border-b border-slate-200 text-slate-600">
                          <th className="px-2 py-2">{t.requestId}</th>
                          <th className="px-2 py-2">{t.tableMode}</th>
                          <th className="px-2 py-2">{t.tableDenied}</th>
                          <th className="px-2 py-2">{t.tableCacheHit}</th>
                          <th className="px-2 py-2">{t.hitKnowledgeBases}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {localAuditRecords.map((row) => (
                          <tr key={`${row.sessionId}_${row.requestId}`} className="border-b border-slate-100">
                            <td className="px-2 py-2 font-mono">{row.requestId}</td>
                            <td className="px-2 py-2 font-mono">{row.mode}</td>
                            <td className="px-2 py-2">{formatBoolean(row.denied)}</td>
                            <td className="px-2 py-2">{formatBoolean(row.cacheHit)}</td>
                            <td className="px-2 py-2 font-mono">{row.hitKbCodes.join(", ") || t.noValue}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-sm text-slate-500">{t.noLocalAuditRecords}</p>
                )}

                <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-3">
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <p className="text-sm font-medium text-slate-700">{t.adminAuditLogs}</p>
                    {canViewAdminViews ? (
                      <button className="btn-secondary" onClick={onLoadAdminAudit} disabled={pending} type="button">
                        {t.loadAuditLogs}
                      </button>
                    ) : null}
                  </div>
                  {canViewAdminViews ? (
                    auditLogs.length > 0 ? (
                      <div className="max-h-[260px] overflow-y-auto overflow-x-auto">
                        <table className="w-full border-collapse text-left text-xs">
                          <thead>
                            <tr className="border-b border-slate-200 text-slate-600">
                              <th className="px-2 py-2">{t.requestId}</th>
                              <th className="px-2 py-2">{t.tableMode}</th>
                              <th className="px-2 py-2">{t.tableDenied}</th>
                              <th className="px-2 py-2">{t.tableCacheHit}</th>
                            </tr>
                          </thead>
                          <tbody>
                            {auditLogs.map((row) => (
                              <tr key={row.request_id} className="border-b border-slate-100">
                                <td className="px-2 py-2 font-mono">{row.request_id}</td>
                                <td className="px-2 py-2 font-mono">{row.mode}</td>
                                <td className="px-2 py-2">{formatBoolean(row.denied)}</td>
                                <td className="px-2 py-2">{formatBoolean(row.cache_hit)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p className="text-xs text-slate-500">{t.adminAuditLogsHint}</p>
                    )
                  ) : (
                    <p className="text-xs text-slate-500">{t.auditViewerPlanned}</p>
                  )}
                </div>
              </section>
            ) : null}

            {activeView === "system_status" ? (
              <section className="glass-panel p-6">
                <h2 className="panel-title">{t.systemStatusPageTitle}</h2>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.routerMode}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {retrievalConfig?.router_mode ?? t.routerModeValue}
                    </div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.routerModel}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {retrievalConfig?.router_model ?? t.noValue}
                    </div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.routerAvailability}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {retrievalConfig?.router_availability ?? t.noValue}
                    </div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.routerFallback}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {retrievalConfig ? formatBoolean(retrievalConfig.router_fallback_last) : t.noValue}
                    </div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.routerError}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {retrievalConfig?.router_error_last ?? t.noValue}
                    </div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.generatorMode}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {retrievalConfig?.generator_mode ?? t.generatorModeValue}
                    </div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.embeddingMode}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {retrievalConfig?.embedding_provider ?? t.noValue}
                    </div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.embeddingDimension}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {retrievalConfig?.embedding_dimension ?? t.noValue}
                    </div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.retrievalEngine}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {retrievalConfig?.retrieval_engine ?? t.noValue}
                    </div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.defaultTopK}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {retrievalConfig?.top_k ?? retrievalConfig?.default_top_k ?? t.noValue}
                    </div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.pgvectorStatus}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {retrievalConfig
                        ? retrievalConfig.pgvector_sql_retrieval_enabled
                          ? t.yes
                          : t.no
                        : t.noValue}
                    </div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.cacheBackend}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {retrievalConfig?.cache_backend ?? t.noValue}
                    </div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.documentUploadStatus}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {retrievalConfig ? formatBoolean(retrievalConfig.document_upload_enabled) : t.noValue}
                    </div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.uploadMaxSize}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {retrievalConfig ? formatSize(retrievalConfig.upload_max_size_bytes) : t.noValue}
                    </div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.uploadSupportedTypes}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {retrievalConfig?.upload_supported_types.join(", ") || t.noValue}
                    </div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.indexingMode}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {retrievalConfig?.indexing_mode ?? t.noValue}
                    </div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.permissionEnforcement}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">{t.permissionEnforcementValue}</div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.functionCallingMode}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {retrievalConfig?.function_calling_mode ?? "backend-controlled-trace"}
                    </div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.llmAutonomousToolCalling}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {formatBoolean(retrievalConfig?.llm_autonomous_tool_calling)}
                    </div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.permissionAuthority}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {retrievalConfig?.permission_authority ?? t.permissionEnforcementValue}
                    </div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">Neo4j configured</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {retrievalConfig ? formatBoolean(retrievalConfig.neo4j_configured) : t.noValue}
                    </div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">Neo4j availability</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {retrievalConfig ? formatBoolean(retrievalConfig.neo4j_available) : t.noValue}
                    </div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.graphSyncStatus}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {retrievalConfig?.graph_last_sync_status ?? t.noValue}
                    </div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.graphSyncNeeded}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {retrievalConfig?.graph_pending_sync_kb_codes.join(", ") || t.noValue}
                    </div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.graphFallback}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {retrievalConfig?.graph_fallback_mode ?? t.noValue}
                    </div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">GraphRAG visualization</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {retrievalConfig ? formatBoolean(retrievalConfig.graph_visualization_enabled) : t.noValue}
                    </div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">GraphRAG permission scope</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {retrievalConfig?.graph_permission_scope ?? t.noValue}
                    </div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.cacheStatus}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">{formatCacheState(activeResponse)}</div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.currentRole}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">{user?.role ?? t.noValue}</div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.currentDepartment}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">{user?.department ?? t.noValue}</div>
                  </div>
                  <div className="soft-card">
                    <div className="text-xs text-slate-500">{t.allowedKbSummary}</div>
                    <div className="mt-1 font-mono text-sm text-slate-800">
                      {knowledgeBases.map((kb) => kb.code).join(", ") || t.noValue}
                    </div>
                  </div>
                </div>
                <p className="mt-4 text-xs text-slate-500">{t.systemStatusHint}</p>
              </section>
            ) : null}

            {activeView === "permission_matrix" ? (
              <section className="min-w-0 space-y-4">
                <div className="glass-panel min-w-0 p-6">
                  <h2 className="panel-title">{t.permissionMatrixPageTitle}</h2>
                  <p className="mb-4 text-sm text-slate-600">{t.permissionMatrixPageHint}</p>

                  {!canViewPermissionMatrix ? (
                    <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                      {t.permissionMatrixNoPermission}
                    </div>
                  ) : permissionMatrixPending ? (
                    <p className="text-sm text-slate-500">{t.working}</p>
                  ) : permissionMatrix ? (
                    <div className="min-w-0 space-y-4">
                      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(320px,370px)]">
                        <div className="min-w-0 rounded-2xl border border-slate-200 bg-slate-50 p-3">
                          <div className="w-full max-w-full overflow-x-auto">
                            <table className="min-w-[1180px] table-fixed border-collapse text-left text-xs">
                              <thead>
                                <tr className="border-b border-slate-200 text-slate-600">
                                  <th className="w-[230px] px-2 py-2">{t.permissionMatrixUsers}</th>
                                  {permissionMatrixKnowledgeBases.map((kb) => (
                                    <th key={kb.code} className="w-[120px] px-2 py-2 align-top text-[11px]">
                                      <div className="max-w-[110px] truncate font-semibold" title={formatPermissionKb(kb.code)}>
                                        {formatPermissionKb(kb.code)}
                                      </div>
                                      <div className="max-w-[110px] truncate text-[10px] font-normal text-slate-500" title={kb.code}>
                                        {kb.code}
                                      </div>
                                      <div className="font-normal text-[10px] text-slate-500">{formatPermissionScope(kb.scope)}</div>
                                    </th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {permissionMatrixUsers.map((userItem) => {
                                  const isSelected = selectedMatrixUser?.email === userItem.email;
                                  const allowedSet = new Set(userItem.allowed_kb_codes);
                                  return (
                                    <tr
                                      key={userItem.email}
                                      className={`cursor-pointer border-b border-slate-100 ${
                                        isSelected ? "bg-white" : "hover:bg-white/70"
                                      }`}
                                      onClick={() => setSelectedMatrixUserEmail(userItem.email)}
                                    >
                                      <td className="w-[230px] px-2 py-2 align-top">
                                        <div className="max-w-[210px] truncate font-mono text-[11px] text-slate-800" title={userItem.email}>
                                          {userItem.email}
                                        </div>
                                        <div className="text-[11px] text-slate-500">
                                          {formatPermissionRole(userItem.role)} / {formatPermissionDepartment(userItem.department)}
                                        </div>
                                      </td>
                                      {permissionMatrixKnowledgeBases.map((kb) => (
                                        <td key={`${userItem.email}_${kb.code}`} className="px-2 py-2 text-center">
                                          {allowedSet.has(kb.code) ? "✅" : "—"}
                                        </td>
                                      ))}
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                          <p className="mt-2 text-xs text-slate-500">{t.permissionMatrixSelectUserHint}</p>
                        </div>

                        <div className="min-w-0 space-y-4 xl:max-w-[370px]">
                          <div className="min-w-0 rounded-2xl border border-slate-200 bg-slate-50 p-3">
                            <h3 className="text-sm font-semibold text-slate-800">{t.permissionMatrixUserDetailTitle}</h3>
                            {selectedMatrixUser ? (
                              <div className="mt-2 space-y-2 text-xs text-slate-700">
                                <div className="truncate font-mono" title={selectedMatrixUser.email}>{selectedMatrixUser.email}</div>
                                <div>
                                  {t.permissionMatrixRole}: {formatPermissionRole(selectedMatrixUser.role)}
                                  <span className="ml-1 text-[11px] text-slate-500">({selectedMatrixUser.role})</span>
                                </div>
                                <div>
                                  {t.permissionMatrixDepartment}: {formatPermissionDepartment(selectedMatrixUser.department)}
                                  {selectedMatrixUser.department ? (
                                    <span className="ml-1 text-[11px] text-slate-500">({selectedMatrixUser.department})</span>
                                  ) : null}
                                </div>
                                <div>
                                  <div className="mb-1 font-medium text-slate-800">{t.permissionMatrixAllowedKbs}</div>
                                  {selectedMatrixUser.allowed_kb_codes.length > 0 ? (
                                    <div className="flex flex-wrap gap-1.5">
                                      {selectedMatrixUser.allowed_kb_codes.map((code) => (
                                        <span key={`${selectedMatrixUser.email}_${code}_allowed`} className="tag-pill max-w-full truncate" title={code}>
                                          {formatPermissionKb(code)}
                                        </span>
                                      ))}
                                    </div>
                                  ) : (
                                    t.noValue
                                  )}
                                </div>
                                <div>
                                  <div className="mb-1 font-medium text-slate-800">{t.permissionMatrixBlockedKbs}</div>
                                  {blockedMatrixKbCodes.length > 0 ? (
                                    <div className="flex flex-wrap gap-1.5">
                                      {blockedMatrixKbCodes.map((code) => (
                                        <span key={`${selectedMatrixUser.email}_${code}_blocked`} className="tag-pill max-w-full truncate" title={code}>
                                          {formatPermissionKb(code)}
                                        </span>
                                      ))}
                                    </div>
                                  ) : (
                                    t.noValue
                                  )}
                                </div>
                              </div>
                            ) : (
                              <p className="mt-2 text-sm text-slate-500">{t.permissionMatrixNoData}</p>
                            )}
                          </div>

                          <div className="min-w-0 rounded-2xl border border-slate-200 bg-slate-50 p-3">
                            <h3 className="text-sm font-semibold text-slate-800">{t.permissionMatrixFormulaTitle}</h3>
                            <div className="mt-2 rounded-sm border border-slate-200 bg-white px-2 py-2 font-mono text-xs text-slate-800">
                              {t.permissionMatrixFormulaLine1}
                            </div>
                            <div className="mt-2 space-y-1 text-xs text-slate-600">
                              <div>{t.permissionMatrixFormulaLine2}</div>
                              <div>{t.permissionMatrixFormulaLine3}</div>
                              <div>{t.permissionMatrixFormulaLine4}</div>
                            </div>
                          </div>

                          <div className="min-w-0 rounded-2xl border border-slate-200 bg-slate-50 p-3">
                            <h3 className="text-sm font-semibold text-slate-800">{t.permissionMatrixDemoCasesTitle}</h3>
                            <div className="mt-2 space-y-2">
                              {PERMISSION_MATRIX_DEMO_CASES.map((item) => (
                                <div key={item.label} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700">
                                  <div className="font-semibold text-slate-800">{item.label}</div>
                                  <div>user = {formatPermissionRole(item.user)}</div>
                                  <div>question = {item.question}</div>
                                  <div>target = {formatPermissionKb(item.target)}</div>
                                  <div>decision = {item.decision}</div>
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>
                      </div>

                      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                        <h3 className="text-sm font-semibold text-amber-900">{t.permissionMatrixSecurityTitle}</h3>
                        <div className="mt-2 font-mono">{t.permissionMatrixTraditionalFlow}</div>
                        <div className="mt-1 font-mono">{t.permissionMatrixProjectFlow}</div>
                        <ul className="mt-2 space-y-1">
                          <li>{t.permissionMatrixSecurityPoint1}</li>
                          <li>{t.permissionMatrixSecurityPoint2}</li>
                          <li>{t.permissionMatrixSecurityPoint3}</li>
                          <li>{t.permissionMatrixSecurityPoint4}</li>
                        </ul>
                      </div>

                      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
                        <div className="flex flex-wrap gap-1.5">
                          <span className="font-medium text-slate-800">{t.permissionMatrixRole}:</span>
                          {permissionMatrix.roles.map((item) => (
                            <span key={item.name} className="tag-pill" title={`${t.permissionMatrixCode}: ${item.name}`}>
                              {formatPermissionRole(item.name)}
                            </span>
                          ))}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          <span className="font-medium text-slate-800">{t.permissionMatrixDepartment}:</span>
                          {permissionMatrix.departments.map((item) => (
                            <span key={item.code} className="tag-pill" title={`${t.permissionMatrixCode}: ${item.code}`}>
                              {formatPermissionDepartment(item.code)}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-slate-500">{t.permissionMatrixNoData}</p>
                  )}
                </div>
              </section>
            ) : null}

            {activeView === "graph_rag" ? (
              <section className="space-y-4">
                <div className="glass-panel p-6">
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                    <h2 className="panel-title mb-0">{t.graphStatusPanelTitle}</h2>
                    {canUploadDocuments ? (
                      <button
                        className="btn-secondary"
                        type="button"
                        disabled={graphSyncPending || !token}
                        onClick={onSyncGraph}
                      >
                        {graphSyncPending ? t.working : t.graphSyncAction}
                      </button>
                    ) : null}
                  </div>
                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                    <div className="soft-card">
                      <div className="text-xs text-slate-500">Neo4j configured</div>
                      <div className="mt-1 font-mono text-sm text-slate-800">
                        {graphStatus ? formatBoolean(graphStatus.neo4j_configured) : t.noValue}
                      </div>
                    </div>
                    <div className="soft-card">
                      <div className="text-xs text-slate-500">Neo4j availability</div>
                      <div className="mt-1 font-mono text-sm text-slate-800">
                        {graphStatus ? formatBoolean(graphStatus.neo4j_available) : t.noValue}
                      </div>
                    </div>
                    <div className="soft-card">
                      <div className="text-xs text-slate-500">{t.graphNodeCount}</div>
                      <div className="mt-1 font-mono text-sm text-slate-800">
                        {graphStatus?.node_count ?? t.noValue}
                      </div>
                    </div>
                    <div className="soft-card">
                      <div className="text-xs text-slate-500">{t.graphEdgeCount}</div>
                      <div className="mt-1 font-mono text-sm text-slate-800">
                        {graphStatus?.relationship_count ?? t.noValue}
                      </div>
                    </div>
                    <div className="soft-card">
                      <div className="text-xs text-slate-500">{t.graphSyncStatus}</div>
                      <div className="mt-1 font-mono text-sm text-slate-800">
                        {String(graphStatus?.last_sync_summary?.status ?? t.noValue)}
                      </div>
                    </div>
                    <div className="soft-card">
                      <div className="text-xs text-slate-500">{t.graphSyncNeeded}</div>
                      <div className="mt-1 font-mono text-sm text-slate-800">
                        {graphStatus?.pending_sync_kb_codes.join(", ") || t.noValue}
                      </div>
                    </div>
                    <div className="soft-card">
                      <div className="text-xs text-slate-500">{t.graphFallback}</div>
                      <div className="mt-1 font-mono text-sm text-slate-800">
                        {graphStatus?.fallback_mode ?? t.noValue}
                      </div>
                    </div>
                    <div className="soft-card">
                      <div className="text-xs text-slate-500">{t.allowedKbSummary}</div>
                      <div className="mt-1 font-mono text-sm text-slate-800">
                        {graphOverview?.allowed_kb_codes.join(", ") || t.noValue}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="glass-panel p-6">
                  <h2 className="panel-title">{t.graphOverviewPanelTitle}</h2>
                  {graphPending ? (
                    <p className="text-sm text-slate-500">{t.working}</p>
                  ) : positionedGraphNodes.length > 0 ? (
                    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
                      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                        <div className="overflow-auto rounded-xl border border-slate-200 bg-white">
                          <svg
                            viewBox={`0 0 ${GRAPH_CANVAS_WIDTH} ${GRAPH_CANVAS_HEIGHT}`}
                            className="h-[540px] w-full min-w-[840px]"
                          >
                            {activeGraphEdges.map((edge) => {
                              const source = graphNodeById.get(edge.source);
                              const target = graphNodeById.get(edge.target);
                              if (!source || !target) return null;
                              const midX = Math.round((source.x + target.x) / 2);
                              const midY = Math.round((source.y + target.y) / 2);
                              return (
                                <g key={edge.id}>
                                  <line x1={source.x} y1={source.y} x2={target.x} y2={target.y} stroke="#cbd5e1" strokeWidth={1.4} />
                                  <text x={midX} y={midY - 4} textAnchor="middle" fontSize="9" fill="#64748b">
                                    {edge.type}
                                  </text>
                                </g>
                              );
                            })}
                            {positionedGraphNodes.map((node) => {
                              const selected = selectedGraphNodeId === node.id;
                              return (
                                <g
                                  key={node.id}
                                  onClick={() => setSelectedGraphNodeId(node.id)}
                                  style={{ cursor: "pointer" }}
                                >
                                  <circle
                                    cx={node.x}
                                    cy={node.y}
                                    r={selected ? 17 : 14}
                                    fill={graphNodeColor(node.type)}
                                    opacity={selected ? 1 : 0.88}
                                  />
                                  <text x={node.x + 20} y={node.y + 4} fontSize="10" fill="#1e293b">
                                    {node.label}
                                  </text>
                                </g>
                              );
                            })}
                          </svg>
                        </div>
                      </div>
                      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                        <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                          {t.graphNodeDetailTitle}
                        </div>
                        {selectedGraphNode ? (
                          <div className="mt-3 space-y-2 text-xs text-slate-700">
                            <div>
                              <span className="text-slate-500">type:</span> {graphTypeLabel(selectedGraphNode.type)}
                            </div>
                            <div className="font-mono text-[11px]">
                              <span className="text-slate-500">id:</span> {selectedGraphNode.id}
                            </div>
                            <div>
                              <span className="text-slate-500">label:</span> {selectedGraphNode.label}
                            </div>
                            <div className="font-mono text-[11px]">
                              <span className="text-slate-500">kb_code:</span> {selectedGraphNode.kb_code ?? t.noValue}
                            </div>
                            <div>{selectedGraphNode.metadata_summary ?? t.noValue}</div>
                          </div>
                        ) : (
                          <p className="mt-3 text-sm text-slate-500">{t.graphNoData}</p>
                        )}
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-slate-500">{t.graphNoData}</p>
                  )}
                  {graphOverview?.security_notes.length ? (
                    <div className="mt-3 rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                      {graphOverview.security_notes.map((note, index) => (
                        <div key={`graph_overview_note_${index}`}>{note}</div>
                      ))}
                    </div>
                  ) : null}
                </div>

                <div className="glass-panel p-6">
                  <h2 className="panel-title">{t.graphPathPanelTitle}</h2>
                  {requestGraphTrace ? (
                    <div className="space-y-3">
                      {requestTrace ? (
                        <div className="soft-card">
                          <div className="text-xs text-slate-500">{t.traceQuestion}</div>
                          <div className="mt-1 text-sm text-slate-800">{requestTrace.question}</div>
                        </div>
                      ) : null}
                      <div className="soft-card">
                        <div className="text-xs text-slate-500">{t.traceAllowedScope}</div>
                        <div className="mt-1 font-mono text-xs text-slate-800">
                          {requestGraphTrace.allowed_kb_codes.join(", ") || t.noValue}
                        </div>
                      </div>
                      {requestGraphTrace.graph_paths.length > 0 ? (
                        <div className="space-y-2">
                          {requestGraphTrace.graph_paths.map((item) => (
                            <div key={`graph_page_${item.chunk_id}`} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                              <div className="font-mono text-[11px] text-slate-700">{item.chunk_id}</div>
                              <div className="mt-1 text-sm text-slate-700">{item.path.join(" → ")}</div>
                              <div className="mt-1 text-xs text-slate-500">{item.explanation}</div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-slate-500">{t.graphNoPath}</p>
                      )}
                      <div className="soft-card">
                        <div className="text-xs text-slate-500">{t.graphFallback}</div>
                        <div className="mt-1 font-mono text-xs text-slate-800">
                          {String(requestGraphTrace.fallback_used)}
                        </div>
                      </div>
                      {requestGraphTrace.security_notes.length > 0 ? (
                        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                          {requestGraphTrace.security_notes.map((note, index) => (
                            <div key={`graph_request_note_${index}`}>{note}</div>
                          ))}
                        </div>
                      ) : null}
                      <details className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                        <summary className="cursor-pointer text-xs font-medium text-slate-700">{t.rawTraceJson}</summary>
                        <pre className="answer-block mt-3 max-h-[280px]">
                          {JSON.stringify(requestGraphTrace, null, 2)}
                        </pre>
                      </details>
                    </div>
                  ) : (
                    <p className="text-sm text-slate-500">{tracePending ? t.working : t.graphNoPath}</p>
                  )}
                </div>
              </section>
            ) : null}

            {activeView === "developer_trace" ? (
              <section className="space-y-4">
                <div className="glass-panel p-6">
                  <h2 className="panel-title">{t.latestRetrievalTrace}</h2>
                  {requestTrace ? (
                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                      <div className="soft-card">
                        <div className="text-xs text-slate-500">{t.traceRequestId}</div>
                        <div className="mt-1 font-mono text-xs">{requestTrace.request_id}</div>
                      </div>
                      <div className="soft-card">
                        <div className="text-xs text-slate-500">cache_hit</div>
                        <div className="mt-1 font-mono text-xs">{String(requestTrace.cache_hit)}</div>
                      </div>
                      <div className="soft-card">
                        <div className="text-xs text-slate-500">{t.responseMode}</div>
                        <div className="mt-1 font-mono text-xs">{requestTrace.mode}</div>
                      </div>
                      <div className="soft-card">
                        <div className="text-xs text-slate-500">{t.retrievalEngine}</div>
                        <div className="mt-1 font-mono text-xs">{requestTrace.retrieval_engine}</div>
                      </div>
                      <div className="soft-card">
                        <div className="text-xs text-slate-500">{t.routerMode}</div>
                        <div className="mt-1 font-mono text-xs">{requestTrace.router_mode}</div>
                      </div>
                      <div className="soft-card">
                        <div className="text-xs text-slate-500">{t.routerModel}</div>
                        <div className="mt-1 font-mono text-xs">{requestTrace.router_model}</div>
                      </div>
                      <div className="soft-card">
                        <div className="text-xs text-slate-500">denied</div>
                        <div className="mt-1 font-mono text-xs">{String(requestTrace.denied)}</div>
                      </div>
                      <div className="soft-card">
                        <div className="text-xs text-slate-500">{t.model}</div>
                        <div className="mt-1 font-mono text-xs">{requestTrace.model || t.noValue}</div>
                      </div>
                      <div className="soft-card">
                        <div className="text-xs text-slate-500">{t.latency}</div>
                        <div className="mt-1 font-mono text-xs">
                          {requestTrace.latency_ms} {t.milliseconds}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-slate-500">{tracePending ? t.working : t.traceUnavailable}</p>
                  )}
                </div>

                <div className="glass-panel p-6">
                  <h2 className="panel-title">{t.tracePathTitle}</h2>
                  {requestTrace ? (
                    <div className="space-y-3">
                      <div className="soft-card">
                        <div className="text-xs text-slate-500">{t.traceQuestion}</div>
                        <div className="mt-1 text-sm text-slate-800">{requestTrace.question}</div>
                      </div>
                      <div className="soft-card">
                        <div className="text-xs text-slate-500">{t.traceIdentity}</div>
                        <div className="mt-1 font-mono text-xs text-slate-800">
                          {requestTrace.user_email ?? t.noValue} / {requestTrace.role ?? t.noValue} /{" "}
                          {requestTrace.department ?? t.noValue}
                        </div>
                      </div>
                      <div className="soft-card">
                        <div className="text-xs text-slate-500">{t.traceRouterStep}</div>
                        <div className="mt-1 space-y-1 font-mono text-xs text-slate-800">
                          <div>language: {requestTrace.router_decision?.language ?? t.noValue}</div>
                          <div>intent: {requestTrace.router_decision?.intent ?? t.noValue}</div>
                          <div>target_department: {requestTrace.router_decision?.target_department ?? t.noValue}</div>
                          <div>need_rag: {String(requestTrace.router_decision?.need_rag ?? false)}</div>
                          <div>confidence: {requestTrace.router_decision?.confidence ?? t.noValue}</div>
                          <div>fallback: {String(requestTrace.router_fallback_used)}</div>
                          <div>availability: {requestTrace.router_availability}</div>
                          {requestTrace.router_error ? <div>router_error: {requestTrace.router_error}</div> : null}
                        </div>
                      </div>
                      <div className="soft-card">
                        <div className="text-xs text-slate-500">{t.traceAllowedScope}</div>
                        <div className="mt-1 font-mono text-xs text-slate-800">
                          {requestTrace.allowed_kb_codes.join(", ") || t.noValue}
                        </div>
                      </div>
                      <div className="soft-card">
                        <div className="text-xs text-slate-500">{t.traceMode}</div>
                        <div className="mt-1 font-mono text-xs text-slate-800">{requestTrace.mode}</div>
                      </div>
                      <div className="soft-card">
                        <div className="text-xs text-slate-500">{t.traceChunks}</div>
                        <div className="mt-2 space-y-1 text-xs">
                          {requestTrace.retrieved_chunks.length > 0 ? (
                            requestTrace.retrieved_chunks.map((item) => (
                              <div key={item.chunk_id} className="rounded-lg border border-slate-200 bg-white px-2 py-1">
                                <div className="font-mono text-[11px] text-slate-700">
                                  {item.kb_code} / {item.document_title} / {item.chunk_id}
                                </div>
                                <div className="mt-1 text-slate-600">{item.content_preview}</div>
                              </div>
                            ))
                          ) : (
                            <div className="text-slate-500">{t.noValue}</div>
                          )}
                        </div>
                      </div>
                      <div className="soft-card">
                        <div className="text-xs text-slate-500">{t.traceDecision}</div>
                        <div className="mt-1 text-sm text-slate-800">
                          {requestTrace.denied
                            ? requestTrace.refusal_reason || t.requestDeniedPrefix
                            : requestTrace.answer}
                        </div>
                      </div>
                      <div className="soft-card">
                        <div className="text-xs text-slate-500">{t.traceAuditRef}</div>
                        <div className="mt-1 space-y-1 font-mono text-xs text-slate-800">
                          <div>request_id: {requestTrace.request_id}</div>
                          <div>cache_hit: {String(requestTrace.cache_hit)}</div>
                          <div>hit_chunk_ids: {requestTrace.hit_chunk_ids.join(", ") || t.noValue}</div>
                        </div>
                      </div>
                      {requestTrace.trace_limits.length > 0 ? (
                        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                          {requestTrace.trace_limits.map((line, index) => (
                            <div key={`${requestTrace.request_id}_limit_${index}`}>{line}</div>
                          ))}
                        </div>
                      ) : null}
                      <details className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                        <summary className="cursor-pointer text-xs font-medium text-slate-700">
                          {t.rawTraceJson}
                        </summary>
                        <pre className="answer-block mt-3 max-h-[300px]">
                          {JSON.stringify(requestTrace, null, 2)}
                        </pre>
                      </details>
                    </div>
                  ) : (
                    <p className="text-sm text-slate-500">{tracePending ? t.working : t.traceUnavailable}</p>
                  )}
                </div>

                <div className="glass-panel p-6">
                  <h2 className="panel-title">{t.functionTraceTitle}</h2>
                  {requestTrace ? (
                    requestTrace.function_trace.length > 0 ? (
                      <div className="space-y-3">
                        {requestTrace.function_trace.map((step) => (
                          <div key={`${requestTrace.request_id}_${step.order_index}_${step.tool_name}`} className="soft-card">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <div className="font-mono text-xs text-slate-800">
                                {step.order_index}. {step.tool_name}
                              </div>
                              <span
                                className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${traceStatusClass(step.status)}`}
                              >
                                {step.status}
                              </span>
                            </div>
                            <div className="mt-2 grid gap-2 md:grid-cols-2">
                              <div>
                                <div className="text-[11px] text-slate-500">{t.functionTraceInput}</div>
                                <div className="mt-1 text-xs text-slate-700">{step.input_summary}</div>
                              </div>
                              <div>
                                <div className="text-[11px] text-slate-500">{t.functionTraceOutput}</div>
                                <div className="mt-1 text-xs text-slate-700">{step.output_summary}</div>
                              </div>
                              <div>
                                <div className="text-[11px] text-slate-500">{t.functionTraceDuration}</div>
                                <div className="mt-1 font-mono text-xs text-slate-700">
                                  {step.duration_ms} {t.milliseconds}
                                </div>
                              </div>
                              <div>
                                <div className="text-[11px] text-slate-500">{t.functionTraceSecurity}</div>
                                <div className="mt-1 text-xs text-slate-700">{step.security_note}</div>
                              </div>
                            </div>
                            {step.error_code ? (
                              <div className="mt-2 text-xs text-red-700">
                                {t.functionTraceErrorCode}: {step.error_code}
                              </div>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-slate-500">{t.traceUnavailable}</p>
                    )
                  ) : (
                    <p className="text-sm text-slate-500">{tracePending ? t.working : t.traceUnavailable}</p>
                  )}
                </div>

                <div className="glass-panel p-6">
                  <h2 className="panel-title">{t.graphTraceTitle}</h2>
                  {requestGraphTrace ? (
                    <div className="space-y-3">
                      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                        <div className="soft-card">
                          <div className="text-xs text-slate-500">{t.traceRequestId}</div>
                          <div className="mt-1 font-mono text-xs text-slate-800">{requestGraphTrace.request_id}</div>
                        </div>
                        <div className="soft-card">
                          <div className="text-xs text-slate-500">{t.graphFallback}</div>
                          <div className="mt-1 font-mono text-xs text-slate-800">
                            {String(requestGraphTrace.fallback_used)}
                          </div>
                        </div>
                        <div className="soft-card">
                          <div className="text-xs text-slate-500">{t.graphNodeCount}</div>
                          <div className="mt-1 font-mono text-xs text-slate-800">{requestGraphTrace.nodes.length}</div>
                        </div>
                        <div className="soft-card">
                          <div className="text-xs text-slate-500">{t.graphEdgeCount}</div>
                          <div className="mt-1 font-mono text-xs text-slate-800">{requestGraphTrace.edges.length}</div>
                        </div>
                      </div>
                      {requestGraphTrace.graph_paths.length > 0 ? (
                        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                            {t.graphPaths}
                          </div>
                          <div className="mt-2 space-y-1 text-xs text-slate-700">
                            {requestGraphTrace.graph_paths.map((item) => (
                              <div key={`graph_path_${item.chunk_id}`} className="rounded-lg border border-slate-200 bg-white px-2 py-1">
                                <div className="font-mono text-[11px] text-slate-600">{item.chunk_id}</div>
                                <div className="mt-1">{item.path.join(" → ")}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <p className="text-sm text-slate-500">{t.graphNoPath}</p>
                      )}
                      {requestGraphTrace.security_notes.length > 0 ? (
                        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                          {requestGraphTrace.security_notes.map((note, index) => (
                            <div key={`graph_note_${index}`}>{note}</div>
                          ))}
                        </div>
                      ) : null}
                      <details className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                        <summary className="cursor-pointer text-xs font-medium text-slate-700">{t.rawTraceJson}</summary>
                        <pre className="answer-block mt-3 max-h-[300px]">
                          {JSON.stringify(requestGraphTrace, null, 2)}
                        </pre>
                      </details>
                    </div>
                  ) : (
                    <p className="text-sm text-slate-500">{tracePending ? t.working : t.traceUnavailable}</p>
                  )}
                </div>

                <div className="glass-panel p-6">
                  <div className="flex items-center justify-between gap-3">
                    <h2 className="panel-title mb-0">{t.securityTestScenarios}</h2>
                    <button className="btn-secondary" type="button" onClick={() => setSecurityOpen((prev) => !prev)}>
                      {securityOpen ? t.collapseScenarios : t.expandScenarios}
                    </button>
                  </div>
                  {securityOpen ? (
                    <div className="mt-3 space-y-2">
                      {OVERREACH_SCENARIOS.map((scenario) => (
                        <button
                          key={scenario.id}
                          className="scenario-card"
                          type="button"
                          disabled={pending}
                          onClick={() => runOverreachScenario(scenario)}
                        >
                          <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{scenario.account}</div>
                          <div className="mt-1 text-sm text-slate-800">{overreachLabels[scenario.id] ?? scenario.id}</div>
                        </button>
                      ))}
                    </div>
                  ) : null}
                </div>
              </section>
            ) : null}
          </main>
        </div>
      </div>
    </div>
  );
}
