# AGENTS.md

## Prime directive
- 「動く」だけでなく「読めて保守できる」を必達にする。
- ハック/場当たり/過剰抽象化/ワンライナー芸は禁止。

## Workflow
- 理解 → 設計（5行以内）→ 実装 → テスト → 整形/命名 → ドキュメント更新。
- 確認質問は「矛盾」か「決定不能」な時だけ。進められる部分は進める。

## Output format (every reply)
1) 方針（3〜6行）
2) 変更diff
3) 実行コマンド（実行した/する）
4) リスク/読みにくくなり得る箇所（あれば）

## Code style
- 関数は小さく（目安30行）。ネストは浅く（目安2段）。
- 命名は意味で付ける。`tmp`, `data`, `x` の乱用禁止。
- コメントは "what" より "why" を書く。

## Safety
- 削除系コマンド、依存更新、秘密情報に触れる操作は慎重に。
- 破壊的変更は事前に影響範囲とロールバック手順を書く。

## Commands (fill these)
- Tests: <TEST_CMD>
- Lint: <LINT_CMD>
- Type: <TYPECHECK_CMD>
- Run:  <RUN_CMD>

