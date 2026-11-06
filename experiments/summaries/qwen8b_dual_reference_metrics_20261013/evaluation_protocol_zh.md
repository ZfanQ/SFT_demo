# Qwen3-8B：200篇双参考指标评估

本轮只计算已保存摘要的ROUGE与BERTScore，不生成摘要，不运行GPT质量评审，也不修改作者Abstract、GPT参考或Qwen输出。

按照2026-09-30会议11:33–12:48的讨论，固定同一批200份Qwen候选摘要，分别对比作者原始Abstract与现有GPT参考摘要。每个编号有两组结果，共400组。输入快照、文件哈希及软件配置随结果保存。现有GPT参考版本和队友之后可能生成的新版本需要分开报告。

## 指标口径

- ROUGE-1、ROUGE-2、ROUGE-L：完整文本、英文stemming，报告逐篇F1的算术平均；逐篇CSV同时包含precision和recall。
- BERTScore：roberta-large，第17层，IDF关闭，baseline rescaling关闭，slow tokenizer，CPU；precision/recall/F1均保存，汇总表报告F1。
- 编码器revision：722cf37b1afa9454edce342e7895e588b6ff1d59。具体包版本和BERTScore hash见metric_config.json。
- 两侧只规范空白，不删除作者原始分节标题、注册信息，不压缩原始Abstract，不用参考字数重新生成候选。
- 分数为0–1，按论文等权平均，不拼接200篇当成一篇评分，也不对不同参考的分数取一个混合总分。

## 长度限制

标准BERTScore的RoBERTa tokenizer最多接收512 tokens（含特殊tokens）。所有Qwen输出与GPT参考均在上限内；11份作者Abstract超过上限：049、061、095、130、141、147、153、154、173、190、192。

这11篇的ROUGE仍使用完整原文。BERTScore按库的标准行为截断，并在逐篇CSV以bertscore_reference_truncated和bertscore_status明确标注；表中该分数不代表完整原始Abstract的相似度。token_length_check.json记录截断前长度。

summary.json另给出189篇两套参考均无截断的匹配子集均值。对照两套参考时可同时查看这个共同子集，避免不同覆盖范围造成误解。若以后改用分段或长上下文编码器，应创建新实验版本，不与本次standard512结果混算。

## 文件

服务器目录：/data/SFT_demo/Oct/results/qwen8b_dual_reference_metrics_20261013T112401Z/

- results.md：总体均值及口径说明。
- per_paper.csv / per_paper.jsonl：400组逐篇指标。
- summary.json：总体与匹配子集均值、长度限制、源文件变化检查。
- inputs/、input_manifest.json：冻结的600个输入文件与哈希。
- metric_config.json、score_saved_summaries.py：实际评分配置及脚本。
- run.log、status.json：运行与完成记录。

ROUGE/BERTScore衡量文本重叠或语义相似度，不能单独认证与全文事实一致。本次范围仅为指标评分。
