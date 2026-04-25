"use client";

import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Clock3,
  Code2,
  Database,
  FileText,
  GraduationCap,
  HelpCircle,
  History,
  KeyRound,
  Loader2,
  LogOut,
  MessageSquare,
  PieChart,
  Play,
  RefreshCw,
  School,
  Send,
  Settings,
  ShieldCheck,
  Trash2,
  UserRound
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  deleteRun,
  fetchCatalog,
  fetchDemoProfile,
  fetchRunDetail,
  fetchRunHistory,
  login,
  logout,
  runOrchestrationSocket
} from "@/lib/api";
import {
  createEmptyRequest,
  experienceText,
  normalizeRequest,
  splitExperienceText,
  validateProfile
} from "@/lib/profile";
import type {
  AdmitPilotRequest,
  AgentCode,
  AgentResult,
  AuthUser,
  CatalogResponse,
  MissingProfileField,
  OrchestrationResponse,
  RunHistoryEntry,
  SchoolOption
} from "@/lib/types";

const STAGES: Array<{ agent: AgentCode; title: string; label: string }> = [
  { agent: "aie", title: "Official intelligence", label: "AIE" },
  { agent: "sae", title: "Strategy evaluation", label: "SAE" },
  { agent: "dta", title: "Timeline architecture", label: "DTA" },
  { agent: "cds", title: "Document support", label: "CDS" }
];

const TAB_LABELS: Record<AgentCode, string> = {
  aie: "AIE",
  sae: "SAE",
  dta: "DTA",
  cds: "CDS"
};

