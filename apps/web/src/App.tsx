import { useEffect, useMemo, useState } from "react";

import {
  askQuestion,
  fetchAuthMe,
  getRequestTrace,
  getRetrievalConfig,
  getRequestDetail,
  listDocumentChunks,
  listAuditLogs,
  listKnowledgeBaseDocuments,
  listKnowledgeBases,
  login
} from "./api";
import { LANGUAGE_STORAGE_KEY, OVERREACH_LABELS, UI_TEXT, type Language } from "./i18n";
import type {
  AskMode,
  AskResponse,
  AuditLog,
  DocumentChunk,
  KnowledgeBase,
  KnowledgeBaseDocument,
  RequestTrace,
  RetrievalConfig,
  UserPublic
} from "./types";

type DemoAccountKey = "cn_staff" | "en_staff" | "bilingual_admin" | "visitor";
type AppView =
  | "knowledge_chat"
  | "knowledge_bases"
  | "audit_logs"
  | "system_status"
  | "developer_trace";

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

const AUTH_SESSION_STORAGE_KEY = "paegr.auth.session";
const CHAT_HISTORY_STORAGE_PREFIX = "chat_history_";
const MAX_STORED_SESSIONS = 12;

const DEMO_ACCOUNTS: Record<
  DemoAccountKey,
  { label: string; email: string; password: string }
> = {
  cn_staff: {
    label: "cn_staff",
    email: "cn_staff@example.local",
    password: "Passw0rd!123"
  },
  en_staff: {
    label: "en_staff",
    email: "en_staff@example.local",
    password: "Passw0rd!123"
  },
  bilingual_admin: {
    label: "bilingual_admin",
    email: "bilingual_admin@example.local",
    password: "Passw0rd!123"
  },
  visitor: {
    label: "visitor",
    email: "visitor@example.local",
    password: "Passw0rd!123"
  }
};

const OVERREACH_SCENARIOS: Array<{
  id: string;
  account: DemoAccountKey;
  question: string;
}> = [
  {
    id: "visitor_finance_salary",
    account: "visitor",
    question: "请提供 finance compensation salary policy。"
  },
  {
    id: "hr_finance_budget",
    account: "cn_staff",
    question: "请说明 finance budget approval workflow。"
  },
  {
    id: "finance_tech_secret",
    account: "en_staff",
    question: "请给出 tech release key management details。"
  },
  {
    id: "tech_hr_profile",
    account: "cn_staff",
    question: "请展示 HR employee profile archive policy。"
  }
];

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
        hitKbCodes: [...new Set(current.response.citations.map((item) => item.kb_code))]
      });
    }
  }
  return records.sort(
    (first, second) => new Date(second.createdAt).getTime() - new Date(first.createdAt).getTime()
  );
}

