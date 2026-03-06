1. ゴールと非ゴール
ゴール

馬柱PDF（5レース分）を投入すると、レースごとに

① ScenarioComment

② FinalMarks（LapType付き）

③ BetTable（A/B/C）

④ DevilSpeak（必要時のみ）

⑤ ShortMemo
を生成（テンプレ2.7準拠）。

「勝つ確率」を単発で返すのではなく、世界線（Pace/Shape/Traffic/坂/小回り）別に

WinGate / PlaceGate の構成

飛び方（詰まり/外回し消耗/仕掛けズレ）
を見える形にする。

非ゴール（最初からやらない）

厳密な物理シミュ（連続時間、速度方程式のガチ再現）

半径や座標をミリ単位で正確に再現する幾何

映像解析（動画から自動で隊列抽出）
→ 代わりに 馬柱＋テキスト（回顧/短評/メモ）をLLMで構造化する。

2. 全体アーキテクチャ（モジュール分割）
[UI]
  ├─ PDF投入/レース選択
  ├─ マグネットボード（隊列編集）
  └─ 結果ビュー（世界線/ゲート/買い目）

[Core Pipeline]
  1) PDF Ingest
  2) Parse & Canonicalize（DeepParse）
  3) Feature Calc（v2.7 Calc + 拡張）
  4) Ability Scoring（客観指数 + 部品スコア）
  5) Course Model（コース形質）
  6) Worldline Generator（Pace/Shape/Traffic）
  7) Queue Simulation（離散時系列）
  8) Gate Select + halt_bakken
  9) TicketSet + OutputFormat

[Data]
  ├─ race_pack（バッチ単位）
  ├─ past_runs_db（過去走）
  ├─ course_db（競馬場/距離/形質）
  └─ logs（抽出・推定の根拠）

3. データ設計（テンプレ2.7準拠＋必要最小の拡張）
3.1 RaceInfo（レース単位）

RaceName

Surface_Distance_Course（例：芝2000m 右内）

FieldSize

AM_Water%（なければnull）

InitBias（同日同場の5レースバッチで推定して埋める）

CourseKey（後述：CornerSeverity / LaneChangeDifficulty / StraightOpportunity / UphillTag など）

3.2 HorseData（馬単位）

テンプレ2.7の骨格を維持しつつ、Simに要る部品を明示する。

No, Name

Style（逃/先/差/追）

Last3Runs（最低3走、足りなければ2走でも進める）

TrackRecord（任意）

Training（任意）

WeightDiff（任意）

LapType（A/B/C：DeepParse後に付与）

Scores（能力部品：0-2または連続）

Cruise（巡航効率）

Kick（直線加速/瞬発）

Stamina（消耗耐性）

Turn（器用さ/コーナーロス耐性）

StartSkill（出遅れ/二の脚）

Moveability（外出し/進路変更）

TrafficResist（揉まれ耐性）

Uncertainty（0-1：データ薄い/条件替わりで増える）

NotesEvidence（LLM抽出の根拠文を保持）

3.3 DeepParse用の“走行ログ”テーブル（過去走行単位）

テンプレ2.7のCSV_Fieldをベースに、隊列Simに必要な列を追加した canonical table を持つ。

必須（v2.7）

race_date, distance, track, surface, head_cnt, draw, jockey, wt

time, diff, last3F, pt1, pt2, pt3, finish_rank

追加（推奨）

pos1c, pos2c, pos3c, pos4c

pace_tag（S/M/H：自動推定可）

wide_trip_tag（0/1/2：LLM補正）

braked_tag（0/1/2：LLM補正）

early_move_tag（0/1/2：LLM補正）

4. 入力（PDF）→ データ化（DeepParse）の仕様
4.1 対応PDF

“馬柱/出馬表”系（枠順/斤量/騎手/馬名/性齢/所属/厩舎 などが表になっているもの）

5レース分をまとめて投入可（PDF複数 or 1PDFに複数レースでも可）

4.2 抽出の基本方針（落ちない設計）

第一段：ルール抽出（表の列構造を保つ）

第二段：LLM補助は「列の意味推定」「欠損の補完理由抽出」まで
→ 数字自体をLLMに“確定”させない（誤読対策）

4.3 欠損の扱い（止めない）

欠損は RequestList に積む（テンプレ2.7の運用）

例：MissingLap(No.3,5,11)、FinalTraining(No.2,9) など

