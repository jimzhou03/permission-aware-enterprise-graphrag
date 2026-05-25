import { useEffect, useMemo, useState } from "react";

import {
  askQuestion,
  fetchAuthMe,
  getRequestDetail,
  listAuditLogs,
  listKnowledgeBases,
  login
} from "./api";
import { LANGUAGE_STORAGE_KEY, OVERREACH_LABELS, UI_TEXT, type Language } from "./i18n";
import type { AskMode, AskResponse, AuditLog, KnowledgeBase, UserPublic } from "./types";

type DemoAccountKey = "cn_staff" | "en_staff" | "bilingual_admin" | "visitor";

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

function sortSessions(sessions: ChatSession[]): ChatSession[] {
  return [...sessions].sort(
    (first, second) => new Date(second.updatedAt).getTime() - new Date(first.updatedAt).getTime()
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

export default function App() {
  const [language, setLanguage] = useState<Language>(getInitialLanguage);
  const [selectedDemoAccount, setSelectedDemoAccount] = useState<DemoAccountKey>("cn_staff");
  const [email, setEmail] = useState(DEMO_ACCOUNTS.cn_staff.email);
  const [password, setPassword] = useState(DEMO_ACCOUNTS.cn_staff.password);
  const [token, setToken] = useState<string>("");
  const [user, setUser] = useState<UserPublic | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
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
  const activeRequestDetail = activeAuditMessage?.requestDetail ?? null;
  const deniedThisRequest = activeResponse?.denied ?? false;
  const latestHitKbCodes = useMemo(() => {
    if (!activeResponse) return [];
    return [...new Set(activeResponse.citations.map((item) => item.kb_code))];
  }, [activeResponse]);

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

  const roleBadgeClass = useMemo(() => {
    const role = user?.role ?? "";
    if (role.includes("admin")) return "bg-accent-100 text-accent-800 border-accent-200";
    if (role === "visitor") return "bg-amber-100 text-amber-800 border-amber-200";
    return "bg-slate-100 text-slate-800 border-slate-200";
  }, [user?.role]);

  function formatBoolean(value: boolean | null | undefined): string {
    if (value === null || value === undefined) return t.noValue;
    return value ? t.yes : t.no;
  }

  function formatCacheState(response: AskResponse | null): string {
    if (!response) return t.cacheNotRequested;
    return response.cache_hit ? t.cacheHit : t.cacheMiss;
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
    setMessage("");
    setHistoryOwnerEmail("");
    setChatSessions([]);
    setActiveSessionId("");
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

        <div className="grid gap-4 xl:grid-cols-[300px_minmax(0,1fr)_360px]">
          <aside className="space-y-4">
            <section className="glass-panel p-5">
              <h2 className="panel-title">{t.currentSession}</h2>
              <div className="grid gap-2 text-xs text-slate-700">
                <div>
                  {t.currentUser}: <span className="font-mono">{user?.email ?? t.noValue}</span>
                </div>
                <div>
                  {t.currentRole}: <span className="font-mono">{user?.role ?? t.noValue}</span>
                </div>
                <div>
                  {t.currentDepartment}:{" "}
                  <span className="font-mono">{user?.department ?? t.noValue}</span>
                </div>
              </div>
            </section>

            <section className="glass-panel p-5">
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
                            : "border-slate-200 bg-slate-50 hover:border-accent-200 hover:bg-white"
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
              <p className="mt-2 text-[11px] leading-5 text-slate-500">{t.historyStoredLocally}</p>
            </section>

            <section className="glass-panel p-5">
              <h2 className="panel-title">{t.accessibleKnowledgeBases}</h2>
              <div className="flex flex-wrap gap-2">
                {knowledgeBases.map((kb) => (
                  <span key={kb.id} className="tag-pill">
                    {kb.code}
                  </span>
                ))}
              </div>
              <p className="mt-2 text-[11px] leading-5 text-slate-500">{t.allowedKbHint}</p>

              <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-3">
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-600">
                  {t.modelStatus}
                </p>
                <div className="space-y-1 text-xs text-slate-700">
                  <div>{t.routerStatus}</div>
                  <div>{t.generatorStatus}</div>
                  <div>
                    {t.cacheLayer}: {formatCacheState(activeResponse)}
                  </div>
                </div>
              </div>
            </section>
          </aside>

          <main className="min-h-[calc(100vh-140px)]">
            <section className="glass-panel flex min-h-[680px] flex-col overflow-hidden">
              <div className="border-b border-slate-200 px-5 py-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="text-base font-semibold text-slate-900">{t.askQuestionSection}</h2>
                    <p className="mt-1 max-w-2xl truncate text-xs text-slate-500">
                      {activeChatSession ? getSessionTitle(activeChatSession, t.untitledSession) : t.untitledSession}
                    </p>
                  </div>
                  <div className={`risk-badge ${deniedThisRequest ? "is-risk" : "is-normal"}`}>
                    {deniedThisRequest ? t.riskAlert : t.normalState}
                  </div>
                </div>
              </div>

              <div className="flex-1 space-y-4 overflow-y-auto px-4 py-5 md:px-6">
                {!activeChatSession || activeChatSession.messages.length === 0 ? (
                  <div className="flex min-h-[360px] items-center justify-center text-center">
                    <div>
                      <p className="text-sm text-slate-500">{t.emptyConversation}</p>
                    </div>
                  </div>
                ) : (
                  activeChatSession.messages.map((chatMessage) => {
                    const isUserMessage = chatMessage.role === "user";
                    return (
                      <div
                        key={chatMessage.id}
                        className={`flex ${isUserMessage ? "justify-end" : "justify-start"}`}
                      >
                        <article
                          className={`max-w-[88%] rounded-2xl border px-4 py-3 shadow-sm md:max-w-[78%] ${
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
                              <div className="text-[11px] font-semibold uppercase tracking-wide">
                                {t.riskAlert}
                              </div>
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
                                    <p className="mt-1 text-xs leading-5 text-slate-600">{item.excerpt}</p>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ) : null}

                          {chatMessage.response ? (
                            <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                              <span
                                className={`rounded-full px-2 py-1 ${
                                  isUserMessage ? "bg-accent-500 text-white" : "bg-slate-100 text-slate-600"
                                }`}
                              >
                                {t.requestId}: {chatMessage.response.request_id}
                              </span>
                              <span
                                className={`rounded-full px-2 py-1 ${
                                  isUserMessage ? "bg-accent-500 text-white" : "bg-slate-100 text-slate-600"
                                }`}
                              >
                                {t.cacheStatus}: {formatCacheState(chatMessage.response)}
                              </span>
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
            </section>
          </main>

          <section className="space-y-4">
            <div className="glass-panel p-5">
              <h2 className="panel-title">{t.auditPanelTitle}</h2>
              {activeResponse ? (
                <div className="space-y-3">
                  <div className="grid gap-2 text-xs text-slate-700">
                    <div className="flex items-center justify-between gap-3">
                      <span>{t.requestId}</span>
                      <span className="truncate font-mono">{activeResponse.request_id}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span>{t.responseMode}</span>
                      <span className="font-mono">{activeResponse.mode}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span>{t.deniedCurrentRequest}</span>
                      <span className={`font-mono ${deniedThisRequest ? "text-red-700" : "text-emerald-700"}`}>
                        {formatBoolean(activeResponse.denied)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span>{t.cacheStatus}</span>
                      <span className="font-mono">{formatCacheState(activeResponse)}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span>{t.model}</span>
                      <span className="truncate font-mono">{activeRequestDetail?.model ?? t.noValue}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span>{t.latency}</span>
                      <span className="font-mono">
                        {activeRequestDetail ? `${activeRequestDetail.latency_ms} ${t.milliseconds}` : t.noValue}
                      </span>
                    </div>
                  </div>
                  <p className="text-[11px] leading-5 text-slate-500">{t.cacheFieldHint}</p>
                </div>
              ) : (
                <p className="text-sm text-slate-500">{t.noAuditForSession}</p>
              )}
            </div>

            <div className="glass-panel p-5">
              <h2 className="panel-title">{t.authorizationPanelTitle}</h2>
              <div className="space-y-3 text-xs text-slate-700">
                <div>
                  <p className="mb-2 font-medium text-slate-600">{t.hitKnowledgeBases}</p>
                  <div className="flex flex-wrap gap-2">
                    {latestHitKbCodes.length > 0 ? (
                      latestHitKbCodes.map((code) => (
                        <span key={code} className="tag-pill hit">
                          {code}
                        </span>
                      ))
                    ) : (
                      <span className="text-slate-500">{t.noValue}</span>
                    )}
                  </div>
                </div>

                <div className={deniedThisRequest ? "risk-panel" : "rounded-2xl border border-emerald-200 bg-emerald-50 px-3 py-2"}>
                  <div className={`text-[11px] font-semibold uppercase tracking-wide ${deniedThisRequest ? "text-red-700" : "text-emerald-700"}`}>
                    {deniedThisRequest ? t.riskAlert : t.notDenied}
                  </div>
                  {deniedThisRequest ? (
                    <p className="mt-1 text-sm text-red-700">
                      {activeResponse?.refusal_reason ?? t.requestDeniedPrefix}
                    </p>
                  ) : null}
                </div>

                {activeRequestDetail ? (
                  <details className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                    <summary className="cursor-pointer text-xs font-medium text-slate-700">
                      {t.rawAuditJson}
                    </summary>
                    <pre className="answer-block mt-3 max-h-[260px]">
                      {JSON.stringify(activeRequestDetail, null, 2)}
                    </pre>
                  </details>
                ) : null}
              </div>
            </div>

            <div className="glass-panel p-5">
              <div className="flex items-center justify-between gap-3">
                <h2 className="panel-title mb-0">{t.securityTestScenarios}</h2>
                <button
                  className="btn-secondary"
                  type="button"
                  onClick={() => setSecurityOpen((prev) => !prev)}
                >
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

            {user?.role?.includes("admin") ? (
              <div className="glass-panel p-5">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <h2 className="panel-title mb-0">{t.adminAuditLogs}</h2>
                  <button className="btn-secondary" onClick={onLoadAdminAudit} disabled={pending} type="button">
                    {t.loadAuditLogs}
                  </button>
                </div>
                {auditLogs.length > 0 ? (
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
                  <p className="text-sm text-slate-500">{t.noRequestDetailLoaded}</p>
                )}
              </div>
            ) : null}
          </section>
        </div>
      </div>
    </div>
  );
}