export default function WorkbenchPage() {
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null);
  const [request, setRequest] = useState<AdmitPilotRequest>(() => createEmptyRequest());
  const [response, setResponse] = useState<OrchestrationResponse | null>(null);
  const [missingFields, setMissingFields] = useState<MissingProfileField[]>([]);
  const [activeTab, setActiveTab] = useState<AgentCode>("aie");
  const [isCatalogLoading, setIsCatalogLoading] = useState(true);
  const [isDemoLoading, setIsDemoLoading] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [isAuthChecking, setIsAuthChecking] = useState(false);
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [authToken, setAuthToken] = useState("");
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [loginEmail, setLoginEmail] = useState("demo@admitpilot.local");
  const [loginPassword, setLoginPassword] = useState("admitpilot-demo");
  const [runHistory, setRunHistory] = useState<RunHistoryEntry[]>([]);
  const [runningStage, setRunningStage] = useState<AgentCode | null>(null);
  const [completedStages, setCompletedStages] = useState<AgentCode[]>([]);
  const [isAccountMenuOpen, setIsAccountMenuOpen] = useState(false);
  const [apiError, setApiError] = useState("");

  useEffect(() => {
    let active = true;
    fetchCatalog()
      .then((payload) => {
        if (active) {
          setCatalog(payload);
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setApiError(error instanceof Error ? error.message : "Catalog request failed");
        }
      })
      .finally(() => {
        if (active) {
          setIsCatalogLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const refreshHistory = useCallback(async (token: string) => {
    setIsHistoryLoading(true);
    try {
      const payload = await fetchRunHistory(token);
      setRunHistory(payload.runs);
    } finally {
      setIsHistoryLoading(false);
    }
  }, []);

  const localMissingFields = useMemo(
    () => validateProfile(request.profile),
    [request.profile]
  );
  const visibleMissingFields = missingFields.length ? missingFields : localMissingFields;
  const missingByKey = useMemo(
    () => new Map(visibleMissingFields.map((item) => [item.key, item])),
    [visibleMissingFields]
  );

  const updateProfile = useCallback(
    <K extends keyof AdmitPilotRequest["profile"]>(
      key: K,
      value: AdmitPilotRequest["profile"][K]
    ) => {
      setRequest((current) => ({
        ...current,
        profile: {
          ...current.profile,
          [key]: value
        }
      }));
      setMissingFields([]);
    },
    []
  );

  const updateGpa = useCallback((value: string) => {
    setRequest((current) => ({
      ...current,
      profile: {
        ...current.profile,
        academic_metrics: {
          ...current.profile.academic_metrics,
          gpa: value
        }
      }
    }));
    setMissingFields([]);
  }, []);

  const updateIelts = useCallback((value: string) => {
    setRequest((current) => ({
      ...current,
      profile: {
        ...current.profile,
        language_scores: {
          ...current.profile.language_scores,
          ielts: value
        }
      }
    }));
    setMissingFields([]);
  }, []);

  const toggleSchool = useCallback(
    (school: SchoolOption) => {
      setRequest((current) => {
        const selected = current.profile.target_schools.includes(school.code);
        const nextSchools = selected
          ? current.profile.target_schools.filter((item) => item !== school.code)
          : [...current.profile.target_schools, school.code];
        const targetProgramBySchool = {
          ...current.constraints.target_program_by_school
        };
        if (selected) {
          delete targetProgramBySchool[school.code];
        } else {
          targetProgramBySchool[school.code] =
            catalog?.default_portfolio[school.code] ?? school.programs[0]?.code ?? "";
        }
        const nextPrograms = uniqueValues(Object.values(targetProgramBySchool));
        return {
          ...current,
          profile: {
            ...current.profile,
            target_schools: nextSchools,
            target_programs: nextPrograms
          },
          constraints: {
            ...current.constraints,
            target_schools: nextSchools,
            target_program_by_school: targetProgramBySchool
          }
        };
      });
      setMissingFields([]);
    },
    [catalog]
  );

  const changeProgram = useCallback((schoolCode: string, programCode: string) => {
    setRequest((current) => {
      const targetProgramBySchool = {
        ...current.constraints.target_program_by_school,
        [schoolCode]: programCode
      };
      const nextSchools = current.profile.target_schools.includes(schoolCode)
        ? current.profile.target_schools
        : [...current.profile.target_schools, schoolCode];
      const nextPrograms = uniqueValues(Object.values(targetProgramBySchool));
      return {
        ...current,
        profile: {
          ...current.profile,
          target_schools: nextSchools,
          target_programs: nextPrograms
        },
        constraints: {
          ...current.constraints,
          target_schools: nextSchools,
          target_program_by_school: targetProgramBySchool
        }
      };
    });
    setMissingFields([]);
  }, []);

  const clearProfile = useCallback(() => {
    setRequest(createEmptyRequest());
    setResponse(null);
    setMissingFields([]);
    setApiError("");
    setActiveTab("aie");
  }, []);

  const loginDemo = useCallback(async () => {
    setIsLoggingIn(true);
    setApiError("");
    try {
      const payload = await login(loginEmail, loginPassword);
      setAuthToken(payload.token);
      setAuthUser(payload.user);
      setIsAccountMenuOpen(false);
      await refreshHistory(payload.token);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "Login failed");
    } finally {
      setIsLoggingIn(false);
    }
  }, [loginEmail, loginPassword, refreshHistory]);

  const logoutDemo = useCallback(async () => {
    const token = authToken;
    setAuthToken("");
    setAuthUser(null);
    setRunHistory([]);
    setResponse(null);
    setRunningStage(null);
    setCompletedStages([]);
    setIsAccountMenuOpen(false);
    if (token) {
      await logout(token).catch(() => undefined);
    }
  }, [authToken]);

  const loadDemo = useCallback(async () => {
    setIsDemoLoading(true);
    setApiError("");
    try {
      const payload = await fetchDemoProfile();
      setRequest(normalizeRequest(payload));
      setResponse(null);
      setMissingFields([]);
      setActiveTab("aie");
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "Demo profile request failed");
    } finally {
      setIsDemoLoading(false);
    }
  }, []);

  const runDemo = useCallback(async () => {
    if (!authToken) {
      setApiError("Sign in before running AdmitPilot.");
      return;
    }
    const localMissing = validateProfile(request.profile);
    if (localMissing.length) {
      setMissingFields(localMissing);
      setResponse(null);
      setApiError("Complete the missing profile fields before running.");
      return;
    }

    setIsRunning(true);
    setApiError("");
    setResponse(null);
    setMissingFields([]);
    setActiveTab("aie");
    setCompletedStages([]);
    setRunningStage("aie");
    try {
      const payload = await runOrchestrationSocket({
        payload: request,
        token: authToken,
        onEvent: (event) => {
          if (event.event === "workflow_started") {
            const firstStage = event.data.stages[0]?.agent ?? "aie";
            setRunningStage(firstStage);
            setResponse({
              status: "partial_delivered",
              summary: "AdmitPilot is running.",
              missing_profile_fields: [],
              results: [],
              trace_id: event.data.trace_id
            });
          }
          if (event.event === "stage_started") {
            setRunningStage(event.data.agent);
          }
          if (event.event === "stage_completed") {
            setCompletedStages((current) =>
              current.includes(event.data.agent)
                ? current
                : [...current, event.data.agent]
            );
            if (event.data.result) {
              const completedResult = event.data.result;
              setResponse((current) => ({
                status: "partial_delivered",
                summary: "AdmitPilot is running.",
                missing_profile_fields: [],
                results: upsertAgentResult(current?.results ?? [], completedResult),
                trace_id: event.data.trace_id
              }));
            }
          }
        }
      });
      setCompletedStages(payload.results.filter((item) => item.success).map((item) => item.agent));
      setRunningStage(null);
      setResponse(payload);
      setMissingFields(payload.missing_profile_fields);
      if (payload.status === "needs_profile_input") {
        setApiError(payload.summary);
      }
      await refreshHistory(authToken);
    } catch (error) {
      setRunningStage(null);
      setApiError(error instanceof Error ? error.message : "Run request failed");
    } finally {
      setIsRunning(false);
    }
  }, [authToken, refreshHistory, request]);

  const loadHistoryRun = useCallback(
    async (runId: string) => {
      if (!authToken) {
        return;
      }
      setIsHistoryLoading(true);
      setApiError("");
      try {
        const payload = await fetchRunDetail(authToken, runId);
        setRequest(normalizeRequest(payload.run.request));
        setResponse(payload.run.response);
        setMissingFields(payload.run.response.missing_profile_fields);
        setCompletedStages([]);
        setRunningStage(null);
        setActiveTab("aie");
      } catch (error) {
        setApiError(error instanceof Error ? error.message : "Run history request failed");
      } finally {
        setIsHistoryLoading(false);
      }
    },
    [authToken]
  );

  const deleteHistoryRun = useCallback(
    async (runId: string) => {
      if (!authToken) {
        return;
      }
      setIsHistoryLoading(true);
      setApiError("");
      try {
        await deleteRun(authToken, runId);
        setRunHistory((current) => current.filter((item) => item.run_id !== runId));
        if (response?.run_id === runId) {
          setResponse(null);
          setMissingFields([]);
          setActiveTab("aie");
        }
      } catch (error) {
        setApiError(error instanceof Error ? error.message : "Delete run request failed");
      } finally {
        setIsHistoryLoading(false);
      }
    },
    [authToken, response]
  );

  if (isAuthChecking) {
    return <LoadingShell />;
  }

  return (
    <main className="min-h-screen overflow-x-hidden bg-paper text-ink">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1920px] flex-col gap-3 px-4 py-3 lg:flex-row lg:items-center lg:justify-between lg:px-6">
          <div className="flex min-w-0 flex-wrap items-center gap-4">
            <div className="flex items-center gap-3">
              <Send className="h-7 w-7 text-pine" aria-hidden="true" />
              <span className="text-xl font-semibold">AdmitPilot</span>
            </div>
            <div className="hidden h-8 w-px bg-slate-200 sm:block" />
            <h1 className="min-w-0 text-base font-semibold sm:text-lg">
              Admissions Planning Workspace
            </h1>
          </div>
          <div className="flex min-w-0 flex-wrap items-center gap-3">
            <span className="inline-flex min-h-9 max-w-full items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700">
              <Code2 className="h-4 w-4" aria-hidden="true" />
              <span className="truncate">API: http://localhost:8000</span>
            </span>
            <StatusBadge response={response} isRunning={isRunning} />
            <HelpCircle className="h-5 w-5 text-slate-600" aria-hidden="true" />
            <div className="relative">
              <button
                type="button"
                onClick={() => setIsAccountMenuOpen((current) => !current)}
                className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-300 bg-white text-slate-600 hover:bg-slate-50"
                aria-label="Open settings"
              >
                <Settings className="h-5 w-5" aria-hidden="true" />
              </button>
              {authUser && isAccountMenuOpen ? (
                <div className="absolute right-0 top-11 z-20 w-72 rounded-lg border border-slate-300 bg-white p-3 text-sm shadow-panel">
                  <p className="font-semibold text-ink">{authUser.display_name}</p>
                  <p className="mt-1 truncate text-xs text-slate-500">{authUser.email}</p>
                  <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                    Local SQLite run history is enabled for this account.
                  </div>
                  <button
                    type="button"
                    onClick={logoutDemo}
                    className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-md bg-pine px-3 py-2 text-sm font-semibold text-white"
                  >
                    <LogOut className="h-4 w-4" aria-hidden="true" />
                    Sign out
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </header>

      {!authUser ? (
        <LoginScreen
          apiError={apiError}
          isLoggingIn={isLoggingIn}
          loginDemo={loginDemo}
          loginEmail={loginEmail}
          loginPassword={loginPassword}
          setLoginEmail={setLoginEmail}
          setLoginPassword={setLoginPassword}
        />
      ) : (

      <div className="mx-auto grid min-h-[calc(100vh-65px)] max-w-[1920px] gap-2 p-2 lg:h-[calc(100vh-65px)] lg:grid-cols-[minmax(360px,460px)_minmax(0,1fr)] lg:overflow-hidden">
          <aside className="min-w-0 overflow-hidden rounded-lg border border-slate-300 bg-white p-4 shadow-panel lg:h-full lg:overflow-y-auto">
            <ProfileForm
              catalog={catalog}
              clearProfile={clearProfile}
              isCatalogLoading={isCatalogLoading}
              missingByKey={missingByKey}
              request={request}
              updateGpa={updateGpa}
              updateIelts={updateIelts}
              updateProfile={updateProfile}
              toggleSchool={toggleSchool}
              changeProgram={changeProgram}
            />
            <SidebarActions
              apiError={apiError}
              isDemoLoading={isDemoLoading}
              isRunning={isRunning}
              loadDemo={loadDemo}
              missingFields={visibleMissingFields}
              response={response}
              runDemo={runDemo}
            />
            <RunHistoryPanel
              activeRunId={response?.run_id ?? ""}
              isHistoryLoading={isHistoryLoading}
              deleteHistoryRun={deleteHistoryRun}
              loadHistoryRun={loadHistoryRun}
              runHistory={runHistory}
            />
          </aside>

          <section className="grid min-w-0 content-start gap-2 lg:h-full lg:overflow-y-auto">
            <StagePipeline
              completedStages={completedStages}
              response={response}
              isRunning={isRunning}
              runningStage={runningStage}
            />
            <ResultsPanel
              activeTab={activeTab}
              response={response}
              setActiveTab={setActiveTab}
            />
          </section>
      </div>
      )}
    </main>
  );
}

function LoadingShell() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-paper text-ink">
      <div className="inline-flex items-center gap-3 rounded-lg border border-slate-300 bg-white px-5 py-4 text-sm font-semibold shadow-panel">
        <Loader2 className="h-5 w-5 animate-spin text-pine" aria-hidden="true" />
        Restoring session
      </div>
    </main>
  );
}

function LoginScreen({
  apiError,
  isLoggingIn,
  loginDemo,
  loginEmail,
  loginPassword,
  setLoginEmail,
  setLoginPassword
}: {
  apiError: string;
  isLoggingIn: boolean;
  loginDemo: () => void;
  loginEmail: string;
  loginPassword: string;
  setLoginEmail: (value: string) => void;
  setLoginPassword: (value: string) => void;
}) {
  return (
    <section className="mx-auto grid min-h-[calc(100vh-65px)] max-w-[1120px] content-center gap-6 px-4 py-8 lg:grid-cols-[minmax(0,1fr)_420px] lg:px-6">
      <div className="min-w-0">
        <p className="text-xs font-bold uppercase tracking-wide text-pine">
          Secure demo workspace
        </p>
        <h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-tight sm:text-4xl">
          Sign in to persist AdmitPilot runs and review the full execution history.
        </h2>
        <div className="mt-6 grid gap-3 sm:grid-cols-3">
          <LoginFeature
            icon={KeyRound}
            title="Session token"
            body="Bearer auth protects orchestration and history endpoints."
          />
          <LoginFeature
            icon={Database}
            title="SQLite storage"
            body="Runs are saved locally with request, response, status, and trace ID."
          />
          <LoginFeature
            icon={History}
            title="Replay history"
            body="Open an earlier run and restore its request and results."
          />
        </div>
      </div>

      <div className="rounded-lg border border-slate-300 bg-white p-5 shadow-panel">
        <div className="flex items-center gap-3">
          <ShieldCheck className="h-6 w-6 text-pine" aria-hidden="true" />
          <div>
            <h2 className="text-xl font-semibold">Demo Login</h2>
            <p className="mt-1 text-sm text-slate-600">
              Use the seeded account for this MVP.
            </p>
          </div>
        </div>
        {apiError ? (
          <div className="mt-4 rounded-md border border-amber-300 bg-amber-50 px-3 py-3 text-sm text-amber-950">
            {apiError}
          </div>
        ) : null}
        <div className="mt-5 grid gap-4">
          <FieldGroup label="Email" htmlFor="login_email">
            <input
              id="login_email"
              className={inputClass(false)}
              value={loginEmail}
              onChange={(event) => setLoginEmail(event.target.value)}
              autoComplete="username"
            />
          </FieldGroup>
          <FieldGroup label="Password" htmlFor="login_password">
            <input
              id="login_password"
              className={inputClass(false)}
              value={loginPassword}
              onChange={(event) => setLoginPassword(event.target.value)}
              type="password"
              autoComplete="current-password"
            />
          </FieldGroup>
          <button
            type="button"
            onClick={loginDemo}
            disabled={isLoggingIn}
            className="inline-flex min-h-12 items-center justify-center gap-2 rounded-md bg-pine px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isLoggingIn ? (
              <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
            ) : (
              <KeyRound className="h-5 w-5" aria-hidden="true" />
            )}
            Sign in
          </button>
        </div>
      </div>
    </section>
  );
}

