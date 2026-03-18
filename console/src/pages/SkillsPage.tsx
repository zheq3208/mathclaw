import { useEffect, useMemo, useState } from "react";
import { Puzzle, RefreshCw, Sparkles, Trash2 } from "lucide-react";
import {
  listSkills,
  listActiveSkills,
  enableSkill,
  disableSkill,
  previewMarkdownSkills,
  createGeneratedSkills,
  deleteSkill,
} from "../api";
import type { SkillDraft, SkillItem } from "../types";
import {
  Badge,
  DetailModal,
  PageHeader,
  Toggle,
} from "../components/ui";

const SKILL_LABELS: Record<string, string> = {
  browser_visible: "Browser",
  cron: "Timer",
  difficulty_calibrator: "Level",
  dingtalk_channel: "DingTalk",
  dingtalk_channel_connect: "DingTalk",
  docx: "DOCX",
  experiment_tracker: "Tracker",
  figure_generator: "Figure",
  file_reader: "Reader",
  formula_render_check: "Formula",
  guiding_users: "Guide",
  himalaya: "Himalaya",
  hint_ladder_policy: "Hints",
  information_architecture: "IA",
  knowledge_extractor: "Extract",
  knowledge_synthesizer: "Synth",
  mastery_updater: "Mastery",
  math_solver_verifier: "Verifier",
  micro_quiz: "Quiz",
  multimodal_analysis: "Vision",
  news: "News",
  ocr_document_processor: "OCR",
  pdf: "PDF",
  pptx: "PPT",
  problem_json_normalizer: "JSON",
  remember: "Memory",
  math_notes: "Notes",
  review_scheduler: "Review",
  socratic_math_tutor: "Socratic",
  sympy: "SymPy",
  variant_generator: "Variants",
  vision_transcribe: "Vision OCR",
  weakness_diagnoser: "Diagnose",
  xlsx: "XLSX",
};

const SKILL_DESCRIPTIONS: Record<string, string> = {
  browser_visible: "真实浏览器操作",
  cron: "定时执行任务",
  difficulty_calibrator: "评估题目难度",
  dingtalk_channel: "钉钉频道接入",
  dingtalk_channel_connect: "钉钉频道接入",
  docx: "读取和编辑 Word",
  experiment_tracker: "记录实验过程",
  figure_generator: "生成图表",
  file_reader: "读取本地文件",
  formula_render_check: "检查公式渲染",
  guiding_users: "分步引导学生",
  himalaya: "Himalaya 工具链",
  hint_ladder_policy: "控制提示层级",
  information_architecture: "整理题目结构",
  knowledge_extractor: "提取知识点",
  knowledge_synthesizer: "总结核心知识",
  mastery_updater: "更新掌握度",
  math_solver_verifier: "校验解题过程",
  micro_quiz: "生成小测题",
  multimodal_analysis: "理解图文输入",
  news: "新闻信息查询",
  ocr_document_processor: "文档 OCR",
  pdf: "读取 PDF",
  pptx: "读取和编辑 PPT",
  problem_json_normalizer: "转成题目 JSON",
  remember: "记录学习记忆",
  math_notes: "整理笔记",
  review_scheduler: "安排复习提醒",
  socratic_math_tutor: "苏格拉底式讲解",
  sympy: "符号计算校验",
  variant_generator: "生成变式题",
  vision_transcribe: "图片题 OCR",
  weakness_diagnoser: "诊断薄弱点",
  xlsx: "读取和编辑表格",
};

const CORE_PIPELINE_SKILLS = [
  { id: "ocr_document_processor", label: "OCR", description: "结构化识别试卷" },
  { id: "math_solver_verifier", label: "Solve", description: "求解与验证" },
  { id: "weakness_diagnoser", label: "Diagnose", description: "定位薄弱点" },
  { id: "guiding_users", label: "Guide", description: "引导式讲解" },
  { id: "variant_generator", label: "Variants", description: "生成变式题" },
] as const;

const CORE_PIPELINE_SKILL_IDS: Set<string> = new Set(
  CORE_PIPELINE_SKILLS.map((skill) => skill.id),
);

function getSkillId(skill: SkillItem, fallback: string) {
  const pathName = skill.path?.split("/").filter(Boolean).pop();
  return pathName || fallback;
}

function getSkillLabel(skillId: string, fallback: string) {
  return SKILL_LABELS[skillId] || SKILL_LABELS[fallback] || fallback;
}

function getSkillDescription(skillId: string, fallback: string, rawName: string) {
  return (
    SKILL_DESCRIPTIONS[skillId]
    || SKILL_DESCRIPTIONS[rawName]
    || fallback
    || "自定义技能"
  );
}

function getSkillCategories(skill: SkillItem) {
  return Array.isArray(skill.categories) ? skill.categories.slice(0, 3) : [];
}

