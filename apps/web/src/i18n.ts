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
    consoleLabel: string;
    language: string;
    chinese: string;
    english: string;
    login: string;
    demoAccount: string;
    email: string;
    password: string;
    signIn: string;
    working: string;
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
    riskAlert: string;
    normalState: string;
    accountState: string;
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
    logout: string;
    loginPageTagline: string;
    capabilityTitle: string;
    capabilityA: string;
    capabilityB: string;
    capabilityC: string;
    securityTestScenarios: string;
    expandScenarios: string;
    collapseScenarios: string;
    routerStatus: string;
    generatorStatus: string;
    restoringSession: string;
    sessionRestoreFailed: string;
    modelStatus: string;
    auditDetail: string;
    demoAccountHint: string;
  }
> = {
  zh: {
    subtitle: "企业级权限感知 GraphRAG 知识助手",
    consoleLabel: "Enterprise Access Console",
    language: "语言",
    chinese: "中文",
    english: "English",
    login: "登录",
    demoAccount: "Demo Account",
    email: "邮箱",
    password: "密码",
    signIn: "登录",
    working: "处理中...",
    currentSession: "当前会话",
    currentUser: "当前用户",
    currentRole: "当前角色",
    deniedCurrentRequest: "本次是否拒绝",
    requestId: "request_id",
    accessibleKnowledgeBases: "可访问知识库",
    hitKnowledgeBases: "命中知识库",
    askQuestionSection: "提问区",
    askQuestionPlaceholder: "请输入问题...",
    ask: "提问",
    mode: "模式",
    kbScopeOptional: "知识库范围（可选）",
    latestResponse: "最新响应",
    noResponseYet: "暂无响应。",
    requestDetailAndAdminAudit: "请求详情与管理员审计",
    noRequestDetailLoaded: "暂无请求详情。",
    loadAuditLogs: "加载审计日志",
    riskAlert: "风险提示",
    normalState: "正常",
    accountState: "账号状态",
    citations: "引用片段",
    graphPaths: "图谱路径",
    loginSuccess: "登录成功。",
    loginFailed: "登录失败。",
    requestDeniedPrefix: "请求被拒绝",
    answerServedFromCache: "命中缓存返回答案。",
    answerGenerated: "答案已生成。",
    askFailed: "提问失败。",
    scenarioExecutedPrefix: "安全测试场景已执行",
    scenarioExecutionFailed: "场景执行失败。",
    loadAuditLogsFailed: "加载审计日志失败。",
    loadedAuditLogsPrefix: "已加载审计日志数量",
    logout: "退出登录",
    loginPageTagline: "企业级权限感知知识问答系统",
    capabilityTitle: "核心能力",
    capabilityA: "后端确定性权限判断与越权拦截",
    capabilityB: "权限范围内 RAG / GraphRAG 检索链路",
    capabilityC: "审计日志与缓存隔离（防缓存越权）",
    securityTestScenarios: "安全测试场景",
    expandScenarios: "展开场景",
    collapseScenarios: "收起场景",
    routerStatus: "Router: rules",
    generatorStatus: "Generator: mock",
    restoringSession: "正在恢复登录状态...",
    sessionRestoreFailed: "登录状态恢复失败，请重新登录。",
    modelStatus: "模型/路由状态",
    auditDetail: "审计详情",
    demoAccountHint: "仅用于演示账号切换"
  },
  en: {
    subtitle: "Permission-Aware Enterprise GraphRAG Knowledge Assistant",
    consoleLabel: "Enterprise Access Console",
    language: "Language",
    chinese: "中文",
    english: "English",
    login: "Login",
    demoAccount: "Demo Account",
    email: "Email",
    password: "Password",
    signIn: "Sign In",
    working: "Working...",
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
    riskAlert: "Risk Alert",
    normalState: "Normal",
    accountState: "Account Status",
    citations: "Citations",
    graphPaths: "Graph Paths",
    loginSuccess: "Login success.",
    loginFailed: "Login failed.",
    requestDeniedPrefix: "Request denied",
    answerServedFromCache: "Answer served from cache.",
    answerGenerated: "Answer generated.",
    askFailed: "Ask failed.",
    scenarioExecutedPrefix: "Security scenario executed",
    scenarioExecutionFailed: "Scenario execution failed.",
    loadAuditLogsFailed: "Load audit logs failed.",
    loadedAuditLogsPrefix: "Loaded audit logs",
    logout: "Logout",
    loginPageTagline: "Enterprise permission-aware knowledge assistant",
    capabilityTitle: "Core Capabilities",
    capabilityA: "Deterministic backend authorization and overreach interception",
    capabilityB: "Permission-scoped RAG / GraphRAG retrieval pipeline",
    capabilityC: "Audit logs and cache isolation to prevent cache overreach",
    securityTestScenarios: "Security Test Scenarios",
    expandScenarios: "Expand",
    collapseScenarios: "Collapse",
    routerStatus: "Router: rules",
    generatorStatus: "Generator: mock",
    restoringSession: "Restoring session...",
    sessionRestoreFailed: "Session restore failed, please sign in again.",
    modelStatus: "Model / Router Status",
    auditDetail: "Audit Detail",
    demoAccountHint: "For demo account switching only"
  }
};
