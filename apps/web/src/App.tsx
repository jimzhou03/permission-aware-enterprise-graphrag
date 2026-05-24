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

type DemoAccountKey = "admin" | "hr" | "finance" | "tech" | "visitor";

const AUTH_SESSION_STORAGE_KEY = "paegr.auth.session";

const DEMO_ACCOUNTS: Record<
  DemoAccountKey,
  { label: string; email: string; password: string }
> = {
  admin: {
    label: "admin",
    email: "admin@example.local",
    password: "Passw0rd!123"
  },
  hr: {
    label: "hr",
    email: "hr@example.local",
    password: "Passw0rd!123"
  },
  finance: {
    label: "finance",
    email: "finance@example.local",
    password: "Passw0rd!123"
  },
  tech: {
    label: "tech",
    email: "tech@example.local",
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
    account: "hr",
    question: "请说明 finance budget approval workflow。"
  },
  {
    id: "finance_tech_secret",
    account: "finance",
    question: "请给出 tech release key management details。"
  },
  {
    id: "tech_hr_profile",
    account: "tech",
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

export default function App() {
  const [language, setLanguage] = useState<Language>(getInitialLanguage);
  const [selectedDemoAccount, setSelectedDemoAccount] = useState<DemoAccountKey>("hr");
  const [email, setEmail] = useState(DEMO_ACCOUNTS.hr.email);
  const [password, setPassword] = useState(DEMO_ACCOUNTS.hr.password);
  const [token, setToken] = useState<string>("");
  const [user, setUser] = useState<UserPublic | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<AskMode>("auto");
  const [selectedKbCodes, setSelectedKbCodes] = useState<string[]>([]);
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [requestDetail, setRequestDetail] = useState<AuditLog | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [sessionReady, setSessionReady] = useState(false);
  const [securityOpen, setSecurityOpen] = useState(false);

  const t = UI_TEXT[language];
  const overreachLabels = OVERREACH_LABELS[language];
  const isAuthenticated = Boolean(token && user);
  const deniedThisRequest = answer?.denied ?? false;

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

  const roleBadgeClass = useMemo(() => {
    const role = user?.role ?? "";
    if (role === "admin") return "bg-accent-100 text-accent-800 border-accent-200";
    if (role === "visitor") return "bg-amber-100 text-amber-800 border-amber-200";
    return "bg-slate-100 text-slate-800 border-slate-200";
  }, [user?.role]);

  const latestHitKbCodes = useMemo(() => {
    if (!answer) return [];
    return [...new Set(answer.citations.map((item) => item.kb_code))];
  }, [answer]);

  function resetAskState() {
    setAnswer(null);
    setRequestDetail(null);
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

  async function submitQuestion(nextToken: string, nextQuestion: string, nextMode: AskMode) {
    const response = await askQuestion(nextToken, nextQuestion.trim(), nextMode, selectedKbCodes);
    setAnswer(response);
    const detail = await getRequestDetail(nextToken, response.request_id);
    setRequestDetail(detail);
    setMessage(
      response.denied
        ? `${t.requestDeniedPrefix}: ${response.refusal_reason ?? "forbidden"}`
        : response.cache_hit
          ? t.answerServedFromCache
          : t.answerGenerated
    );
  }

  async function onAsk(event: React.FormEvent) {
    event.preventDefault();
    if (!token || !question.trim()) return;
    setPending(true);
    setMessage("");
    try {
      await submitQuestion(token, question, mode);
    } catch (error) {
      setMessage(error instanceof Error ? `${t.askFailed} ${error.message}` : t.askFailed);
    } finally {
      setPending(false);
    }
  }

  async function runOverreachScenario(scenario: (typeof OVERREACH_SCENARIOS)[number]) {
    setPending(true);
    setMessage("");
    try {
      applyDemoAccount(scenario.account);
      const account = DEMO_ACCOUNTS[scenario.account];
      const session = await loginByCredentials(account.email, account.password);
      setQuestion(scenario.question);
      setMode("auto");
      await submitQuestion(session.token, scenario.question, "auto");
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
              <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">{t.consoleLabel}</div>
              <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900 md:text-3xl">
                Permission-Aware Enterprise GraphRAG Assistant
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
              <h2 className="panel-title">{t.login}</h2>
              <form className="space-y-3" onSubmit={onLogin}>
                <label className="block space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-slate-600">{t.demoAccount}</span>
                    <span className="text-[11px] text-slate-500">{t.demoAccountHint}</span>
                  </div>
                  <select
                    className="field"
                    value={selectedDemoAccount}
                    onChange={(event) => applyDemoAccount(event.target.value as DemoAccountKey)}
                  >
                    {(Object.keys(DEMO_ACCOUNTS) as DemoAccountKey[]).map((key) => (
                      <option key={key} value={key}>
                        {DEMO_ACCOUNTS[key].label}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="block space-y-1">
                  <span className="text-xs font-medium text-slate-600">{t.email}</span>
                  <input
                    className="field"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="hr@example.local"
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
      <div className="mx-auto w-full max-w-[1500px] px-4 py-5 md:px-8">
        <header className="glass-panel mb-5 flex flex-wrap items-center justify-between gap-4 px-5 py-4">
          <div>
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">{t.consoleLabel}</div>
            <h1 className="text-lg font-semibold tracking-tight text-slate-900 md:text-2xl">
              Permission-Aware Enterprise GraphRAG Assistant
            </h1>
            <p className="mt-1 text-sm text-slate-600">{t.subtitle}</p>
          </div>
          <div className="flex items-center gap-2">
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
              {user ? `${user.role} · ${user.department ?? "none"}` : t.accountState}
            </div>
            <button className="btn-secondary" onClick={logout} type="button">
              {t.logout}
            </button>
          </div>
        </header>

        <div className="grid gap-4 xl:grid-cols-[300px_minmax(0,1fr)_340px]">
          <aside className="space-y-4">
            <section className="glass-panel p-5">
              <h2 className="panel-title">{t.currentSession}</h2>
              <div className="grid gap-2 text-xs text-slate-700">
                <div>
                  {t.currentUser}: <span className="font-mono">{user?.email ?? "-"}</span>
                </div>
                <div>
                  {t.currentRole}: <span className="font-mono">{user?.role ?? "-"}</span>
                </div>
              </div>

              <div className="mt-4">
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-600">
                  {t.accessibleKnowledgeBases}
                </p>
                <div className="flex flex-wrap gap-2">
                  {knowledgeBases.map((kb) => (
                    <span key={kb.id} className="tag-pill">
                      {kb.code}
                    </span>
                  ))}
                </div>
              </div>

              <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-3">
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-600">
                  {t.modelStatus}
                </p>
                <div className="space-y-1 text-xs text-slate-700">
                  <div>{t.routerStatus}</div>
                  <div>{t.generatorStatus}</div>
                </div>
              </div>
            </section>
          </aside>

          <main className="space-y-4">
            <section className="glass-panel p-5">
              <h2 className="panel-title">{t.askQuestionSection}</h2>
              <form className="space-y-3" onSubmit={onAsk}>
                <div className="grid gap-3 md:grid-cols-[1fr_170px]">
                  <textarea
                    className="soft-textarea"
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
                      {t.ask}
                    </button>
                  </div>
                </div>

                <div className="soft-card">
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-600">
                    {t.kbScopeOptional}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {knowledgeBases.map((kb) => (
                      <label key={kb.id} className="tag-check">
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

              {message ? <div className="mt-3 notification-line">{message}</div> : null}
            </section>

            <section className="glass-panel p-5">
              <div className="mb-3 flex items-start justify-between gap-3">
                <h2 className="panel-title">{t.latestResponse}</h2>
                <div className={`risk-badge ${deniedThisRequest ? "is-risk" : "is-normal"}`}>
                  {deniedThisRequest ? t.riskAlert : t.normalState}
                </div>
              </div>
              {!answer ? (
                <p className="text-sm text-slate-500">{t.noResponseYet}</p>
              ) : (
                <div className="space-y-3">
                  {deniedThisRequest ? (
                    <div className="risk-panel">
                      <div className="text-xs font-semibold uppercase tracking-wide text-red-700">
                        {t.requestDeniedPrefix}
                      </div>
                      <p className="mt-1 text-sm text-red-700">{answer.refusal_reason ?? "forbidden"}</p>
                    </div>
                  ) : null}

                  <pre className="answer-block">{answer.answer}</pre>

                  {answer.citations.length > 0 ? (
                    <div>
                      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-600">
                        {t.citations}
                      </p>
                      <div className="space-y-2">
                        {answer.citations.map((item) => (
                          <div key={item.chunk_id} className="soft-card">
                            <div className="font-mono text-xs text-slate-700">
                              {item.kb_code} / {item.document_title} / score={item.score}
                            </div>
                            <p className="mt-1 text-xs text-slate-600">{item.excerpt}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              )}
            </section>
          </main>

          <section className="space-y-4">
            <div className="glass-panel p-5">
              <h2 className="panel-title">{t.auditDetail}</h2>
              <div className="grid gap-2 text-xs text-slate-700">
                <div>
                  {t.requestId}: <span className="font-mono">{answer?.request_id ?? "-"}</span>
                </div>
                <div>
                  {t.deniedCurrentRequest}:{" "}
                  <span className={`font-mono ${deniedThisRequest ? "text-red-700" : "text-emerald-700"}`}>
                    {answer ? String(answer.denied) : "-"}
                  </span>
                </div>
                <div>
                  {t.hitKnowledgeBases}:{" "}
                  <span className="font-mono">
                    {latestHitKbCodes.length > 0 ? latestHitKbCodes.join(", ") : "-"}
                  </span>
                </div>
              </div>

              <div className="mt-4">
                {requestDetail ? (
                  <pre className="answer-block max-h-[260px]">{JSON.stringify(requestDetail, null, 2)}</pre>
                ) : (
                  <p className="text-sm text-slate-500">{t.noRequestDetailLoaded}</p>
                )}
              </div>
            </div>

            <div className="glass-panel p-5">
              <div className="flex items-center justify-between">
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

            {user?.role === "admin" ? (
              <div className="glass-panel p-5">
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="panel-title mb-0">{t.requestDetailAndAdminAudit}</h2>
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
                          <th className="px-2 py-2">{t.mode.toLowerCase()}</th>
                          <th className="px-2 py-2">denied</th>
                          <th className="px-2 py-2">cache_hit</th>
                        </tr>
                      </thead>
                      <tbody>
                        {auditLogs.map((row) => (
                          <tr key={row.request_id} className="border-b border-slate-100">
                            <td className="px-2 py-2 font-mono">{row.request_id}</td>
                            <td className="px-2 py-2 font-mono">{row.mode}</td>
                            <td className="px-2 py-2">{String(row.denied)}</td>
                            <td className="px-2 py-2">{String(row.cache_hit)}</td>
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
