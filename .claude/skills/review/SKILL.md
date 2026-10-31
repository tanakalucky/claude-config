---
name: review
description: タスク変更全体を正確性/安全性・テスト・設計/可読性の3観点でレビューし統合する。報告のみ。
argument-hint: "[比較元(ブランチ/コミット)] [要件の要約]"
disallowed-tools: Write, Edit
---

# review

リンクはこのSKILL.mdの場所を基準に解決し、指定した文書を全文読んでから実行する。読めなければ不足を報告する。

[共通レビュー方針](../../../.ai-config/review/policy.md)を適用する。
`disallowed-tools: Write, Edit`で編集ツールを除外する。shellや外部ツールまで含む完全な読取専用sandboxではない。`allowed-tools`は追加しない。

[レビューの共通手順](../../../.ai-config/review/workflow.md)に従い、対象を確定して統合する。
親のinlineコンテキストで実行する。子agentを直接起動せず、次の3つをSkill呼出で各1回実行して全結果を待つ。各skillは`context: fork` / `background: false`で会話履歴を持たない。

- [review-correctness](../review-correctness/SKILL.md)
- [review-tests](../review-tests/SKILL.md)
- [review-design](../review-design/SKILL.md)
