import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import {
  MessageSquare,
  FileText,
  Radio,
  MessageCircle,
  Timer,
  Heart,
  Activity,
  FolderOpen,
  Puzzle,
  Cable,
  Settings,
  Cpu,
  KeyRound,
} from "lucide-react";
import ChatPage from "./pages/ChatPage";
import PapersPage from "./pages/PapersPage";
import StatusPage from "./pages/StatusPage";
import ChannelsPage from "./pages/ChannelsPage";
import SessionsPage from "./pages/SessionsPage";
import CronJobsPage from "./pages/CronJobsPage";
import HeartbeatPage from "./pages/HeartbeatPage";
import EnvironmentsPage from "./pages/EnvironmentsPage";
import SkillsPage from "./pages/SkillsPage";
import McpPage from "./pages/McpPage";
import WorkspacePage from "./pages/WorkspacePage";
import AgentConfigPage from "./pages/AgentConfigPage";
import ModelsPage from "./pages/ModelsPage";
import ConsoleCronBubble from "./components/ConsoleCronBubble";
import { IconBadge } from "./components/icons";
import { useI18n } from "./i18n";

type ShellNavItem = {
  to: string;
  label: string;
  hint: string;
  icon: ReactNode;
};

type Meta = {
  title: string;
  desc: string;
  ctaLabel: string;
  ctaTo: string;
};

const studentNav: ShellNavItem[] = [
  {
    to: "/chat",
    label: "Solve Workspace",
    hint: "AI chat with tool traces",
    icon: (
      <IconBadge tone="brand" size="sm">
        <MessageSquare size={14} />
      </IconBadge>
    ),
  },
  {
    to: "/papers",
    label: "Paper Search",
    hint: "ArXiv / Scholar retrieval",
    icon: (
      <IconBadge tone="teal" size="sm">
        <FileText size={14} />
      </IconBadge>
    ),
  },
  {
    to: "/sessions",
    label: "Sessions",
    hint: "History and replay",
    icon: (
      <IconBadge tone="green" size="sm">
        <MessageCircle size={14} />
      </IconBadge>
    ),
  },
  {
    to: "/cron-jobs",
    label: "Study Plan",
    hint: "Cron tasks and reminders",
    icon: (
      <IconBadge tone="amber" size="sm">
        <Timer size={14} />
      </IconBadge>
    ),
  },
  {
    to: "/status",
    label: "Runtime Status",
    hint: "Health and dependencies",
    icon: (
      <IconBadge tone="violet" size="sm">
        <Activity size={14} />
      </IconBadge>
    ),
  },
];

const systemNav: ShellNavItem[] = [
  {
    to: "/channels",
    label: "Channels",
    hint: "Multi-channel connections",
    icon: (
      <IconBadge tone="blue" size="sm">
        <Radio size={14} />
      </IconBadge>
    ),
  },
  {
    to: "/heartbeat",
    label: "Heartbeat",
    hint: "Checks and alerts",
    icon: (
      <IconBadge tone="danger" size="sm">
        <Heart size={14} />
      </IconBadge>
    ),
  },
  {
    to: "/workspace",
    label: "Workspace",
    hint: "Files and key context",
    icon: (
      <IconBadge tone="slate" size="sm">
        <FolderOpen size={14} />
      </IconBadge>
    ),
  },
  {
    to: "/skills",
    label: "Skills",
    hint: "Skill lifecycle",
    icon: (
      <IconBadge tone="brand" size="sm">
        <Puzzle size={14} />
      </IconBadge>
    ),
  },
  {
    to: "/mcp",
    label: "MCP",
    hint: "Tool gateway",
    icon: (
      <IconBadge tone="teal" size="sm">
        <Cable size={14} />
      </IconBadge>
    ),
  },
  {
    to: "/agent-config",
    label: "Agent Config",
    hint: "Prompt and strategy",
    icon: (
      <IconBadge tone="violet" size="sm">
        <Settings size={14} />
      </IconBadge>
    ),
  },
  {
    to: "/models",
    label: "Models",
    hint: "Model providers",
    icon: (
      <IconBadge tone="blue" size="sm">
        <Cpu size={14} />
      </IconBadge>
    ),
  },
  {
    to: "/environments",
    label: "Env Vars",
    hint: "Secrets and runtime vars",
    icon: (
      <IconBadge tone="amber" size="sm">
        <KeyRound size={14} />
      </IconBadge>
    ),
  },
];