function LoginFeature({
  body,
  icon: Icon,
  title
}: {
  body: string;
  icon: typeof KeyRound;
  title: string;
}) {
  return (
    <div className="rounded-md border border-slate-300 bg-white p-4 shadow-panel">
      <Icon className="h-5 w-5 text-pine" aria-hidden="true" />
      <p className="mt-3 font-semibold">{title}</p>
      <p className="mt-2 text-sm leading-6 text-slate-600">{body}</p>
    </div>
  );
}

function RunHistoryPanel({
  activeRunId,
  deleteHistoryRun,
  isHistoryLoading,
  loadHistoryRun,
  runHistory
}: {
  activeRunId: string;
  deleteHistoryRun: (runId: string) => void;
  isHistoryLoading: boolean;
  loadHistoryRun: (runId: string) => void;
  runHistory: RunHistoryEntry[];
}) {
  return (
    <section className="mt-6 grid min-w-0 gap-3 border-t border-slate-200 pt-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <History className="h-5 w-5 text-pine" aria-hidden="true" />
          <h2 className="text-lg font-semibold">Run History</h2>
        </div>
        {isHistoryLoading ? (
          <Loader2 className="h-4 w-4 animate-spin text-pine" aria-hidden="true" />
        ) : null}
      </div>
      {runHistory.length ? (
        <div className="grid max-h-[360px] gap-2 overflow-y-auto pr-1">
          {runHistory.map((run) => (
            <div
              key={run.run_id}
              className={`min-w-0 rounded-md border px-3 py-3 text-left text-sm transition hover:border-pine ${
                activeRunId === run.run_id
                  ? "border-pine bg-emerald-50"
                  : "border-slate-200 bg-slate-50"
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={() => loadHistoryRun(run.run_id)}
                  className="min-w-0 flex-1 truncate text-left font-semibold hover:text-pine"
                >
                  {run.run_id}
                </button>
                <span className="flex shrink-0 items-center gap-2">
                  <span className="rounded-full bg-white px-2 py-1 text-xs font-semibold text-slate-700">
                    {run.status}
                  </span>
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      deleteHistoryRun(run.run_id);
                    }}
                    className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-500 hover:border-red-300 hover:text-red-700"
                    aria-label={`Delete ${run.run_id}`}
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  </button>
                </span>
              </div>
              <button
                type="button"
                onClick={() => loadHistoryRun(run.run_id)}
                className="mt-2 block w-full text-left"
              >
                <span className="line-clamp-2 text-xs leading-5 text-slate-600">
                {englishText(run.summary, "Saved AdmitPilot run")}
                </span>
              </button>
              <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
                <span>{formatRunDate(run.created_at)}</span>
                <span>{run.result_count} results</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-md border border-dashed border-slate-300 bg-slate-50 px-3 py-6 text-center text-sm text-slate-500">
          No persisted runs yet
        </div>
      )}
    </section>
  );
}

function ProfileForm({
  catalog,
  clearProfile,
  isCatalogLoading,
  missingByKey,
  request,
  updateGpa,
  updateIelts,
  updateProfile,
  toggleSchool,
  changeProgram
}: {
  catalog: CatalogResponse | null;
  clearProfile: () => void;
  isCatalogLoading: boolean;
  missingByKey: Map<string, MissingProfileField>;
  request: AdmitPilotRequest;
  updateGpa: (value: string) => void;
  updateIelts: (value: string) => void;
  updateProfile: <K extends keyof AdmitPilotRequest["profile"]>(
    key: K,
    value: AdmitPilotRequest["profile"][K]
  ) => void;
  toggleSchool: (school: SchoolOption) => void;
  changeProgram: (schoolCode: string, programCode: string) => void;
}) {
  return (
    <form className="grid min-w-0 gap-4 overflow-hidden">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <GraduationCap className="h-5 w-5 text-pine" aria-hidden="true" />
          <h2 className="text-sm font-bold uppercase tracking-wide text-pine">
            Applicant Profile
          </h2>
        </div>
        <button
          type="button"
          onClick={clearProfile}
          className="inline-flex items-center gap-2 rounded-md px-2 py-1 text-sm font-semibold text-slate-600 hover:bg-slate-100"
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Clear
        </button>
      </div>

      <FieldGroup label="Name" htmlFor="name">
        <input
          id="name"
          className={inputClass(false)}
          value={request.profile.name}
          onChange={(event) => updateProfile("name", event.target.value)}
          placeholder="Demo Applicant"
        />
      </FieldGroup>

      <FieldGroup
        label="Degree level"
        htmlFor="degree_level"
        error={missingByKey.get("degree_level")}
      >
        <select
          id="degree_level"
          className={inputClass(missingByKey.has("degree_level"))}
          value={request.profile.degree_level}
          onChange={(event) => updateProfile("degree_level", event.target.value)}
        >
          <option value="">Select</option>
          <option value="bachelor">Bachelor&apos;s degree</option>
          <option value="master">Master&apos;s degree</option>
          <option value="undergraduate">Undergraduate student</option>
        </select>
      </FieldGroup>

      <FieldGroup
        label="Major interest"
        htmlFor="major_interest"
        error={missingByKey.get("major_interest")}
      >
        <input
          id="major_interest"
          className={inputClass(missingByKey.has("major_interest"))}
          value={request.profile.major_interest}
          onChange={(event) => updateProfile("major_interest", event.target.value)}
          placeholder="Computer Science"
        />
      </FieldGroup>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <FieldGroup
          label="GPA"
          htmlFor="gpa"
          error={missingByKey.get("academic_metrics.gpa")}
        >
          <input
            id="gpa"
            className={inputClass(missingByKey.has("academic_metrics.gpa"))}
            min="0"
            step="0.01"
            type="number"
            value={String(request.profile.academic_metrics.gpa ?? "")}
            onChange={(event) => updateGpa(event.target.value)}
            placeholder="3.72"
          />
        </FieldGroup>
        <FieldGroup
          label="IELTS"
          htmlFor="ielts"
          error={missingByKey.get("language_scores")}
        >
          <input
            id="ielts"
            className={inputClass(missingByKey.has("language_scores"))}
            min="0"
            step="0.5"
            type="number"
            value={String(request.profile.language_scores.ielts ?? "")}
            onChange={(event) => updateIelts(event.target.value)}
            placeholder="7.5"
          />
        </FieldGroup>
      </div>

      <FieldGroup
        label="Experience materials"
        htmlFor="experiences"
        error={missingByKey.get("experiences")}
      >
        <textarea
          id="experiences"
          className={`${inputClass(missingByKey.has("experiences"))} min-h-[132px] resize-y`}
          value={experienceText(request.profile)}
          onChange={(event) =>
            updateProfile("experiences", splitExperienceText(event.target.value))
          }
          placeholder="One research, internship, course project, or competition experience per line"
        />
      </FieldGroup>

      <div className="border-t border-slate-200 pt-4">
        <div className="mb-3 flex items-center gap-2">
          <School className="h-5 w-5 text-pine" aria-hidden="true" />
          <h2 className="text-lg font-semibold">Target portfolio</h2>
        </div>
        {missingByKey.has("target_schools") || missingByKey.has("target_programs") ? (
          <p className="mb-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            {missingByKey.get("target_schools")?.help_text ??
              missingByKey.get("target_programs")?.help_text}
          </p>
        ) : null}
        {isCatalogLoading ? (
          <div className="flex items-center gap-2 text-sm text-slate-600">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            Loading catalog
          </div>
        ) : (
          <div className="grid gap-3">
            {catalog?.schools.map((school) => {
              const selected = request.profile.target_schools.includes(school.code);
              const programValue =
                request.constraints.target_program_by_school[school.code] ??
                catalog.default_portfolio[school.code] ??
                school.programs[0]?.code ??
                "";
              return (
                <div
                  key={school.code}
                  className="min-w-0 overflow-hidden rounded-md border border-slate-200 bg-slate-50 px-3 py-3"
                >
                  <label className="flex items-center justify-between gap-3">
                    <span className="flex min-w-0 flex-1 items-center gap-2">
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => toggleSchool(school)}
                        className="h-4 w-4 rounded border-slate-300 text-pine"
                      />
                      <span className="min-w-0">
                        <span className="block text-sm font-semibold">{school.code}</span>
                        <span className="block truncate text-xs text-slate-500">
                          {school.display_name}
                        </span>
                      </span>
                    </span>
                    <span className="max-w-[96px] shrink-0 truncate rounded-full bg-mist px-2 py-1 text-xs text-slate-700">
                      {school.region}
                    </span>
                  </label>
                  {selected ? (
                    <select
                      className="mt-3 block w-full min-w-0 max-w-full truncate rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
                      value={programValue}
                      onChange={(event) => changeProgram(school.code, event.target.value)}
                    >
                      {school.programs.map((program) => (
                        <option key={program.code} value={program.code}>
                          {program.code} - {program.display_name}
                        </option>
                      ))}
                    </select>
                  ) : null}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </form>
  );
}

function SidebarActions({
  apiError,
  isDemoLoading,
  isRunning,
  loadDemo,
  missingFields,
  response,
  runDemo
}: {
  apiError: string;
  isDemoLoading: boolean;
  isRunning: boolean;
  loadDemo: () => void;
  missingFields: MissingProfileField[];
  response: OrchestrationResponse | null;
  runDemo: () => void;
}) {
  return (
    <div className="mt-6 grid min-w-0 gap-3 border-t border-slate-200 pt-4">
      {apiError ? (
        <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-3 text-sm text-amber-950">
          <div className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{apiError}</span>
          </div>
        </div>
      ) : null}

      {missingFields.length ? (
        <div className="grid gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-amber-950">
            <AlertTriangle className="h-4 w-4" aria-hidden="true" />
            Complete these profile fields
          </div>
          <div className="flex flex-wrap gap-2">
            {missingFields.map((field) => (
              <span
                key={field.key}
                className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-amber-950"
              >
                {field.label}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {response ? (
        <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-700">
          <p className="font-semibold text-slate-800">Latest run</p>
          <p className="mt-1">
            {englishText(
              response.summary,
              "AdmitPilot completed the selected workflow and produced structured agent results."
            )}
          </p>
        </div>
      ) : null}

      <button
        type="button"
        onClick={loadDemo}
        disabled={isDemoLoading || isRunning}
        className="inline-flex min-h-12 items-center justify-center gap-2 rounded-md border border-pine bg-white px-3 py-2 text-sm font-semibold text-pine disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isDemoLoading ? (
          <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
        ) : (
          <UserRound className="h-5 w-5" aria-hidden="true" />
        )}
        Load Demo Profile
      </button>
      <button
        type="button"
        onClick={runDemo}
        disabled={isRunning}
        className="inline-flex min-h-12 items-center justify-center gap-2 rounded-md bg-pine px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isRunning ? (
          <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
        ) : (
          <Play className="h-5 w-5" aria-hidden="true" />
        )}
        Run AdmitPilot
      </button>
    </div>
  );
}

function StagePipeline({
  completedStages,
  response,
  isRunning,
  runningStage
}: {
  completedStages: AgentCode[];
  response: OrchestrationResponse | null;
  isRunning: boolean;
  runningStage: AgentCode | null;
}) {
  const resultByAgent = useMemo(() => {
    return new Map(response?.results.map((item) => [item.agent, item]) ?? []);
  }, [response]);
  const completedCount = response
    ? response.results.filter((item) => item.success).length
    : completedStages.length;

  return (
    <section className="rounded-lg border border-slate-300 bg-white p-5 shadow-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-pine">
            Admissions Pipeline Status
          </p>
          <h2 className="mt-1 text-xl font-semibold">Agent stages</h2>
        </div>
        <div className="flex items-center gap-2 text-sm text-slate-600">
          <Clock3 className="h-5 w-5 text-brass" aria-hidden="true" />
          {isRunning
            ? `${completedCount}/4 stages complete`
            : response
              ? `${completedCount}/4 stages complete`
              : "Ready to run"}
        </div>
      </div>
      <div className="mt-5 grid gap-3 xl:grid-cols-4">
        {STAGES.map((stage) => {
          const result = resultByAgent.get(stage.agent);
          const state = stageState({
            agent: stage.agent,
            completedStages,
            isRunning,
            result,
            runningStage
          });
          const Icon = stageIcon(stage.agent);
          const style = stageStyle(state);
          return (
            <div
              key={stage.agent}
              className={`min-h-[108px] rounded-md border bg-white px-5 py-4 ${style.card}`}
            >
              <div className="flex items-center justify-between gap-4">
                <div className="flex min-w-0 items-center gap-4">
                  <Icon className={`h-8 w-8 shrink-0 ${style.icon}`} aria-hidden="true" />
                  <div className="min-w-0">
                    <p className="text-base font-bold">{stage.label}</p>
                    <p className="mt-1 text-sm text-slate-600">{stage.title}</p>
                  </div>
                </div>
                <StageStateBadge state={state} />
              </div>
              <p className="mt-4 text-xs text-slate-500">
                {result
                  ? `${result.task} - confidence ${percent(result.confidence)}`
                  : state === "running"
                    ? "Executing this agent now"
                    : state === "done"
                      ? "Stage completed in this run"
                      : "Waiting for execution"}
              </p>
            </div>
          );
        })}
      </div>
      <div className="mt-5 flex flex-wrap items-center gap-4 text-sm text-slate-600">
        <span className="inline-flex items-center gap-2">
          <Clock3 className="h-4 w-4" aria-hidden="true" />
          {isRunning
            ? `Running ${runningStage?.toUpperCase() ?? "agent"}`
            : response
              ? "Last run: current session"
              : "Last run: not run yet"}
        </span>
        <span className="hidden h-4 w-px bg-slate-300 sm:block" />
        <span>Run ID: {response?.trace_id ?? "pending"}</span>
        {response?.status === "needs_profile_input" ? (
          <span className="inline-flex items-center gap-2 text-brass">
            <AlertTriangle className="h-4 w-4" aria-hidden="true" />
            Action items require attention
          </span>
        ) : null}
      </div>
    </section>
  );
}

function ResultsPanel({
  activeTab,
  response,
  setActiveTab
}: {
  activeTab: AgentCode;
  response: OrchestrationResponse | null;
  setActiveTab: (tab: AgentCode) => void;
}) {
  const resultByAgent = useMemo(() => {
    return new Map(response?.results.map((item) => [item.agent, item]) ?? []);
  }, [response]);
  const activeResult = resultByAgent.get(activeTab);

  return (
    <section className="rounded-lg border border-slate-300 bg-white p-4 shadow-panel">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-3">
        <div className="flex items-center gap-2">
          <FileText className="h-5 w-5 text-pine" aria-hidden="true" />
          <h2 className="text-xl font-semibold">Results</h2>
        </div>
        <div className="flex rounded-md border border-slate-300 bg-slate-50 p-1">
          {STAGES.map((stage) => (
            <button
              key={stage.agent}
              type="button"
              onClick={() => setActiveTab(stage.agent)}
              className={`min-h-9 rounded px-3 py-1.5 text-sm font-semibold ${
                activeTab === stage.agent
                  ? "bg-pine text-white"
                  : "text-slate-600 hover:bg-white"
              }`}
            >
              {TAB_LABELS[stage.agent]}
            </button>
          ))}
        </div>
      </div>
      <div className="min-h-[420px] pt-4">
        <AgentResultView agent={activeTab} result={activeResult} />
      </div>
    </section>
  );
}

function AgentResultView({
  agent,
  result
}: {
  agent: AgentCode;
  result?: AgentResult;
}) {
  if (!result) {
    return (
      <div className="flex min-h-[360px] items-center justify-center rounded-md border border-dashed border-slate-300 bg-slate-50 text-sm text-slate-500">
        Waiting for results
      </div>
    );
  }
  if (!result.success) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 px-3 py-3 text-sm text-red-950">
        {result.blocked_by.length ? result.blocked_by.join(", ") : "Agent failed"}
      </div>
    );
  }
  if (agent === "aie") {
    return <AieResult result={result} />;
  }
  if (agent === "sae") {
    return <SaeResult result={result} />;
  }
  if (agent === "dta") {
    return <DtaResult result={result} />;
  }
  return <CdsResult result={result} />;
}

function AieResult({ result }: { result: AgentResult }) {
  const output = result.output;
  const statusBySchool = asRecord(output.official_status_by_school);
  const programBySchool = asRecord(output.target_program_by_school);
  const urlsBySchool = asRecord(output.official_source_urls_by_school);
  const records = asRecordArray(output.official_records);
  const forecastSignals = asRecordArray(output.forecast_signals);

  return (
    <div className="grid gap-4">
      <div className="grid gap-3 lg:grid-cols-2">
        {Object.keys(statusBySchool).map((school) => {
          const urls = asRecord(urlsBySchool[school]);
          return (
            <div key={school} className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <div className="flex items-center justify-between gap-3">
                <span className="font-semibold">{school}</span>
                <span className="rounded-full bg-white px-2 py-1 text-xs text-slate-700">
                  {toText(statusBySchool[school])}
                </span>
              </div>
              <p className="mt-2 text-sm text-slate-600">
                Program: {toText(programBySchool[school])}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {Object.values(urls)
                  .slice(0, 2)
                  .map((url, index) => (
                    <a
                      key={`${school}-${index}`}
                      className="rounded-full border border-slate-300 bg-white px-3 py-1 text-xs font-semibold text-pine"
                      href={toText(url)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      source {index + 1}
                    </a>
                  ))}
              </div>
            </div>
          );
        })}
      </div>
      <MetricStrip
        items={[
          ["Official records", String(records.length)],
          ["Forecast signals", String(forecastSignals.length)],
          ["Cycle", toText(output.cycle)],
          ["As of", toText(output.as_of_date)]
        ]}
      />
    </div>
  );
}

function SaeResult({ result }: { result: AgentResult }) {
  const output = result.output;
  const recommendations = asRecordArray(output.recommendations);
  const gapActions = englishItems(asStringArray(output.gap_actions), "Gap action");
  const strengths = englishItems(asStringArray(output.strengths), "Strength");
  const weaknesses = englishItems(asStringArray(output.weaknesses), "Weakness");
  const modelBreakdown = asRecord(output.model_breakdown);

  return (
    <div className="grid gap-4">
      <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
        <p className="text-xs font-bold uppercase tracking-wide text-pine">Strategy Summary</p>
        <p className="mt-2 text-sm leading-6 text-slate-700">
        {englishText(
          output.summary,
          `Completed evaluation for ${recommendations.length} target programs.`
        )}
        </p>
      </div>

      <div className="overflow-x-auto rounded-md border border-slate-200">
        <table className="w-full min-w-[720px] border-collapse text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="border-b border-slate-200 px-3 py-3">School / Program</th>
              <th className="border-b border-slate-200 px-3 py-3">Tier</th>
              <th className="border-b border-slate-200 px-3 py-3">Overall</th>
              <th className="border-b border-slate-200 px-3 py-3">Rule</th>
              <th className="border-b border-slate-200 px-3 py-3">Semantic</th>
              <th className="border-b border-slate-200 px-3 py-3">Risk</th>
            </tr>
          </thead>
          <tbody>
            {recommendations.map((item) => (
              <tr key={`${toText(item.school)}-${toText(item.program)}`}>
                <td className="border-b border-slate-200 px-3 py-3">
                  <p className="font-semibold">{toText(item.school)}</p>
                  <p className="text-xs text-slate-500">{toText(item.program)}</p>
                </td>
                <td className="border-b border-slate-200 px-3 py-3">
                  <span className="rounded-full bg-emerald-50 px-2 py-1 text-xs font-semibold text-pine">
                    {toText(item.tier)}
                  </span>
                </td>
                <td className="border-b border-slate-200 px-3 py-3 font-semibold">
                  {scoreText(item.overall_score)}
                </td>
                <td className="border-b border-slate-200 px-3 py-3">
                  {scoreText(item.rule_score)}
                </td>
                <td className="border-b border-slate-200 px-3 py-3">
                  {scoreText(item.semantic_score)}
                </td>
                <td className="border-b border-slate-200 px-3 py-3">
                  {scoreText(item.risk_score)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        {recommendations.map((item, index) => (
          <div
            key={`${toText(item.school)}-details`}
            className="rounded-md border border-slate-200 bg-slate-50 p-3"
          >
            <p className="font-semibold">
              {index + 1}. {toText(item.school)}
            </p>
            <ListBlock
              compact
              title="Reasons"
              items={englishItems(asStringArray(item.reasons), "Recommendation reason")}
            />
            <ListBlock
              compact
              title="Gaps"
              items={englishItems(asStringArray(item.gaps), "Program gap")}
            />
            <ListBlock
              compact
              title="Risk flags"
              items={englishItems(asStringArray(item.risk_flags), "Risk flag")}
            />
          </div>
        ))}
      </div>

      <MetricStrip
        items={Object.entries(modelBreakdown).map(([key, value]) => [
          `${key} weight`,
          scoreText(value)
        ])}
      />
      <div className="grid gap-3 xl:grid-cols-3">
        <ListBlock title="Strengths" items={strengths} />
        <ListBlock title="Weaknesses" items={weaknesses} />
        <ListBlock title="Gap actions" items={gapActions} />
      </div>
    </div>
  );
}

function DtaResult({ result }: { result: AgentResult }) {
  const output = result.output;
  const milestones = asRecordArray(output.milestones);
  const weeklyPlan = asRecordArray(output.weekly_plan);
  const riskMarkers = asRecordArray(output.risk_markers);

  return (
    <div className="grid gap-4">
      <div>
        <p className="text-sm font-semibold text-slate-500">Board</p>
        <h3 className="mt-1 text-xl font-semibold">
          {englishText(output.board_title, "Application timeline board")}
        </h3>
      </div>

      <div className="overflow-x-auto rounded-md border border-slate-200">
        <table className="w-full min-w-[820px] border-collapse text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="border-b border-slate-200 px-3 py-3">Week</th>
              <th className="border-b border-slate-200 px-3 py-3">Focus</th>
              <th className="border-b border-slate-200 px-3 py-3">Tasks</th>
              <th className="border-b border-slate-200 px-3 py-3">School scope</th>
              <th className="border-b border-slate-200 px-3 py-3">Risks</th>
            </tr>
          </thead>
          <tbody>
            {weeklyPlan.map((week) => (
              <tr key={toText(week.week)}>
                <td className="border-b border-slate-200 px-3 py-3 font-semibold">
                  Week {toText(week.week)}
                </td>
                <td className="border-b border-slate-200 px-3 py-3">
                  {englishText(week.focus, "Application progress")}
                </td>
                <td className="border-b border-slate-200 px-3 py-3">
                  <ul className="grid gap-1">
                    {englishItems(asStringArray(week.items), "Weekly task").map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </td>
                <td className="border-b border-slate-200 px-3 py-3">
                  {asStringArray(week.school_scope).join(", ") || "All target schools"}
                </td>
                <td className="border-b border-slate-200 px-3 py-3">
                  {englishItems(asStringArray(week.risks), "Weekly risk").join("; ") || "None"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <div className="overflow-x-auto rounded-md border border-slate-200">
          <table className="w-full min-w-[420px] border-collapse text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="border-b border-slate-200 px-3 py-3">Milestone</th>
                <th className="border-b border-slate-200 px-3 py-3">Due</th>
                <th className="border-b border-slate-200 px-3 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {milestones.map((item, index) => (
                <tr key={toText(item.key)}>
                  <td className="border-b border-slate-200 px-3 py-3">
                    {englishText(item.title, `Milestone ${index + 1}`)}
                  </td>
                  <td className="border-b border-slate-200 px-3 py-3">
                    Week {toText(item.due_week)}
                  </td>
                  <td className="border-b border-slate-200 px-3 py-3">
                    {toText(item.status)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <ListBlock
          title="Risk markers"
          items={riskMarkers.map(
            (item, index) =>
              `${toText(item.level)}: ${englishText(item.message, `Risk marker ${index + 1}`)}`
          )}
        />
        <ListBlock
          title="Document instructions"
          items={englishItems(asStringArray(output.document_instructions), "Document instruction")}
        />
      </div>
    </div>
  );
}

function CdsResult({ result }: { result: AgentResult }) {
  const output = result.output;
  const drafts = asRecordArray(output.document_drafts);
  const talkingPoints = englishItems(
    asStringArray(output.interview_talking_points),
    "Interview talking point"
  );
  const checklist = englishItems(asStringArray(output.review_checklist), "Review item");
  const issues = asRecordArray(output.consistency_issues);

  return (
    <div className="grid gap-4">
      <div className="grid gap-3 xl:grid-cols-2">
        {drafts.map((draft) => (
          <div
            key={`${toText(draft.target_school)}-${toText(draft.document_type)}`}
            className="rounded-md border border-slate-200 bg-slate-50 p-3"
          >
            <div className="flex items-center justify-between gap-3">
              <span className="font-semibold">{toText(draft.target_school)}</span>
              <span className="rounded-full bg-white px-2 py-1 text-xs text-slate-700">
                {toText(draft.document_type)}
              </span>
            </div>
            <ul className="mt-3 grid gap-1 text-sm text-slate-700">
              {englishItems(asStringArray(draft.content_outline), "Document outline item").map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            <div className="mt-3 overflow-x-auto rounded-md border border-slate-200 bg-white">
              <table className="w-full min-w-[420px] border-collapse text-left text-xs">
                <thead className="bg-slate-50 uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="border-b border-slate-200 px-3 py-2">Fact slot</th>
                    <th className="border-b border-slate-200 px-3 py-2">Source</th>
                    <th className="border-b border-slate-200 px-3 py-2">Verified</th>
                  </tr>
                </thead>
                <tbody>
                  {asRecordArray(draft.fact_slots).map((slot) => (
                    <tr key={toText(slot.slot_id)}>
                      <td className="border-b border-slate-200 px-3 py-2">
                        {englishText(slot.value, toText(slot.slot_id))}
                      </td>
                      <td className="border-b border-slate-200 px-3 py-2">
                        {toText(slot.source_ref)}
                      </td>
                      <td className="border-b border-slate-200 px-3 py-2">
                        {slot.verified ? "Yes" : "No"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-xs font-semibold text-slate-500">
              Review status: {toText(draft.review_status)}
            </p>
          </div>
        ))}
      </div>
      <div className="grid gap-3 xl:grid-cols-3">
        <ListBlock title="Interview talking points" items={talkingPoints} />
        <ListBlock title="Review checklist" items={checklist} />
        <ListBlock
          title="Consistency issues"
          items={
            issues.length
              ? issues.map((item, index) =>
                  englishText(item.message, `Consistency issue ${index + 1}`)
                )
              : ["No consistency issues"]
          }
        />
      </div>
    </div>
  );
}

function FieldGroup({
  children,
  error,
  htmlFor,
  label
}: {
  children: React.ReactNode;
  error?: MissingProfileField;
  htmlFor: string;
  label: string;
}) {
  const helperText = error?.help_text ?? "";
  return (
    <div className="grid min-w-0 gap-1.5">
      <label className="text-sm font-semibold text-slate-700" htmlFor={htmlFor}>
        {label}
      </label>
      {children}
      <p className={`min-h-10 text-xs leading-5 ${error ? "text-amber-800" : "invisible"}`}>
        {helperText || "placeholder"}
      </p>
    </div>
  );
}

function StatusBadge({
  response,
  isRunning
}: {
  response: OrchestrationResponse | null;
  isRunning: boolean;
}) {
  if (isRunning) {
    return (
      <span className="inline-flex items-center gap-2 rounded-full bg-brass px-3 py-2 text-sm font-semibold text-white">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        Running
      </span>
    );
  }
  if (!response) {
    return (
      <span className="inline-flex items-center gap-2 rounded-full border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700">
        <ShieldCheck className="h-4 w-4" aria-hidden="true" />
        Ready
      </span>
    );
  }
  const failed = response.status === "failed" || response.status === "needs_profile_input";
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full px-3 py-2 text-sm font-semibold ${
        failed ? "bg-amber-100 text-amber-950" : "bg-emerald-100 text-emerald-950"
      }`}
    >
      {failed ? (
        <AlertTriangle className="h-4 w-4" aria-hidden="true" />
      ) : (
        <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
      )}
      {response.status}
    </span>
  );
}

function StageStateBadge({ state }: { state: string }) {
  const className =
    state === "done"
      ? "bg-emerald-100 text-emerald-950"
      : state === "running"
        ? "bg-brass text-white"
        : state === "failed"
          ? "bg-red-100 text-red-950"
          : "bg-white text-slate-600";
  return (
    <span className={`rounded-full px-2 py-1 text-xs font-semibold ${className}`}>
      {state}
    </span>
  );
}

function MetricStrip({ items }: { items: Array<[string, string]> }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {items.map(([label, value]) => (
        <div key={label} className="rounded-md border border-slate-200 bg-slate-50 p-3">
          <p className="text-xs font-semibold uppercase text-slate-500">{label}</p>
          <p className="mt-1 text-lg font-semibold">{value}</p>
        </div>
      ))}
    </div>
  );
}

function ListBlock({
  compact = false,
  title,
  items
}: {
  compact?: boolean;
  title: string;
  items: string[];
}) {
  return (
    <div className={`rounded-md border border-slate-200 bg-slate-50 ${compact ? "mt-3 p-2" : "p-3"}`}>
      <p className={compact ? "text-xs font-bold uppercase tracking-wide text-slate-500" : "font-semibold"}>
        {title}
      </p>
      <ul className={`${compact ? "mt-2 gap-1 text-xs" : "mt-3 gap-2 text-sm"} grid text-slate-700`}>
        {items.length ? items.map((item) => <li key={item}>{item}</li>) : <li>No items</li>}
      </ul>
    </div>
  );
}

function inputClass(hasError: boolean): string {
  return `block w-full min-w-0 max-w-full rounded-md border bg-white px-3 py-2 text-sm text-ink focus:border-pine focus:outline-none focus:ring-2 focus:ring-inset focus:ring-pine ${
    hasError ? "border-amber-500" : "border-slate-300"
  }`;
}

function uniqueValues(values: string[]): string[] {
  return Array.from(new Set(values.filter(Boolean)));
}

function upsertAgentResult(results: AgentResult[], nextResult: AgentResult): AgentResult[] {
  const nextResults = results.filter((item) => item.agent !== nextResult.agent);
  nextResults.push(nextResult);
  return nextResults.sort(
    (left, right) =>
      STAGES.findIndex((stage) => stage.agent === left.agent) -
      STAGES.findIndex((stage) => stage.agent === right.agent)
  );
}

function stageState({
  agent,
  completedStages,
  isRunning,
  result,
  runningStage
}: {
  agent: AgentCode;
  completedStages: AgentCode[];
  isRunning: boolean;
  result: AgentResult | undefined;
  runningStage: AgentCode | null;
}): string {
  if (result?.status === "SUCCESS") {
    return "done";
  }
  if (result?.status === "FAILED") {
    return "failed";
  }
  if (result?.status === "SKIPPED" || result?.status === "DEGRADED") {
    return "blocked";
  }
  if (!isRunning) {
    return "waiting";
  }
  if (completedStages.includes(agent)) {
    return "done";
  }
  if (runningStage === agent) {
    return "running";
  }
  return "waiting";
}

function stageIcon(agent: AgentCode) {
  if (agent === "sae") {
    return BarChart3;
  }
  if (agent === "dta") {
    return PieChart;
  }
  if (agent === "cds") {
    return MessageSquare;
  }
  return FileText;
}

function stageStyle(state: string): { card: string; icon: string } {
  if (state === "done") {
    return {
      card: "border-pine shadow-[0_0_0_1px_rgba(15,95,88,0.16)]",
      icon: "text-pine"
    };
  }
  if (state === "running") {
    return {
      card: "border-brass shadow-[0_0_0_1px_rgba(184,121,42,0.16)]",
      icon: "text-brass"
    };
  }
  if (state === "failed" || state === "blocked") {
    return {
      card: "border-amber-400 shadow-[0_0_0_1px_rgba(184,121,42,0.16)]",
      icon: "text-brass"
    };
  }
  return {
    card: "border-slate-300",
    icon: "text-slate-600"
  };
}

function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function asRecordArray(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value)
    ? value.filter((item): item is Record<string, unknown> => {
        return Boolean(item) && typeof item === "object" && !Array.isArray(item);
      })
    : [];
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => String(item)).filter((item) => item.trim())
    : [];
}

const CJK_PATTERN = /[\u3400-\u9fff]/;

function englishItems(items: string[], fallbackPrefix: string): string[] {
  return items.map((item, index) => englishText(item, `${fallbackPrefix} ${index + 1}`));
}

function englishText(value: unknown, fallback: string): string {
  const text = toText(value);
  if (!CJK_PATTERN.test(text)) {
    return text;
  }
  return fallback;
}

function toText(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "n/a";
  }
  return String(value);
}

function scoreText(value: unknown): string {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric.toFixed(2) : "n/a";
}

function formatRunDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}
