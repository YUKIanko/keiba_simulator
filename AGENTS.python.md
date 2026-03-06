# AGENTS.md (Python)

## Rules
- 依存追加は最小。必要なら理由と代替案を書く。
- I/O境界以外のモック過多は禁止。統合テスト/実行で最終確認する。

## Style
- 型ヒントを優先（可能な範囲で）。例外は「境界」でまとめる。
- 早期return、ガード節、純粋関数化を優先。
- CLIは `argparse` か `typer` のどちらかに統一。

## Structure
- `src/` と `tests/` の責務を分ける。
- “設定”は `config.yaml`/`.env` いずれかに寄せ、散らさない。

## Output format
- 方針 → diff → 実行コマンド → 変更点の要約（最大10行）

## Commands (fill)
- Tests: pytest -q
- Lint: ruff check . && ruff format --check .
- Type: mypy .
- Run: python -m <module>