欠損があってもシムは走らせる（Uncertaintyを上げる）

5. 能力数値化（テンプレ2.7の思想で“部品化”）

ここが「一般的な予想」と同じに見える部分。でも、Simに入れるために 形を変える。

5.1 v2.7のCalc（必須）

pace_rank = mean(pt1,pt2,pt3)

delta_rank = pace_rank - last3F_rank

rel_last3F = Zscore(last3F)（同条件分布で標準化）

LapType判定 → A/B/C

客観指数 += LapType.Adj

薄残しFlag（A,Bは100円残し）

5.2 標準化（競馬場×芝ダ×距離）

目的：東京芝1600の速さと小倉芝1200の速さを同じ尺度に載せる

最低ライン：

distance_bucket（1200/1400/1600/1800/2000/2200/2400/2600…）

track、surfaceで分布を分けてZ化

5.3 能力部品スコア（Simに入る形）

馬ごとに以下を作る（0-2または連続値）。
計算元は canonical table と標準化値。

Cruise：ペース耐性＋巡航安定（中盤の順位安定、終いに繋がる余力）

Kick：直線で順位を上げる頻度＋上がり質

Stamina：距離延長/タフ条件での崩れにくさ

Turn：小回り/コーナーきつい条件での落ちにくさ（CourseKeyと相互作用）

StartSkill：pos1cの安定（出遅れ癖を拾う）

Moveability：3C→4Cで動いて成功する頻度（外出し/捲り成功）

TrafficResist：内で揉まれて崩れない頻度（内枠や密集での成績）

5.4 LLMでやるべき“補正タグ”（ここだけで良い）

馬柱だけでは「凡走の理由」が分解できないので、LLMは原因タグ化に使う。

WideTrip（外々を回された）

EarlyMove（早仕掛け/ロングスパート）

Braked（前詰まり/不利/進路変更でブレーキ）

PacePressure（楽じゃない逃げ/先行）

CorneringSmooth（コーナーでのロス少）

これらは 能力スコアを直接盛らず、Sim側の

外回し消耗（E減少）

交通事故率（Checked/Blocked）

仕掛けタイミング
に反映する。

6. コースDB設計（形質＝“行動の自由度”として持つ）

ここがあなたの言う「ローカルで負ける」を再現する中核。

6.1 CourseKey（必須3＋任意）

CornerSeverity：コーナー厳しさ（小回り度/急さ）

LaneChangeDifficulty：外に出しづらさ（幅・コーナーでの進路変更難）

StraightOpportunity：直線で挽回できる余地（直線長＋坂）

任意：UphillTag（坂が効く場）、TurnEntryTightness（入口の詰まりやすさ）

6.2 DistanceConfig（最低限これ）

start_to_first_turn_m（スタート→最初のコーナーまで）

home_stretch_m（ホーム直線）

lap_len_m（周回距離）

turn_cost_coeff（コーナー消耗係数）

lane_extra_dist_coeff（外回し距離増係数）

※ 半径を直接持たず、消耗係数で吸収する設計。

7. 世界線（Scenario）生成（テンプレ2.7 / 4-1を拡張）
7.1 生成する世界線の最小セット

PaceScenario：Slow / Standard / Fast（+確率）

Shape：Compact / String / Split（+確率）

SecondaryPressFlag：あり/なし（+確率）

TrafficMode：内詰まり / 中立 / 外詰まり（同日同場バイアスで更新）

OutsideSweepScenario：成立/不成立（派生）

7.2 ルール（テンプレ2.7のペース規則）

先行馬が多い、距離差小さい、などでFast寄りに強制する規則（v2.7のCSI思想に合わせる）

坂（UphillTag）×Fastは「前が落ちる確率」を上げる

8. 隊列シミュレーション設計（疑似物理・離散時系列）
8.1 時系列ステップ（固定）

T0: Start

T1: 1C入口

T2: 向正面

T3: 3C入口

T4: 4C出口（直線入口）

T5: ゴール前

この6点で十分「外回し＝消耗→キレ減」を表現できる。

8.2 馬の状態（Sim内）

各馬に状態を持つ（世界線ごとに更新）：

pos(t)：前後位置（順位相当）

lane(t)：内外（0=内、1=外）

E(t)：残パワー（スタミナ＋瞬発の統合）

route_state：ok / wait / checked / blocked（交通イベント）

