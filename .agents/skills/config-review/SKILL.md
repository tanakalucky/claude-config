---
name: config-review
description: タスク変更全体を正確性/安全性・テスト・設計/可読性の3観点でレビューし統合する。報告のみ。
---

# config-review

リンクはこのSKILL.mdの場所を基準に解決し、指定した文書を全文読んでから実行する。読めなければ不足を報告する。

[共通レビュー方針](../../../.ai-config/review/policy.md)を適用する。
[Codexの実行条件](../../review-runtime.md)を確認して適用する。

[レビューの共通手順](../../../.ai-config/review/workflow.md)に従い、対象を確定して統合する。
次の3つを、独立した子agentに1つずつ渡して実行させ、全結果を待つ。

- [config-review-correctness](../config-review-correctness/SKILL.md)
- [config-review-tests](../config-review-tests/SKILL.md)
- [config-review-design](../config-review-design/SKILL.md)