export default function SkillsPage() {
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [active, setActive] = useState<string[]>([]);
  const [, setLoaded] = useState(false);
  const [listError, setListError] = useState("");
  const [creatorInput, setCreatorInput] = useState("");
  const [previewing, setPreviewing] = useState(false);
  const [installingPreview, setInstallingPreview] = useState(false);
  const [creatorMessage, setCreatorMessage] = useState("");
  const [creatorError, setCreatorError] = useState("");
  const [deletingSkillId, setDeletingSkillId] = useState("");
  const [previewDrafts, setPreviewDrafts] = useState<SkillDraft[]>([]);
  const [previewOpen, setPreviewOpen] = useState(false);

  async function onLoad() {
    try {
      const [nextSkills, nextActive] = await Promise.all([
        listSkills(),
        listActiveSkills(),
      ]);
      setSkills(nextSkills);
      setActive(nextActive);
      setListError("");
    } catch (error) {
      setListError(error instanceof Error ? error.message : "加载技能失败");
    } finally {
      setLoaded(true);
    }
  }

  useEffect(() => {
    void onLoad();
  }, []);

  const generatedSkills = useMemo(() => {
    return [...skills]
      .filter((skill, idx) => {
        const rawName = skill.name || `skill-${idx}`;
        const skillId = getSkillId(skill, rawName);
        return !CORE_PIPELINE_SKILL_IDS.has(skillId)
          && (skill.deletable === true || skill.generated === true);
      })
      .sort((left, right) => {
        const leftName = getSkillLabel(
          getSkillId(left, left.name || ""),
          left.name || "",
        );
        const rightName = getSkillLabel(
          getSkillId(right, right.name || ""),
          right.name || "",
        );
        return leftName.localeCompare(rightName, "zh-Hans-CN");
      });
  }, [skills]);

  const skillById = useMemo(() => {
    const nextMap = new Map<string, SkillItem>();
    skills.forEach((skill, idx) => {
      const rawName = skill.name || `skill-${idx}`;
      nextMap.set(getSkillId(skill, rawName), skill);
    });
    return nextMap;
  }, [skills]);

  async function onToggle(skillId: string, nextChecked: boolean) {
    if (nextChecked) {
      await enableSkill(skillId);
    } else {
      await disableSkill(skillId);
    }
    await onLoad();
  }

  async function onPreview() {
    const requirements = creatorInput.trim();
    if (requirements.length < 8) {
      setCreatorError("请先写清楚想让 Skill 帮你完成什么");
      return;
    }

    setPreviewing(true);
    setCreatorError("");
    setCreatorMessage("");
    try {
      const drafts = await previewMarkdownSkills(requirements, 2);
      setPreviewDrafts(drafts);
      setPreviewOpen(true);
    } catch (error) {
      setCreatorError(error instanceof Error ? error.message : "预览失败");
    } finally {
      setPreviewing(false);
    }
  }

  async function onInstallPreview() {
    if (previewDrafts.length === 0) {
      setCreatorError("没有可安装的预览内容");
      return;
    }

    setInstallingPreview(true);
    setCreatorError("");
    setCreatorMessage("");
    try {
      const created = await createGeneratedSkills(previewDrafts);
      await onLoad();
      setPreviewOpen(false);
      setPreviewDrafts([]);
      setCreatorInput("");
      const names = created.map((skill, index) => {
        const rawName = skill.name || `skill-${index}`;
        return getSkillLabel(getSkillId(skill, rawName), rawName);
      });
      setCreatorMessage(`已生成并启用：${names.join("、")}`);
    } catch (error) {
      setCreatorError(error instanceof Error ? error.message : "安装失败");
    } finally {
      setInstallingPreview(false);
    }
  }

  async function onDelete(skill: SkillItem, displayName: string) {
    const rawName = skill.name || displayName;
    const skillId = getSkillId(skill, rawName);
    const confirmed = window.confirm(`删除 Skill「${displayName}」？`);
    if (!confirmed) {
      return;
    }

    setDeletingSkillId(skillId);
    setCreatorError("");
    setCreatorMessage("");
    try {
      await deleteSkill(skillId);
      await onLoad();
      setCreatorMessage(`已删除：${displayName}`);
    } catch (error) {
      setCreatorError(error instanceof Error ? error.message : "删除失败");
    } finally {
      setDeletingSkillId("");
    }
  }

  return (
    <div className="panel">
      <PageHeader
        title="技能管理"
        description="系统技能固定保留；Skill Creator 生成的技能需先预览，再确认加入。"
        actions={
          <button onClick={onLoad}>
            <RefreshCw size={15} />
            刷新技能
          </button>
        }
      />

      {listError && (
        <div className="skill-creator-status is-error skill-list-status">
          {listError}
        </div>
      )}

      <div className="card-list animate-list">
        {CORE_PIPELINE_SKILLS.map((coreSkill) => {
          const matchedSkill = skillById.get(coreSkill.id);
          const isActive = true;
          const title = matchedSkill?.name
            ? `${coreSkill.id} - ${matchedSkill.name}`
            : coreSkill.id;
          return (
            <div key={coreSkill.id} className="data-row">
              <div className="data-row-info">
                <div className="data-row-title">
                  <Puzzle
                    size={14}
                    style={{ marginRight: 6, verticalAlign: "middle" }}
                  />
                  <span className="skill-name" title={title}>
                    {coreSkill.label}
                  </span>
                  <span className="skill-state-pill is-on">
                    {"\u5df2\u542f\u52a8"}
                  </span>
                  <Badge variant="neutral">{"\u56fa\u5b9a"}</Badge>
                </div>
                <div className="data-row-meta">{coreSkill.description}</div>
              </div>
              <div className="data-row-actions">
                <Toggle
                  className="skills-toggle"
                  checked={isActive}
                  disabled
                  onChange={() => {}}
                />
              </div>
            </div>
          );
        })}

        {generatedSkills.map((skill: SkillItem, idx: number) => {
          const rawName = skill.name || `skill-${idx}`;
          const skillId = getSkillId(skill, rawName);
          const displayName = getSkillLabel(skillId, rawName);
          const description = getSkillDescription(
            skillId,
            skill.description || "",
            rawName,
          );
          const isActive = active.includes(skillId) || skill.enabled === true;
          const title = rawName === skillId ? skillId : `${skillId} - ${rawName}`;
          const categories = getSkillCategories(skill);
          return (
            <div key={skillId} className="data-row">
              <div className="data-row-info">
                <div className="data-row-title">
                  <Puzzle
                    size={14}
                    style={{ marginRight: 6, verticalAlign: "middle" }}
                  />
                  <span className="skill-name" title={title}>
                    {displayName}
                  </span>
                  <span
                    className={`skill-state-pill ${isActive ? "is-on" : "is-off"}`}
                  >
                    {isActive ? "已启动" : "未启动"}
                  </span>
                  <Badge variant="info">Creator</Badge>
                </div>
                {description && (
                  <div className="data-row-meta">{description}</div>
                )}
                {categories.length > 0 && (
                  <div className="skill-chip-row">
                    {categories.map((category) => (
                      <Badge key={`${skillId}-${category}`} variant="warning">
                        {category}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
              <div className="data-row-actions">
                <button
                  className="btn-secondary btn-icon skill-delete-btn"
                  title="删除这个 Skill"
                  disabled={deletingSkillId === skillId}
                  onClick={() => onDelete(skill, displayName)}
                >
                  <Trash2 size={15} />
                </button>
                <Toggle
                  className="skills-toggle"
                  checked={isActive}
                  onChange={(nextChecked) => onToggle(skillId, nextChecked)}
                />
              </div>
            </div>
          );
        })}
      </div>

      <div className="card skill-creator-panel">
        <div className="skill-creator-header">
          <div className="skill-creator-title">
            <Sparkles size={16} />
            <span>Skill Creator</span>
          </div>
          <Badge variant="info">Qwen3-VL</Badge>
        </div>
        <p className="skill-creator-note">
          写下学生或老师需要的能力，系统会先生成 1-2 个
          <code>SKILL.md</code>
          预览，再由你确认加入技能列表。
        </p>
        <textarea
          className="skill-creator-input"
          value={creatorInput}
          onChange={(event) => setCreatorInput(event.target.value)}
          placeholder="例：我想要一个适合初中生的一元一次方程讲解 Skill，先检查题目条件，再按提示阶梯讲解，最后给出一题同结构练习。"
        />
        <div className="skill-creator-actions">
          <span className="skill-creator-hint">
            系统技能固定保留；Creator 生成技能可删除。
          </span>
          <button onClick={onPreview} disabled={previewing || creatorInput.trim().length < 8}>
            <Sparkles size={15} />
            {previewing ? "生成预览中..." : "生成预览"}
          </button>
        </div>
        {creatorMessage && (
          <div className="skill-creator-status is-success">{creatorMessage}</div>
        )}
        {creatorError && (
          <div className="skill-creator-status is-error">{creatorError}</div>
        )}
      </div>

      {previewOpen && (
        <DetailModal
          title="Skill Creator 预览"
          onClose={() => {
            if (!installingPreview) {
              setPreviewOpen(false);
            }
          }}
        >
          <div className="skill-preview-list">
            {previewDrafts.map((draft) => (
              <div className="skill-preview-card" key={draft.slug}>
                <div className="skill-preview-head">
                  <div>
                    <h4>{draft.title}</h4>
                    <p>{draft.description}</p>
                  </div>
                  <div className="skill-chip-row">
                    {draft.categories.map((category) => (
                      <Badge key={`${draft.slug}-${category}`} variant="warning">
                        {category}
                      </Badge>
                    ))}
                  </div>
                </div>
                <pre className="skill-preview-markdown">{draft.markdown}</pre>
              </div>
            ))}
          </div>
          <div className="skill-preview-actions">
            <button
              className="btn-secondary"
              onClick={() => setPreviewOpen(false)}
              disabled={installingPreview}
            >
              返回编辑
            </button>
            <button onClick={onPreview} disabled={previewing || installingPreview}>
              <RefreshCw size={15} />
              {previewing ? "重新生成中..." : "重新生成"}
            </button>
            <button onClick={onInstallPreview} disabled={installingPreview}>
              <Sparkles size={15} />
              {installingPreview ? "加入中..." : "加入技能"}
            </button>
          </div>
        </DetailModal>
      )}
    </div>
  );
}