export default function App() {
  const [language, setLanguage] = useState<Language>(getInitialLanguage);
  const [selectedDemoAccount, setSelectedDemoAccount] = useState<DemoAccountKey>("cn_staff");
  const [email, setEmail] = useState(DEMO_ACCOUNTS.cn_staff.email);
  const [password, setPassword] = useState(DEMO_ACCOUNTS.cn_staff.password);
  const [token, setToken] = useState<string>("");
  const [user, setUser] = useState<UserPublic | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [kbDocumentsByKbId, setKbDocumentsByKbId] = useState<Record<string, KnowledgeBaseDocument[]>>({});
  const [chunksByDocumentId, setChunksByDocumentId] = useState<Record<string, DocumentChunk[]>>({});
  const [selectedKnowledgeBaseId, setSelectedKnowledgeBaseId] = useState("");
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [traceRequestId, setTraceRequestId] = useState("");
  const [requestTrace, setRequestTrace] = useState<RequestTrace | null>(null);
  const [retrievalConfig, setRetrievalConfig] = useState<RetrievalConfig | null>(null);
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

  const t = UI_TEXT[language];
  const overreachLabels: Record<string, string> = OVERREACH_LABELS[language];
  const isAuthenticated = Boolean(token && user);
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
  const latestHitKbCodes = useMemo(() => {
    if (!activeResponse) return [];
    return [...new Set(activeResponse.citations.map((item) => item.kb_code))];
  }, [activeResponse]);
  const localAuditRecords = useMemo(
    () => collectLocalAuditRecords(visibleChatSessions, t.untitledSession),
    [t.untitledSession, visibleChatSessions]
  );

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
        setKnowledgeBases(kbs);
        setMessage("");
      } catch {
        clearAuthSession();
        if (cancelled) return;
        setToken("");
        setUser(null);
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
      setKbDocumentsByKbId({});
      setChunksByDocumentId({});
      setSelectedKnowledgeBaseId("");
      setSelectedDocumentId("");
      setTraceRequestId("");
      setRequestTrace(null);
      setRetrievalConfig(null);
      return;
    }
    const storedSessions = readChatSessions(user.email);
    const nextSessions = storedSessions.length > 0 ? storedSessions : [createEmptyChatSession()];
    setHistoryOwnerEmail(user.email);
    setChatSessions(nextSessions);
    setActiveSessionId(nextSessions[0].id);
  }, [user?.email]);

  useEffect(() => {
    if (!user?.email || historyOwnerEmail !== user.email) return;
    saveChatSessions(user.email, chatSessions);
  }, [chatSessions, historyOwnerEmail, user?.email]);

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
      setTracePending(false);
      return;
    }
    let cancelled = false;
    setTracePending(true);
    async function loadTrace() {
      try {
        const payload = await getRequestTrace(token, traceRequestId);
        if (!cancelled) setRequestTrace(payload);
      } catch {
        if (!cancelled) setRequestTrace(null);
      } finally {
        if (!cancelled) setTracePending(false);
      }
    }
    void loadTrace();
    return () => {
      cancelled = true;
    };
  }, [token, traceRequestId]);

  const roleBadgeClass = useMemo(() => {
    const role = user?.role ?? "";
    if (role.includes("admin")) return "bg-accent-100 text-accent-800 border-accent-200";
    if (role === "visitor") return "bg-amber-100 text-amber-800 border-amber-200";
    return "bg-slate-100 text-slate-800 border-slate-200";
  }, [user?.role]);

  const navItems: Array<{ key: AppView; label: string }> = [
    { key: "knowledge_chat", label: t.navKnowledgeChat },
    { key: "knowledge_bases", label: t.navKnowledgeBases },
    { key: "audit_logs", label: t.navAuditLogs },
    { key: "system_status", label: t.navSystemStatus },
    { key: "developer_trace", label: t.navDeveloperTrace }
  ];

  function formatBoolean(value: boolean | null | undefined): string {
    if (value === null || value === undefined) return t.noValue;
    return value ? t.yes : t.no;
  }

  function formatCacheState(response: AskResponse | null): string {
    if (!response) return t.cacheNotRequested;
    return response.cache_hit ? t.cacheHit : t.cacheMiss;
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

  function resetAskState() {
    setAuditLogs([]);
    setQuestion("");
    setSelectedKbCodes([]);
  }

  function applyDemoAccount(account: DemoAccountKey) {
    setSelectedDemoAccount(account);
    setEmail(DEMO_ACCOUNTS[account].email);
    setPassword(DEMO_ACCOUNTS[account].password);
  }

  function applyAuthenticatedSession(accessToken: string, nextUser: UserPublic, kbs: KnowledgeBase[]) {
    setToken(accessToken);
    setUser(nextUser);
    setKnowledgeBases(kbs);
    saveAuthSession(accessToken, nextUser);
  }

  async function loginByCredentials(loginEmail: string, loginPassword: string) {
    const response = await login(loginEmail, loginPassword);
    const kbs = await listKnowledgeBases(response.access_token);
    applyAuthenticatedSession(response.access_token, response.user, kbs);
    return { token: response.access_token, user: response.user, kbs };
  }

  function logout() {
    clearAuthSession();
    setToken("");
    setUser(null);
    setKnowledgeBases([]);
    setKbDocumentsByKbId({});
    setChunksByDocumentId({});
    setSelectedKnowledgeBaseId("");
    setSelectedDocumentId("");
    setTraceRequestId("");
    setRequestTrace(null);
    setRetrievalConfig(null);
    setMessage("");
    setHistoryOwnerEmail("");
    setChatSessions([]);
    setActiveSessionId("");
    setActiveView("knowledge_chat");
    resetAskState();
  }

  async function onLogin(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setMessage("");
    try {
      await loginByCredentials(email, password);
      resetAskState();
      setMessage(t.loginSuccess);
    } catch (error) {
      setMessage(error instanceof Error ? `${t.loginFailed} ${error.message}` : t.loginFailed);
      clearAuthSession();
      setToken("");
      setUser(null);
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

  function toggleKb(code: string) {
    setSelectedKbCodes((prev) =>
      prev.includes(code) ? prev.filter((item) => item !== code) : [...prev, code]
    );
  }

  async function onSelectKnowledgeBase(kbId: string) {
    if (!token) return;
    setSelectedKnowledgeBaseId(kbId);
    setSelectedDocumentId("");
    if (kbDocumentsByKbId[kbId]) return;
    setViewerPending(true);
    try {
      const documents = await listKnowledgeBaseDocuments(token, kbId);
      setKbDocumentsByKbId((prev) => ({ ...prev, [kbId]: documents }));
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

  function openTraceView(requestId: string) {
    setTraceRequestId(requestId);
    setActiveView("developer_trace");
  }

  if (!sessionReady) {
    return (
      <div className="min-h-screen bg-slate-100">
        <div className="mx-auto flex min-h-screen max-w-5xl items-center justify-center px-6">
          <div className="glass-panel px-6 py-5 text-sm text-slate-600">{message || t.restoringSession}</div>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-slate-100">
        <div className="mx-auto w-full max-w-6xl px-4 py-8 md:px-8">
          <div className="mb-6 flex items-center justify-end gap-2">
            <label className="text-xs text-slate-600" htmlFor="login-language-select">
              {t.language}
            </label>
            <select
              id="login-language-select"
              className="h-9 rounded-xl border border-slate-300 bg-white px-2 text-xs text-slate-700"
              value={language}
              onChange={(event) => setLanguage(event.target.value as Language)}
            >
              <option value="zh">{t.chinese}</option>
              <option value="en">{t.english}</option>
            </select>
          </div>

          <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
            <section className="glass-panel p-8">
              <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">
                {t.consoleLabel}
              </div>
              <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900 md:text-3xl">
                {t.productName}
              </h1>
              <p className="mt-2 text-sm text-slate-600">{t.loginPageTagline}</p>
              <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-600">
                  {t.capabilityTitle}
                </p>
                <ul className="mt-3 space-y-2 text-sm text-slate-700">
                  <li>{t.capabilityA}</li>
                  <li>{t.capabilityB}</li>
                  <li>{t.capabilityC}</li>
                </ul>
              </div>
            </section>

            <section className="glass-panel p-8">
              <h2 className="panel-title">{t.signInPanelTitle}</h2>
              <form className="space-y-3" onSubmit={onLogin}>
                <fieldset className="space-y-2">
                  <legend className="sr-only">{t.demoAccount}</legend>
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-xs font-medium text-slate-600">{t.chooseDemoAccount}</span>
                    <span className="text-[11px] text-slate-500">{t.demoAccountHint}</span>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {(Object.keys(DEMO_ACCOUNTS) as DemoAccountKey[]).map((key) => {
                      const account = DEMO_ACCOUNTS[key];
                      const isSelected = selectedDemoAccount === key;
                      return (
                        <button
                          key={key}
                          aria-pressed={isSelected}
                          className={`min-h-[64px] rounded-xl border px-3 py-2 text-left transition focus:outline-none focus:ring-2 focus:ring-accent-200 ${
                            isSelected
                              ? "border-accent-500 bg-accent-50 ring-1 ring-accent-200"
                              : "border-slate-200 bg-slate-50 hover:border-accent-200 hover:bg-white"
                          }`}
                          onClick={() => applyDemoAccount(key)}
                          type="button"
                        >
                          <span className="flex items-center justify-between gap-2">
                            <span
                              className={`font-mono text-sm font-semibold ${
                                isSelected ? "text-accent-800" : "text-slate-800"
                              }`}
                            >
                              {account.label}
                            </span>
                            <span
                              className={`h-2 w-2 shrink-0 rounded-full ${
                                isSelected ? "bg-accent-600" : "bg-slate-300"
                              }`}
                            />
                          </span>
                          <span className="mt-1 block truncate text-[11px] text-slate-500">{account.email}</span>
                        </button>
                      );
                    })}
                  </div>
                </fieldset>

                <label className="block space-y-1">
                  <span className="text-xs font-medium text-slate-600">{t.email}</span>
                  <input
                    className="field"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="cn_staff@example.local"
                    autoComplete="username"
                  />
                </label>

                <label className="block space-y-1">
                  <span className="text-xs font-medium text-slate-600">{t.password}</span>
                  <input
                    className="field"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    type="password"
                    placeholder="Passw0rd!123"
                    autoComplete="current-password"
                  />
                </label>

                <button className="btn-primary w-full" disabled={pending}>
                  {pending ? t.working : t.signIn}
                </button>
              </form>

              {message ? <div className="mt-3 notification-line">{message}</div> : null}
            </section>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <div className="mx-auto w-full max-w-[1540px] px-4 py-5 md:px-8">
        <header className="glass-panel mb-5 flex flex-wrap items-center justify-between gap-4 px-5 py-4">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">
              {t.consoleLabel}
            </div>
            <h1 className="text-lg font-semibold tracking-tight text-slate-900 md:text-2xl">
              {t.productName}
            </h1>
            <p className="mt-1 text-sm text-slate-600">{t.subtitle}</p>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <label className="text-xs text-slate-600" htmlFor="ui-language-select">
              {t.language}
            </label>
            <select
              id="ui-language-select"
              className="h-9 rounded-xl border border-slate-300 bg-white px-2 text-xs text-slate-700"
              value={language}
              onChange={(event) => setLanguage(event.target.value as Language)}
            >
              <option value="zh">{t.chinese}</option>
              <option value="en">{t.english}</option>
            </select>
            <div className={`status-pill ${roleBadgeClass}`}>
              {user ? `${t.signedInAs} · ${user.role}` : t.accountState}
            </div>
            <button className="btn-secondary" onClick={logout} type="button">
              {t.logout}
            </button>
          </div>
        </header>

        <div className="grid gap-4 xl:grid-cols-[260px_minmax(0,1fr)]">
          <aside className="space-y-4">
            <section className="glass-panel p-4">
              <h2 className="panel-title">{t.navTitle}</h2>
              <div className="space-y-2">
                {navItems.map((item) => (
                  <button
                    key={item.key}
                    className={`w-full rounded-xl border px-3 py-2 text-left text-sm transition ${
                      activeView === item.key
                        ? "border-accent-300 bg-accent-50 text-accent-800"
                        : "border-slate-200 bg-slate-50 text-slate-700 hover:border-accent-200 hover:bg-white"
                    }`}
                    onClick={() => setActiveView(item.key)}
                    type="button"
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </section>

            <section className="glass-panel p-4">
              <h2 className="panel-title">{t.currentSession}</h2>
              <div className="space-y-1 text-xs text-slate-700">
                <div>
                  {t.currentUser}: <span className="font-mono">{user?.email ?? t.noValue}</span>
                </div>
                <div>
                  {t.currentRole}: <span className="font-mono">{user?.role ?? t.noValue}</span>
                </div>
                <div>
                  {t.currentDepartment}: <span className="font-mono">{user?.department ?? t.noValue}</span>
                </div>
              </div>
            </section>
          </aside>

          <main className="space-y-4">
            {activeView === "knowledge_chat" ? (
              <section className="glass-panel overflow-hidden">
                <div className="grid gap-0 xl:grid-cols-[280px_minmax(0,1fr)]">
                  <div className="border-b border-slate-200 bg-slate-50 p-4 xl:border-b-0 xl:border-r">
                    <div className="mb-3 flex items-center justify-between gap-2">
                      <h2 className="panel-title mb-0">{t.recentSessions}</h2>
                      <button className="btn-secondary px-2 py-1 text-xs" onClick={startNewSession} type="button">
                        {t.newSession}
                      </button>
                    </div>
                    <div className="space-y-2">
                      {visibleChatSessions.length === 0 ? (
                        <p className="text-sm text-slate-500">{t.noRecentSessions}</p>
                      ) : (
                        visibleChatSessions.map((session) => {
                          const isActive = activeChatSession?.id === session.id;
                          return (
                            <button
                              key={session.id}
                              className={`w-full rounded-xl border px-3 py-2 text-left transition ${
                                isActive
                                  ? "border-accent-300 bg-accent-50"
                                  : "border-slate-200 bg-white hover:border-accent-200"
                              }`}
                              onClick={() => selectChatSession(session.id)}
                              type="button"
                            >
                              <div className="truncate text-sm font-medium text-slate-800">
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
                      {t.clearCurrentSession}
                    </button>
                    <p className="mt-2 text-[11px] text-slate-500">{t.historyStoredLocally}</p>
                  </div>

                  <div className="flex min-h-[700px] flex-col">
                    <div className="border-b border-slate-200 px-5 py-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <h2 className="text-base font-semibold text-slate-900">{t.askQuestionSection}</h2>
                          <p className="mt-1 text-xs text-slate-500">{t.chatPageDescription}</p>
                        </div>
                        <div className={`risk-badge ${deniedThisRequest ? "is-risk" : "is-normal"}`}>
                          {deniedThisRequest ? t.riskAlert : t.normalState}
                        </div>
                      </div>
                    </div>

                    <div className="flex-1 space-y-4 overflow-y-auto px-4 py-5 md:px-6">
                      {!activeChatSession || activeChatSession.messages.length === 0 ? (
                        <div className="flex min-h-[320px] items-center justify-center text-center">
                          <p className="text-sm text-slate-500">{t.emptyConversation}</p>
                        </div>
                      ) : (
                        activeChatSession.messages.map((chatMessage) => {
                          const isUserMessage = chatMessage.role === "user";
                          return (
                            <div key={chatMessage.id} className={`flex ${isUserMessage ? "justify-end" : "justify-start"}`}>
                              <article
                                className={`max-w-[90%] rounded-2xl border px-4 py-3 shadow-sm md:max-w-[80%] ${
                                  isUserMessage
                                    ? "border-accent-200 bg-accent-600 text-white"
                                    : chatMessage.error
                                      ? "border-red-200 bg-red-50 text-red-800"
                                      : "border-slate-200 bg-white text-slate-800"
                                }`}
                              >
                                <div
                                  className={`mb-2 flex flex-wrap items-center gap-2 text-[11px] ${
                                    isUserMessage ? "text-accent-50" : "text-slate-500"
                                  }`}
                                >
                                  <span className="font-semibold">
                                    {isUserMessage ? t.userMessageLabel : t.assistantMessageLabel}
                                  </span>
                                  <span>{formatDateTime(chatMessage.createdAt, language)}</span>
                                  {chatMessage.mode ? <span className="font-mono">{chatMessage.mode}</span> : null}
                                </div>
                                <div className="whitespace-pre-wrap text-sm leading-6">{chatMessage.content}</div>

                                {isUserMessage ? (
                                  <div className="mt-2 text-[11px] text-accent-50">
                                    {t.selectedKbScope}: {formatKbScope(chatMessage.kbCodes)}
                                  </div>
                                ) : null}

                                {chatMessage.response?.denied ? (
                                  <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                                    <div className="text-[11px] font-semibold uppercase tracking-wide">{t.riskAlert}</div>
                                    <div className="mt-1">{chatMessage.response.refusal_reason ?? t.requestDeniedPrefix}</div>
                                  </div>
                                ) : null}

                                {chatMessage.response && chatMessage.response.citations.length > 0 ? (
                                  <div className="mt-3 border-t border-slate-200 pt-3">
                                    <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                                      {t.citations}
                                    </p>
                                    <div className="space-y-2">
                                      {chatMessage.response.citations.map((item) => (
                                        <div key={item.chunk_id} className="rounded-xl bg-slate-50 px-3 py-2">
                                          <div className="font-mono text-[11px] text-slate-700">
                                            {item.kb_code} / {item.document_title} / {t.score}={item.score}
                                          </div>
                                          <div className="mt-1 font-mono text-[11px] text-slate-500">
                                            chunk_id: {item.chunk_id}
                                          </div>
                                          <p className="mt-1 text-xs leading-5 text-slate-600">{item.excerpt}</p>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                ) : null}

                                {chatMessage.response ? (
                                  <div className="mt-3 space-y-2">
                                    <button
                                      className="btn-secondary px-2 py-1 text-xs"
                                      type="button"
                                      onClick={() => openTraceView(chatMessage.response!.request_id)}
                                    >
                                      {t.traceViewAction}
                                    </button>
                                    <details className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
                                      <summary className="cursor-pointer font-medium text-slate-700">
                                        {t.technicalDetails}
                                      </summary>
                                      <div className="mt-2 space-y-1 font-mono text-[11px]">
                                        <div>request_id: {chatMessage.response.request_id}</div>
                                        <div>cache_hit: {String(chatMessage.response.cache_hit)}</div>
                                        <div>mode: {chatMessage.response.mode}</div>
                                        <div>
                                          router: {chatMessage.response.router_mode}/{chatMessage.response.router_model}
                                        </div>
                                        <div>router_fallback_used: {String(chatMessage.response.router_fallback_used)}</div>
                                        {chatMessage.response.router_error ? (
                                          <div>router_error: {chatMessage.response.router_error}</div>
                                        ) : null}
                                        <div>
                                          function_trace_summary:{" "}
                                          {(chatMessage.response.function_trace_summary ?? []).join(" | ") || "-"}
                                        </div>
                                        <div>allowed_kb_ids(frontend): {knowledgeBases.map((kb) => kb.id).join(", ") || "-"}</div>
                                      </div>
                                    </details>
                                  </div>
                                ) : null}
                              </article>
                            </div>
                          );
                        })
                      )}
                    </div>

                    <form className="border-t border-slate-200 bg-slate-50 p-4" onSubmit={onAsk}>
                      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_180px]">
                        <textarea
                          className="soft-textarea min-h-24 bg-white"
                          value={question}
                          onChange={(event) => setQuestion(event.target.value)}
                          placeholder={t.askQuestionPlaceholder}
                        />
                        <div className="space-y-2">
                          <label className="block space-y-1">
                            <span className="text-xs font-medium text-slate-600">{t.mode}</span>
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
                            {pending ? t.working : t.sendQuestion}
                          </button>
                        </div>
                      </div>

                      <div className="mt-3">
                        <p className="mb-2 text-xs font-medium text-slate-600">{t.kbScopeOptional}</p>
                        <div className="flex flex-wrap gap-2">
                          {knowledgeBases.map((kb) => (
                            <label key={kb.id} className="tag-check bg-white">
                              <input
                                type="checkbox"
                                checked={selectedKbCodes.includes(kb.code)}
                                onChange={() => toggleKb(kb.code)}
                              />
                              <span className="font-mono text-xs">{kb.code}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                    </form>

                    {message ? <div className="border-t border-slate-200 px-4 py-3 notification-line">{message}</div> : null}
                  </div>
                </div>
              </section>
            ) : null}

            {activeView === "knowledge_bases" ? (
              <section className="glass-panel p-5">
                <h2 className="panel-title">{t.knowledgeBasesPageTitle}</h2>
                <p className="mb-4 text-sm text-slate-600">{t.knowledgeBasesPageHint}</p>
                <p className="mb-4 text-xs text-slate-500">{t.allowedScopeHint}</p>

                <div className="grid gap-4 xl:grid-cols-[minmax(0,520px)_minmax(0,1fr)]">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                    <div className="overflow-x-auto">
                      <table className="w-full border-collapse text-left text-sm">
                        <thead>
                          <tr className="border-b border-slate-200 text-slate-600">
                            <th className="px-2 py-2">kb_id</th>
                            <th className="px-2 py-2">{t.knowledgeBaseCode}</th>
                            <th className="px-2 py-2">{t.kbDisplayName}</th>
                            <th className="px-2 py-2">{t.kbLanguage}</th>
                            <th className="px-2 py-2">{t.kbDepartment}</th>
                            <th className="px-2 py-2"></th>
                          </tr>
                        </thead>
                        <tbody>
                          {knowledgeBases.map((kb) => {
                            const selected = selectedKnowledgeBaseId === kb.id;
                            return (
                              <tr key={kb.id} className={`border-b border-slate-100 ${selected ? "bg-white" : ""}`}>
                                <td className="px-2 py-2 font-mono text-xs">{kb.id}</td>
                                <td className="px-2 py-2 font-mono text-xs">{kb.code}</td>
                                <td className="px-2 py-2">{kb.display_name || kb.name}</td>
                                <td className="px-2 py-2">
                                  {kb.language === "zh"
                                    ? t.languageChinese
                                    : kb.language === "en"
                                      ? t.languageEnglish
                                      : kb.language}
                                </td>
                                <td className="px-2 py-2 font-mono text-xs">{kb.department ?? t.noValue}</td>
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
                        <p className="text-sm font-medium text-slate-700">{t.documentsPanelTitle}</p>
                        <div className="text-xs text-slate-500">
                          {t.selectedKnowledgeBase}:{" "}
                          <span className="font-mono text-slate-700">
                            {selectedKnowledgeBase?.code ?? t.noValue}
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
                                      <button
                                        className="btn-secondary px-2 py-1 text-xs"
                                        type="button"
                                        onClick={() => onSelectDocument(doc.id)}
                                      >
                                        {t.viewChunks}
                                      </button>
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
                          <span className="font-mono text-slate-700">
                            {selectedDocument?.id ?? t.noValue}
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
                                    <div className="font-mono text-slate-700">{t.chunkId}: {chunk.id}</div>
                                    <div className="text-slate-600">{t.embeddingStatus}: {chunk.has_embedding ? t.embeddingPresent : t.embeddingMissing}</div>
                                    <div className="text-slate-600">{t.embeddingDimension}: {chunk.embedding_dimension}</div>
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
              <section className="glass-panel p-5">
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
                    {user?.role?.includes("admin") ? (
                      <button className="btn-secondary" onClick={onLoadAdminAudit} disabled={pending} type="button">
                        {t.loadAuditLogs}
                      </button>
                    ) : null}
                  </div>
                  {user?.role?.includes("admin") ? (
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
              <section className="glass-panel p-5">
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

            {activeView === "developer_trace" ? (
              <section className="space-y-4">
                <div className="glass-panel p-5">
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

                <div className="glass-panel p-5">
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

                <div className="glass-panel p-5">
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

                <div className="glass-panel p-5">
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