8.3 更新則（最小で効く形）
(A) コーナー消耗（外回しの代償）

外側ほど距離増：Δd ∝ lane_extra_dist_coeff * lane

コーナーは速度上限が落ちる：v_cap_corner（係数）

消耗：E -= turn_cost_coeff * (1 + α*lane) + pace_cost

(B) 交通イベント（詰まりで加速開始できない）

TrafficRisk は以下の関数で決める：
Draw, Style, Moveability, TrafficResist, Shape, TrafficMode, LaneChangeDifficulty

Blocked/Checked/Wait を確率抽選し、該当馬は Eとposに罰を与える
（最重要：直線入口でのBlockedは勝率を大きく削る）

(C) 仕掛け（3C→4Cの動き）

動きたい馬（LongRunner/勝ち筋の馬）は lane を外へ移そうとする

ただし LaneChangeDifficulty が高いコースでは失敗率が増える
→ これが「ローカルで外に出せず負ける」を作る

8.4 出力（世界線ごとの同時確率）

各世界線で

Top1（勝ち馬）

Top3（馬券内組）

飛び内訳（事故/消耗/ペース不適）
をカウントし、最後に加重平均して

P(win)（単勝確率）

P(in3)（複勝確率）

P(traffic_fail)（詰まり負け率）

P(wide_cost_fail)（外回し消耗負け率）

相手分布（勝つ時の2-3着が前寄りか差し寄りか）

を返す。

9. Gate確定と halt_bakken（テンプレ2.7の“停止思想”）
9.1 WinGate（勝ち切り候補）

P(win)上位2〜3頭を基本

ただし

P(traffic_fail)が極端に高い

世界線により勝者が入れ替わりすぎる
場合はWinGateを広げる or 見送り寄り

9.2 PlaceGate（連下候補）

P(in3)上位＋LapType(A/B)＋薄残しFlagで拾う

勝たないが残る馬（B FrontGritなど）がここに乗る

9.3 halt_bakken()

WinGateが絞れない（上位が団子）

世界線が割れすぎ（勝者がばらける）

交通事故率が高すぎて運ゲー
→ 「買わない」を明示的に出力する（2.7のストッパー運用）

10. UI設計（マグネットボード＋時系列可視化）
10.1 画面構成

左：マグネットボード（コース上のセクション帯つき）

右上：世界線スイッチ（Pace/Shape/TrafficMode/坂）

右中：馬ごとのゲージ

E(t)（残パワー）

TrafficRisk

lane_cost

右下：結果（WinGate/PlaceGate、買い目案、飛び内訳）

10.2 操作

馬アイコンをドラッグして

4角時点の lane や pos の“初期配置”を修正できる

「この馬は外へ出す/内で溜める/捲る/我慢」トグル（意志）を指定

変更するとSimを即再計算し、勝率・飛び率が動く
→ “位置取りミスで1番人気級が飛ぶ”が視覚的に分かる

11. 5レースバッチ運用（同日同場の共有）

5レースをまとめる意味はここ：

InitBias（内前/外差）をバッチ内で推定して更新

TrafficMode（内が詰まる/外が開く）を更新

turn_cost_coeff の当日補正（馬場の重さでコーナー消耗が増える等）

つまり、Simの“前提世界線”が同場内で自己整合する。

12. 出力（テンプレ2.7 / 7.OutputFormat完全準拠）

各レースごとに

① ScenarioComment

主要世界線（Fast+坂→前崩れ、内詰まり等）

勝ち筋（外に出せる差し or 前残り）

② FinalMarks（LapType付き）

印＋LapType(A/B/C)

WinGate/PlaceGateの明示

“飛び条件”タグ（TrafficHigh、WideCostHigh）

③ BetTable

A保険/B本線/C穴（点数・1点額・合計）

薄残し（100円）ルールを自動適用

④ DevilSpeak（必要時のみ）

世界線が割れてる時、または◎の飛び条件が強い時だけ
（詰まり、外回し消耗、早仕掛け、スロー前残り等）

⑤ ShortMemo

勝ち筋1行＋負け筋1行

13. ログと説明責任（“納得できる予想”にする仕掛け）

LLMが付けたタグは 根拠文付きで保存（NotesEvidence）

どの要因が P(win) を削ったかを “内訳” で出す
（例：TrafficFail 12% / WideCostFail 8% / PaceMismatch 5%）

これが無いと、ただのブラックボックス指数になる。