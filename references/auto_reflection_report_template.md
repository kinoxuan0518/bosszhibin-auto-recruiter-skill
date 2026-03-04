# 🧠 自动复盘报告 - 执行质量分析

**生成时间**：{timestamp}
**任务ID**：{execution_id}
**Skill版本**：{skill_version}
**执行时长**：{execution_time_minutes} 分钟

---

## 📊 执行效率评估

### 职位1：{job_name_1}

#### 【遍历效率】{traversal_rating_stars} ({traversal_score}/5)

- ✅ 总滚动次数：{total_scrolls}次
- ✅ 看到候选人：{candidates_seen}人
- ✅ 终止原因：{termination_reason}
- ✅ 遍历耗时：{time_cost_display}
- 💡 **评价**：{traversal_comment}

#### 【筛选效率】{screening_rating_stars} ({screening_score}/5)

- ✅ 候选人总数：{total_candidates}人
- ✅ 已联系过：{already_contacted}人（自动跳过）
- ✅ 通过筛选：{contacted}人 / {available_candidates}人（{pass_rate}%）
- ⚠️  学校不符：{failed_school}人（{school_reject_rate}%）
- ⚠️  公司不符：{failed_company}人（{company_reject_rate}%）
- 💡 **评价**：{screening_comment}

#### 【操作效率】{operation_rating_stars} ({operation_score}/5)

- ✅ 平均批次：{avg_batch_size}人/批
- ✅ 批次数：{batches_processed}批
- ✅ 联系成功率：{contact_success_rate}%
- ✅ 操作失败：{contact_failures}次
- 💡 **评价**：{operation_comment}

#### 【候选人质量】{quality_rating_stars} ({quality_score}/5)

- ✅ 联系候选人平均分：{avg_contacted_score}分
- ✅ 90+优秀候选人：{excellent_count}人（{excellent_ratio}%）
- ✅ 80-89良好候选人：{good_count}人（{good_ratio}%）
- ✅ 70-79合格候选人：{qualified_count}人（{qualified_ratio}%）
- 💡 **评价**：{quality_comment}

---

### 职位2：{job_name_2}

{重复相同结构...}

---

## 🚨 异常检测结果

**【检测到 {anomaly_count} 个问题】**

### ⚠️  问题1：{anomaly_title_1}

**影响**：{anomaly_impact}

**原因分析**：
- {reason_1}
- {reason_2}

**优化建议**：
- **方案A**：{solution_A}（{solution_A_pros}）
- **方案B**：{solution_B}（{solution_B_pros}）
- **方案C**：{solution_C}（{solution_C_pros}）

**建议采纳**：{recommended_solution}（{rationale}）

---

### ⚠️  问题2：{anomaly_title_2}

{重复相同结构...}

---

## 💡 自动优化建议（按优先级排序）

### 建议1：【高优先级】{suggestion_title_1} 🎯

**当前状态**：{current_state_1}

**优化方案**：
- {proposed_change_1}

**预期效果**：{expected_impact_1}

**实施难度**：{implementation_difficulty_1}

---

### 建议2：【中优先级】{suggestion_title_2} ⚡

**当前状态**：{current_state_2}

**优化方案**：
- {proposed_change_2}

**预期效果**：{expected_impact_2}

**实施难度**：{implementation_difficulty_2}

---

### 建议3：【低优先级】{suggestion_title_3} 📊

**当前状态**：{current_state_3}

**优化方案**：
- {proposed_change_3}

**预期效果**：{expected_impact_3}

**实施难度**：{implementation_difficulty_3}

---

## 📈 历史对比分析

**对比上次执行（{previous_execution_date}）：**

### 指标变化：

| 指标 | 上次 | 本次 | 变化 |
|------|------|------|------|
| 遍历完整度 | {prev_coverage}% | {curr_coverage}% | {coverage_change} |
| 候选人覆盖 | {prev_candidates}人 | {curr_candidates}人 | {candidates_change} |
| 联系成功率 | {prev_success_rate}% | {curr_success_rate}% | {success_rate_change} |
| 候选人平均分 | {prev_avg_score}分 | {curr_avg_score}分 | {score_change} |

### 问题改善：
- ✅ {improvement_1}
- ✅ {improvement_2}

### 持续问题：
- ⚠️  {persisting_issue_1}

---

## 🎯 下次执行行动计划

### 立即行动（建议本次任务后执行）：
1. {immediate_action_1}
2. {immediate_action_2}

### 短期优化（1-3天内）：
1. {short_term_optimization_1}
2. {short_term_optimization_2}

### 长期优化（1-2周内）：
1. {long_term_improvement_1}
2. {long_term_improvement_2}

---

## 💾 本次优化已记录到进化历史

**进化记录保存位置**：
`${BOSSZHIBIN_CACHE_DIR:-~/.codex/bosszhibin_cache}/evolution_history.json`

**本次记录包含**：
- ✅ 执行指标数据
- ✅ 异常检测结果
- ✅ 优化建议清单
- ✅ 历史对比分析

下次执行时将自动加载历史数据进行对比分析。

---

## 📊 执行质量总评

| 维度 | 得分 | 评级 |
|------|------|------|
| 遍历完整度 | {traversal_final_score}/5 | {traversal_grade} |
| 筛选效率 | {screening_final_score}/5 | {screening_grade} |
| 操作稳定性 | {operation_final_score}/5 | {operation_grade} |
| 候选人质量 | {quality_final_score}/5 | {quality_grade} |
| **综合评分** | **{overall_score}/5** | **{overall_grade}** |

### 总体评价：

{overall_assessment}

---

💡 **本次进化已记录，下次执行时我会更智能！**
