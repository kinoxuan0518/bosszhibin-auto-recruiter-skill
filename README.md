# bosszhibin-auto-recruiter-skill

Boss直聘自动招聘技能（v7.3 consolidated）。

## 当前版本

- Skill: `v7.3-consolidated`
- 主文件: `SKILL.md`
- 结构: 两层

1. 执行必需：`SKILL.md`
2. 按需参考：`references/` 模板文件

## 目录结构

```text
.
├── SKILL.md
├── agents/
│   └── openai.yaml
└── references/
    ├── execution_metrics_template.json
    ├── auto_reflection_report_template.md
    └── evolution_history_template.json
```

## 使用方式

1. 把本仓库内容安装到 Codex 全局技能目录（或直接引用）。
2. 启动会话时触发该技能。
3. 执行时优先读取 `SKILL.md`，仅在需要模板时再读取 `references/`。

## 设计要点

- 运行协议内聚在单文件：终止条件、频率退避、幂等、人工中断、流程模式。
- 职位规则走缓存分层：`global_rule_defaults + jobs[].rule_overrides`。
- 模板与结构定义外置：减少每轮执行前的读取开销。

## 兼容说明

- 历史版本文档（v7.1）已从主分支移除。
- 执行指标模板中的 `skill_version` 已对齐为 `7.3-consolidated`。
