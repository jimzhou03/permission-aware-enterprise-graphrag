export type Language = "zh" | "en";

export const LANGUAGE_STORAGE_KEY = "paegr.ui.language";

export const OVERREACH_LABELS: Record<
  Language,
  Record<string, string>
> = {
  zh: {
    visitor_finance_salary: "visitor问finance薪酬制度",
    hr_finance_budget: "hr问finance预算审批",
    finance_tech_secret: "finance问tech发布密钥",
    tech_hr_profile: "tech问HR员工档案"
  },
  en: {
    visitor_finance_salary: "visitor asks finance salary policy",
    hr_finance_budget: "hr asks finance budget approval",
    finance_tech_secret: "finance asks tech release secret",
    tech_hr_profile: "tech asks HR employee file"
  }
};

export const UI_TEXT: Record<
  Language,
  {
    subtitle: string;
    language: string;
    chinese: string;
    english: string;
    login: string;
    demoAccount: string;
    email: string;
    password: string;
    signIn: string;
    working: string;
    overreachDemoQuestions: string;
    currentSession: string;
    currentUser: string;
    currentRole: string;
    deniedCurrentRequest: string;
    requestId: string;
    accessibleKnowledgeBases: string;
    hitKnowledgeBases: string;
    askQuestionSection: string;
    askQuestionPlaceholder: string;
    ask: string;
    mode: string;
    kbScopeOptional: string;
    latestResponse: string;
    noResponseYet: string;
    requestDetailAndAdminAudit: string;
    noRequestDetailLoaded: string;
    loadAuditLogs: string;
    citations: string;
    graphPaths: string;
    loginSuccess: string;
    loginFailed: string;
    requestDeniedPrefix: string;
    answerServedFromCache: string;
    answerGenerated: string;
    askFailed: string;
    scenarioExecutedPrefix: string;
    scenarioExecutionFailed: string;
    loadAuditLogsFailed: string;
    loadedAuditLogsPrefix: string;
  }
> = {
  zh: {
    subtitle: "权限矩阵演示控制台",
    language: "语言",
    chinese: "中文",
    english: "English",
    login: "登录",
    demoAccount: "演示账号",
    email: "Email",
    password: "Password",
    signIn: "Sign In",
    working: "处理中...",
    overreachDemoQuestions: "越权演示问题",
    currentSession: "当前会话",
    currentUser: "当前用户",
    currentRole: "当前角色",
    deniedCurrentRequest: "本次拒绝",
    requestId: "request_id",
    accessibleKnowledgeBases: "可访问知识库",
    hitKnowledgeBases: "本次命中知识库",
    askQuestionSection: "提问",
    askQuestionPlaceholder: "Ask a question...",
    ask: "Ask",
    mode: "Mode",
    kbScopeOptional: "Knowledge Base Scope (optional)",
    latestResponse: "最新响应",
    noResponseYet: "暂无响应。",
    requestDetailAndAdminAudit: "Request Detail & Admin Audit",
    noRequestDetailLoaded: "暂无请求详情。",
    loadAuditLogs: "Load Audit Logs",
    citations: "Citations",
    graphPaths: "Graph Paths",
    loginSuccess: "登录成功。",
    loginFailed: "登录失败。",
    requestDeniedPrefix: "请求被拒绝",
    answerServedFromCache: "命中缓存返回答案。",
    answerGenerated: "答案已生成。",
    askFailed: "提问失败。",
    scenarioExecutedPrefix: "演示场景已执行",
    scenarioExecutionFailed: "场景执行失败。",
    loadAuditLogsFailed: "加载审计日志失败。",
    loadedAuditLogsPrefix: "已加载审计日志数量"
  },
  en: {
    subtitle: "Permission Matrix Demo Console",
    language: "Language",
    chinese: "中文",
    english: "English",
    login: "Login",
    demoAccount: "Demo Account",
    email: "Email",
    password: "Password",
    signIn: "Sign In",
    working: "Working...",
    overreachDemoQuestions: "Overreach Demo Questions",
    currentSession: "Current Session",
    currentUser: "Current User",
    currentRole: "Current Role",
    deniedCurrentRequest: "Denied This Request",
    requestId: "request_id",
    accessibleKnowledgeBases: "Accessible Knowledge Bases",
    hitKnowledgeBases: "Hit Knowledge Bases",
    askQuestionSection: "Ask",
    askQuestionPlaceholder: "Ask a question...",
    ask: "Ask",
    mode: "Mode",
    kbScopeOptional: "Knowledge Base Scope (optional)",
    latestResponse: "Latest Response",
    noResponseYet: "No response yet.",
    requestDetailAndAdminAudit: "Request Detail & Admin Audit",
    noRequestDetailLoaded: "No request detail loaded.",
    loadAuditLogs: "Load Audit Logs",
    citations: "Citations",
    graphPaths: "Graph Paths",
    loginSuccess: "Login success.",
    loginFailed: "Login failed.",
    requestDeniedPrefix: "Request denied",
    answerServedFromCache: "Answer served from cache.",
    answerGenerated: "Answer generated.",
    askFailed: "Ask failed.",
    scenarioExecutedPrefix: "Scenario executed",
    scenarioExecutionFailed: "Scenario execution failed.",
    loadAuditLogsFailed: "Load audit logs failed.",
    loadedAuditLogsPrefix: "Loaded audit logs"
  }
};