const pageMeta: Record<string, Meta> = {
  "/chat": {
    title: "MathClaw Solve Workspace",
    desc: "Web-style shell on top of the original ResearchClaw console capabilities.",
    ctaLabel: "New Chat",
    ctaTo: "/chat",
  },
  "/papers": {
    title: "Paper Search",
    desc: "Original retrieval features are preserved with a new shell experience.",
    ctaLabel: "Search Papers",
    ctaTo: "/papers",
  },
  "/sessions": {
    title: "Sessions and Replay",
    desc: "Keep all existing session management and traceability functions.",
    ctaLabel: "Refresh Sessions",
    ctaTo: "/sessions",
  },
  "/cron-jobs": {
    title: "Cron Plans",
    desc: "Keep scheduling, reminders, and recurring automation behavior.",
    ctaLabel: "New Job",
    ctaTo: "/cron-jobs",
  },
  "/status": {
    title: "System Status",
    desc: "Keep API, runtime, and dependency health diagnostics.",
    ctaLabel: "View Status",
    ctaTo: "/status",
  },
  "/channels": {
    title: "Channels",
    desc: "Keep channel configuration and dispatch behavior.",
    ctaLabel: "Manage Channels",
    ctaTo: "/channels",
  },
  "/heartbeat": {
    title: "Heartbeat",
    desc: "Keep heartbeats and infrastructure checks.",
    ctaLabel: "Run Check",
    ctaTo: "/heartbeat",
  },
  "/workspace": {
    title: "Workspace",
    desc: "Keep file inspection and editor workflows.",
    ctaLabel: "Refresh Workspace",
    ctaTo: "/workspace",
  },
  "/skills": {
    title: "Skills",
    desc: "Keep skill loading, listing, and control.",
    ctaLabel: "Refresh Skills",
    ctaTo: "/skills",
  },
  "/mcp": {
    title: "MCP Clients",
    desc: "Keep MCP client configuration and connection details.",
    ctaLabel: "Add Client",
    ctaTo: "/mcp",
  },
  "/agent-config": {
    title: "Agent Config",
    desc: "Keep agent policy parameters and runtime config.",
    ctaLabel: "Load Config",
    ctaTo: "/agent-config",
  },
  "/models": {
    title: "Models and Providers",
    desc: "Keep provider management and hot-apply behavior.",
    ctaLabel: "Add Provider",
    ctaTo: "/models",
  },
  "/environments": {
    title: "Environment Variables",
    desc: "Keep secret keys and runtime variable management.",
    ctaLabel: "Refresh Env",
    ctaTo: "/environments",
  },
};

function resolveMeta(pathname: string): Meta {
  if (pathname === "/") return pageMeta["/chat"];
  return pageMeta[pathname] ?? pageMeta["/chat"];
}

function SideLink({ item }: { item: ShellNavItem }) {
  return (
    <NavLink
      to={item.to}
      className={({ isActive }) =>
        `mc-nav-item${isActive ? " active" : ""}`
      }
    >
      <span className="mc-nav-icon">{item.icon}</span>
      <span className="mc-nav-text">
        <strong>{item.label}</strong>
        <small>{item.hint}</small>
      </span>
    </NavLink>
  );
}

export default function App() {
  const location = useLocation();
  const { locale, setLocale } = useI18n();
  const meta = resolveMeta(location.pathname);

  return (
    <div className="mc-shell">
      <aside className="mc-sidebar">
        <div className="mc-brand">
          <div className="mc-brand-mark">
            <img
              src="/researchclaw-symbol.png"
              alt="ResearchClaw Symbol"
              className="mc-brand-mark-img"
            />
          </div>
          <div>
            <div className="mc-brand-title">MathClaw Console</div>
            <div className="mc-brand-sub">Research workflow + learning shell</div>
          </div>
        </div>

        <div className="mc-nav-group">
          <div className="mc-nav-label">Student Workspace</div>
          {studentNav.map((item) => (
            <SideLink key={item.to} item={item} />
          ))}
        </div>

        <div className="mc-nav-group mc-nav-group-bottom">
          <div className="mc-nav-label">System Console</div>
          {systemNav.map((item) => (
            <SideLink key={item.to} item={item} />
          ))}
        </div>

        <div className="mc-side-status">
          <div className="mc-status-title">
            <span className="mc-dot" /> ResearchClaw Running
          </div>
          <div className="mc-status-grid">
            <span>Backend API</span>
            <span>Online</span>
            <span>MCP</span>
            <span>Ready</span>
            <span>Skills</span>
            <span>Loaded</span>
          </div>
          <div className="mc-lang-switch">
            <button
              type="button"
              className={`mc-lang-btn${locale === "zh" ? " active" : ""}`}
              onClick={() => setLocale("zh")}
            >
              ZH
            </button>
            <button
              type="button"
              className={`mc-lang-btn${locale === "en" ? " active" : ""}`}
              onClick={() => setLocale("en")}
            >
              EN
            </button>
          </div>
        </div>
      </aside>

      <section className="mc-main-wrap">
        <header className="mc-topbar">
          <div>
            <div className="mc-eyebrow">MathClaw x ResearchClaw</div>
            <h1>{meta.title}</h1>
            <p>{meta.desc}</p>
          </div>
          <div className="mc-topbar-actions">
            <div className="mc-search-box">Search chats, papers, jobs, skills...</div>
            <NavLink to={meta.ctaTo} className="mc-btn mc-btn-primary">
              {meta.ctaLabel}
            </NavLink>
          </div>
        </header>

        <main className="content mc-content">
          <ConsoleCronBubble />
          <Routes location={location} key={location.pathname}>
            <Route path="/" element={<ChatPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/papers" element={<PapersPage />} />
            <Route path="/channels" element={<ChannelsPage />} />
            <Route path="/sessions" element={<SessionsPage />} />
            <Route path="/cron-jobs" element={<CronJobsPage />} />
            <Route path="/heartbeat" element={<HeartbeatPage />} />
            <Route path="/status" element={<StatusPage />} />
            <Route path="/workspace" element={<WorkspacePage />} />
            <Route path="/skills" element={<SkillsPage />} />
            <Route path="/agent-config" element={<AgentConfigPage />} />
            <Route path="/models" element={<ModelsPage />} />
            <Route path="/environments" element={<EnvironmentsPage />} />
            <Route path="/mcp" element={<McpPage />} />
          </Routes>
        </main>
      </section>
    </div>
  );
}

