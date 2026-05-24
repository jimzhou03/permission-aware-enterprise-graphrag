import { useEffect, useMemo, useState } from "react";

import { askQuestion, getRequestDetail, listAuditLogs, listKnowledgeBases, login } from "./api";
import { LANGUAGE_STORAGE_KEY, OVERREACH_LABELS, UI_TEXT, type Language } from "./i18n";
import type { AskMode, AskResponse, AuditLog, KnowledgeBase, UserPublic } from "./types";

type DemoAccountKey = "admin" | "hr" | "finance" | "tech" | "visitor";

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
  const [message, setMessage] = useState<string>("");

  const t = UI_TEXT[language];
  const overreachLabels = OVERREACH_LABELS[language];

  useEffect(() => {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  }, [language]);

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

  function applyDemoAccount(account: DemoAccountKey) {
    setSelectedDemoAccount(account);
    setEmail(DEMO_ACCOUNTS[account].email);
    setPassword(DEMO_ACCOUNTS[account].password);
  }

  async function loginByCredentials(loginEmail: string, loginPassword: string) {
    const response = await login(loginEmail, loginPassword);
    const kbs = await listKnowledgeBases(response.access_token);
    setToken(response.access_token);
    setUser(response.user);
    setKnowledgeBases(kbs);
    setSelectedKbCodes([]);
    setAuditLogs([]);
    return { token: response.access_token, user: response.user, kbs };
  }

  async function onLogin(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setMessage("");
    try {
      await loginByCredentials(email, password);
      setAnswer(null);
      setRequestDetail(null);
      setMessage(t.loginSuccess);
    } catch (error) {
      setMessage(error instanceof Error ? `${t.loginFailed} ${error.message}` : t.loginFailed);
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

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,#dff2ea_0%,#f1f5f9_40%,#f8fafc_100%)]">
      <div className="mx-auto w-full max-w-7xl px-4 py-6 md:px-8">
        <header className="mb-5 flex flex-wrap items-end justify-between gap-3 border-b border-slate-200 pb-4">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-slate-900 md:text-2xl">
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
              className="h-8 rounded-md border border-slate-300 bg-white px-2 text-xs text-slate-700"
              value={language}
              onChange={(event) => setLanguage(event.target.value as Language)}
            >
              <option value="zh">{t.chinese}</option>
              <option value="en">{t.english}</option>
            </select>
            {user ? (
              <div className={`rounded-md border px-3 py-1 text-xs font-medium ${roleBadgeClass}`}>
                {user.role} · {user.department ?? "none"} · {user.email}
              </div>
            ) : null}
          </div>
        </header>

        <div className="grid gap-4 lg:grid-cols-[340px_1fr]">
          <aside className="space-y-4">
            <section className="panel p-4">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-700">
                {t.login}
              </h2>
              <form className="space-y-3" onSubmit={onLogin}>
                <label className="block space-y-1">
                  <span className="text-xs font-medium text-slate-600">{t.demoAccount}</span>
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
            </section>

            <section className="panel p-4">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-700">
                {t.overreachDemoQuestions}
              </h2>
              <div className="space-y-2">
                {OVERREACH_SCENARIOS.map((scenario) => (
                  <button
                    key={scenario.id}
                    className="btn-secondary w-full justify-start text-left"
                    type="button"
                    disabled={pending}
                    onClick={() => runOverreachScenario(scenario)}
                  >
                    {overreachLabels[scenario.id] ?? scenario.id}
                  </button>
                ))}
              </div>
            </section>
          </aside>

          <main className="space-y-4">
            <section className="panel p-4">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-700">
                {t.currentSession}
              </h2>
              <div className="grid gap-2 text-xs text-slate-700 sm:grid-cols-2 xl:grid-cols-4">
                <div>
                  {t.currentUser}: <span className="font-mono">{user?.email ?? "-"}</span>
                </div>
                <div>
                  {t.currentRole}: <span className="font-mono">{user?.role ?? "-"}</span>
                </div>
                <div>
                  {t.deniedCurrentRequest}:{" "}
                  <span className="font-mono">{answer ? String(answer.denied) : "-"}</span>
                </div>
                <div>
                  {t.requestId}: <span className="font-mono">{answer?.request_id ?? "-"}</span>
                </div>
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-600">
                    {t.accessibleKnowledgeBases}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {knowledgeBases.length === 0 ? (
                      <span className="text-xs text-slate-500">-</span>
                    ) : (
                      knowledgeBases.map((kb) => (
                        <span
                          key={kb.id}
                          className="rounded border border-slate-300 bg-white px-2 py-1 font-mono text-xs"
                        >
                          {kb.code}
                        </span>
                      ))
                    )}
                  </div>
                </div>
                <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-600">
                    {t.hitKnowledgeBases}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {latestHitKbCodes.length === 0 ? (
                      <span className="text-xs text-slate-500">-</span>
                    ) : (
                      latestHitKbCodes.map((code) => (
                        <span
                          key={code}
                          className="rounded border border-slate-300 bg-white px-2 py-1 font-mono text-xs"
                        >
                          {code}
                        </span>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </section>

            <section className="panel p-4">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-700">
                {t.askQuestionSection}
              </h2>
              <form className="space-y-3" onSubmit={onAsk}>
                <div className="grid gap-3 md:grid-cols-[1fr_140px]">
                  <textarea
                    className="min-h-24 w-full rounded-md border border-slate-300 bg-white p-3 text-sm text-slate-900 outline-none transition focus:border-accent-500 focus:ring-2 focus:ring-accent-200"
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

                <div>
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-600">
                    {t.kbScopeOptional}
                  </p>
                  <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                    {knowledgeBases.map((kb) => (
                      <label
                        key={kb.id}
                        className="flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-2 py-2 text-xs"
                      >
                        <input
                          type="checkbox"
                          checked={selectedKbCodes.includes(kb.code)}
                          onChange={() => toggleKb(kb.code)}
                        />
                        <span className="font-mono">{kb.code}</span>
                      </label>
                    ))}
                  </div>
                </div>
              </form>

              {message ? (
                <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                  {message}
                </div>
              ) : null}
            </section>

            <section className="panel p-4">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-700">
                {t.latestResponse}
              </h2>
              {!answer ? (
                <p className="text-sm text-slate-500">{t.noResponseYet}</p>
              ) : (
                <div className="space-y-3">
                  <div className="grid gap-2 text-xs text-slate-600 md:grid-cols-4">
                    <div>
                      {t.requestId}: <span className="font-mono">{answer.request_id}</span>
                    </div>
                    <div>
                      {t.mode.toLowerCase()}: <span className="font-mono">{answer.mode}</span>
                    </div>
                    <div>
                      cache_hit: <span className="font-mono">{String(answer.cache_hit)}</span>
                    </div>
                    <div>
                      denied: <span className="font-mono">{String(answer.denied)}</span>
                    </div>
                  </div>
                  <pre className="overflow-x-auto rounded-md border border-slate-200 bg-slate-50 p-3 font-mono text-xs whitespace-pre-wrap">
                    {answer.answer}
                  </pre>
                  {answer.citations.length > 0 ? (
                    <div>
                      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-600">
                        {t.citations}
                      </p>
                      <div className="space-y-2">
                        {answer.citations.map((item) => (
                          <div
                            key={item.chunk_id}
                            className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs"
                          >
                            <div className="font-mono text-slate-700">
                              {item.kb_code} / {item.document_title} / score={item.score}
                            </div>
                            <p className="mt-1 text-slate-600">{item.excerpt}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {answer.graph_paths.length > 0 ? (
                    <div>
                      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-600">
                        {t.graphPaths}
                      </p>
                      <div className="space-y-2">
                        {answer.graph_paths.map((item) => (
                          <div
                            key={item.chunk_id}
                            className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs"
                          >
                            <div className="font-mono text-slate-700">{item.path.join(" -> ")}</div>
                            <p className="mt-1 text-slate-600">{item.explanation}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              )}
            </section>

            <section className="panel p-4">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-700">
                  {t.requestDetailAndAdminAudit}
                </h2>
                {user?.role === "admin" ? (
                  <button className="btn-secondary" onClick={onLoadAdminAudit} disabled={pending}>
                    {t.loadAuditLogs}
                  </button>
                ) : null}
              </div>
              {requestDetail ? (
                <pre className="overflow-x-auto rounded-md border border-slate-200 bg-slate-50 p-3 font-mono text-xs whitespace-pre-wrap">
                  {JSON.stringify(requestDetail, null, 2)}
                </pre>
              ) : (
                <p className="text-sm text-slate-500">{t.noRequestDetailLoaded}</p>
              )}
              {user?.role === "admin" && auditLogs.length > 0 ? (
                <div className="mt-3 overflow-x-auto">
                  <table className="w-full border-collapse text-left text-xs">
                    <thead>
                      <tr className="border-b border-slate-200 text-slate-600">
                        <th className="px-2 py-2">{t.requestId}</th>
                        <th className="px-2 py-2">{t.mode.toLowerCase()}</th>
                        <th className="px-2 py-2">denied</th>
                        <th className="px-2 py-2">cache_hit</th>
                        <th className="px-2 py-2">question</th>
                      </tr>
                    </thead>
                    <tbody>
                      {auditLogs.map((row) => (
                        <tr key={row.request_id} className="border-b border-slate-100">
                          <td className="px-2 py-2 font-mono">{row.request_id}</td>
                          <td className="px-2 py-2 font-mono">{row.mode}</td>
                          <td className="px-2 py-2">{String(row.denied)}</td>
                          <td className="px-2 py-2">{String(row.cache_hit)}</td>
                          <td className="px-2 py-2">{row.question}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </section>
          </main>
        </div>
      </div>
    </div>
  );
}
