import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import {
  MessageSquare,
  Radio,
  Timer,
  Heart,
  Activity,
  Brain,
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
import MemoryPage from "./pages/MemoryPage";
import AgentConfigPage from "./pages/AgentConfigPage";
import ModelsPage from "./pages/ModelsPage";
import ConsoleCronBubble from "./components/ConsoleCronBubble";
import { IconBadge } from "./components/icons";
import mathClawLogo from "../../logo.png";

type ShellNavItem = { to: string; label: string; hint: string; icon: ReactNode };

const studentNav: ShellNavItem[] = [
  { to: "/chat", label: "解题工作台", hint: "AI 对话与工具轨迹", icon: <IconBadge tone="brand" size="sm"><MessageSquare size={14} /></IconBadge> },
  { to: "/cron-jobs", label: "学习计划", hint: "定时任务与提醒", icon: <IconBadge tone="amber" size="sm"><Timer size={14} /></IconBadge> },
  { to: "/status", label: "运行状态", hint: "健康检查与依赖", icon: <IconBadge tone="violet" size="sm"><Activity size={14} /></IconBadge> },
];

const systemNav: ShellNavItem[] = [
  { to: "/channels", label: "频道", hint: "多通道连接", icon: <IconBadge tone="blue" size="sm"><Radio size={14} /></IconBadge> },
  { to: "/heartbeat", label: "心跳", hint: "检查与提醒", icon: <IconBadge tone="danger" size="sm"><Heart size={14} /></IconBadge> },
  { to: "/memory", label: "记忆", hint: "跨会话学习画像", icon: <IconBadge tone="green" size="sm"><Brain size={14} /></IconBadge> },
  { to: "/skills", label: "Skills", hint: "Skill 生命周期", icon: <IconBadge tone="brand" size="sm"><Puzzle size={14} /></IconBadge> },
  { to: "/mcp", label: "MCP", hint: "MCP 工具连接", icon: <IconBadge tone="teal" size="sm"><Cable size={14} /></IconBadge> },
  { to: "/agent-config", label: "Agent 配置", hint: "提示词与策略", icon: <IconBadge tone="violet" size="sm"><Settings size={14} /></IconBadge> },
  { to: "/models", label: "模型配置", hint: "模型与提供商", icon: <IconBadge tone="blue" size="sm"><Cpu size={14} /></IconBadge> },
  { to: "/environments", label: "环境变量", hint: "密钥与运行变量", icon: <IconBadge tone="amber" size="sm"><KeyRound size={14} /></IconBadge> },
];


function SideLink({ item }: { item: ShellNavItem }) {
  return (
    <NavLink to={item.to} className={({ isActive }) => `mc-nav-item${isActive ? " active" : ""}`}>
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

  return (
    <div className="mc-shell" data-build="20260317-r1">
      <aside className="mc-sidebar">
        <div className="mc-brand">
          <div className="mc-brand-mark">
            <img src={mathClawLogo} alt="MathClaw Logo" className="mc-brand-mark-img" />
          </div>
          <div className="mc-brand-copy">
            <div className="mc-brand-title">MathClaw</div>
          </div>
        </div>

        <div className="mc-nav-group">
          <div className="mc-nav-label">学生工作台</div>
          {studentNav.map((item) => <SideLink key={item.to} item={item} />)}
        </div>

        <div className="mc-nav-group mc-nav-group-bottom">
          <div className="mc-nav-label">系统控制台</div>
          {systemNav.map((item) => <SideLink key={item.to} item={item} />)}
        </div>
      </aside>

      <section className="mc-main-wrap">

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
            <Route path="/memory" element={<MemoryPage />} />
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
