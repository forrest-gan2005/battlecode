循环从看板取出想法卡和任务卡，实现、检查，再把决策交回给我们。

卡片统一显示卡号加短名，例如 `#27 passage`。
短名保存在卡片的 `name:<slug>` 标签中。
候选 PR 标题以卡片引用开头：`Candidate #27 passage`。
PR 编号只出现在标为 `PR` 的链接内部；始终跟随卡号。
任务卡优先（最早的先），人类作者轮流（Zhe、QWQ、준싱）；每启动 3 张人类卡后给 AI 一次机会，没有人类就绪卡时也可处理 AI。
每张卡片用一个 GitHub 状态标签说明下一步，重启后也能继续。
人来回答问题、确认行为是否符合预期，并批准发布。
循环不会自行上传，也不会请求排位赛。
由 준싱 于 2026-10-04 提出，有问题直接在 Discord 说。

## AI 卡片自行决策

只有 `by:ai` 想法卡在结论发布后自动决策，已有 tested 卡也在下次轮询处理；人的卡仍由作者决策。
`verdict.json` 和隐藏结果标记保存相同／总配对数、每组净胜场、mechanism_shown 和 target_seen；相同指记录的结果字段一致，并非未保留的回放事件一致。
≥95% 配对相同或目标行为从未出现时，带结论证据自动修改一次；再次如此则关闭为 inconclusive。
留出组或合并未见组净胜 ≤−9 则关闭为 rejected；留出组 ≥+9、机制已展示且旧图 ≥−9 则进入通常的候选 PR，合并仍需一位队员 OK。
其他情况留在 tested，并注明 "coin flip locally; a 30:30 online pair test would settle it (tools/smoke.py pair)"；meowbot 照常提醒，循环不自行启动线上测试。
每次决策只发一条简短原因与下一步；自动修改次数在重启后保留。

## 循环如何运行

卡片是用 Idea 模板创建的 GitHub issue，包含主张、证据、领域、预期变化，以及什么结果能证伪。toggle 是改动的开关；新开关默认关闭。

`main` 是共用发布分支。基准是当前已发布的 bot，候选是拟替换它的版本。commit ID 标识一个确定的代码版本。A/B 比较候选与基准；smoke 是可选的简短线上行为检查。

不按定时波次运行。runner 脚本每隔几分钟轮询 GitHub，不消耗 AI tokens；只有卡片进入需要 AI 的状态时才调用 AI，调用次数不限。

| 工作 | AI 档位 |
|---|---|
| 澄清问题、实现计划与代码、结论草稿、从天梯对局提出假设 | Opus 5.5 high |
| 简单排版、接线、摘要 | 轻量模型 |

天梯指线上比赛及其对局记录。我们的天梯对局每产生一批新记录，循环就据此创建想法卡片，标记 `by:ai`。

| 选取顺序 | 卡片 |
|---|---|
| 1 | `type:task`：必须保持行为一致的任务 |
| 2 | 人类作者轮流：最近最少被服务的先（从未服务者优先），同作者最早的卡先 |
| 3 | `by:ai`：无人类卡就绪时，以及每 3 张人类卡之后 |

同作者先取最早就绪的卡片。Zhe 仍必须先澄清，再确认回放。等待某个人回复时，可以继续处理其他卡片。

## 任务卡（Task cards）

`[Task]` 卡使用 `type:task` 和 `status:untested`，填写改什么、为什么、如何检查完成，以及提议人。
安全、重构、CPU 节省和工具改动只有不改变行为才是任务；任何行为变化（包括修复 bug）都必须用想法卡。
任务属于同一个循环和单分支流程：`card/N → candidate → main`，作者决策和批准规则相同。
任务走 `ready → building`；只有不明确时才提问，Zhe 的任务也一样；跳过 needs-look 和结果 A/B。
AI 按实际发布配置实现任务，并运行卡片指定的检查（单元测试、脚本或断言）。
runner 独立检查旧 10 张地图 × 2 个种子、双方起始侧的回放，与当前基准（最新 main 发布版／上一版本）完全一致，并要求任务专属检查通过。
通过后先写三行白话摘要，再发 `[check]`，设为 `tested`；作者选择 candidate、rejected 或 inconclusive。
一致性失败退回 `ready`，注明 “this changes play; make it an idea card or fix it”；其他检查失败也带证据退回 ready。
任务先；人类中最近最少被服务的作者先（从未服务者优先），同作者最早的卡先；每 3 张人类卡后给 AI 一次机会。`ready → building/needs-info` 时记录到循环输出目录的 `fair.json`（`~/meow-loop-out`），AI 和对局批次锁也按此顺序排队。AI 的机会只有一次：任何 AI 卡拿到锁（任意步骤）即用掉；没有 AI 卡能用时，同一轮里人类卡照常拿锁。Zhe 的提问和回放确认不变。

## 每张卡片只有一个状态

每张卡片必须且只能有一个 `status:*` 标签，作为阶段的唯一依据。每次流转都替换旧状态，不能叠加。作者标签（`by:*`）和领域标签（`area:*`）只描述卡片，不表示状态。

runner 仅凭标签恢复下一步，不依赖私有队列或记忆中的计时器。问题、回答、基准和候选 commit ID、批次进度、回放链接、批准记录都保存在卡片或关联 PR 上。PR（pull request）是供审查和合并的代码改动提案。

| 状态 | 谁来行动 | 完成条件 / 下一状态 |
|---|---|---|
| `status:untested` | 人 | 新卡片等待同意运行；同意后转 `status:ready`。 |
| `status:ready` | Runner | 按优先级选取；任务直接进入 building；Zhe 的想法卡片转 `status:needs-info`，其他卡片不清楚时也转那里，否则转 `status:building`。 |
| `status:needs-info` | AI，然后作者 | AI 提出“如果……会怎样”的边界情况问题，通过 meowbot @作者。作者在卡片或 Discord 回答；Discord 回答须记回卡片，然后开始实现。无超时。 |
| `status:building` | AI | 任务按上述检查直接进入 tested；想法实现默认关闭的开关。构建通过，关闭开关时在旧 10 张地图上与当前基准的回放完全一致。通过后转 `status:needs-look`；失败则转回 `status:ready`，说明待修问题。 |
| `status:needs-look` | AI，然后作者 | 小规模运行确认预期行为出现，用 `tools/smoke_pick.py` 挑几份回放。Zhe 看 2–3 份并确认“这就是我的意思”；否则回 `status:building` 修改。其他作者自动通过此步。随后转 `status:testing`。 |
| `status:testing` | Runner 和 AI | 本地 A/B 检查对局结果，每次跑一批；发布结果后转 `status:tested`。 |
| `status:tested` | 作者 | 结果已就绪，不代表接受。作者选择候选（可请求 smoke）、拒绝或证据不足。AI 可将自己的想法推进为候选。 |
| `status:candidate` | AI 准备；人批准 | 创建候选 PR，meowbot 发批准按钮。收到所需 OK 并通过发布检查后，合并到 main，提交该确切合并 commit；请求了 smoke 则转 `status:smoke`，否则转 `status:kept`。 |
| `status:smoke` | 人或批准操作启动；领域负责人决策 | 可选线上行为检查。领域负责人加另一人的 OK 决定保留或回滚；最终为 kept、rejected 或 inconclusive，并记录回滚。 |
| `status:kept` | 无待办 | 已接受并发布；终态。 |
| `status:rejected` | 无待办 | 放弃并说明原因；终态。 |
| `status:inconclusive` | 无待办 | 证据不足以定论，说明缺什么；终态。 |

回放完全一致指游戏动作和事件相同，不只是赢家相同。旧 10 张地图是现有回归测试集，用于检查原有行为是否仍正常。

## 旧标签如何映射

能沿用的名称就沿用。下表依据仓库中的 workflow、模板和 `work/board.py`，并非从 GitHub 获取的标签清单。

| 现有标签 | 在此循环中的含义 |
|---|---|
| `status:untested` | 保留：尚未获准进入队列的新卡片。 |
| `loop:ready` | 替换为 `status:ready`，删除旧标签。 |
| `status:in-progress`, `loop:running` | 检查进度后替换为实际当前状态，删除旧标签。 |
| `status:tested` | 沿用为“结果就绪，作者决策”，不能表示保留。迁移前先检查旧卡片。 |
| `status:rejected`, `status:inconclusive` | 沿用为终态；`board.py` 已支持 `inconclusive`。 |
| `area:*`, `by:*`, `wf:*` | 仅作描述；`wf:*` 表示旧 workflow 分组，不表示当前状态。 |

需要新增：`status:ready`、`status:needs-info`、`status:building`、`status:needs-look`、`status:testing`、`status:candidate`、`status:smoke`、`status:kept`。也要确保 `status:inconclusive` 存在。保留作者标签 `by:zhe`、`by:junsing`、`by:qwq`、`by:ai`。

## 本地测试回答什么

A/B 将打开新开关的候选与当前 main 发布版比较。配对对局使用相同地图和随机种子（用于复现随机初始条件的数字），并交换起始侧，避免幸运开局左右结果。

测试使用留出地图（未用于设计或调参）、转置副本（交换行列）及旧 10 张地图。每次跑一批：先在小规模机制检查中确认预期行为，再用 A/B 检查对局结果。

测试始终以当前 main 发布版为基准，记录确切 commit。新版本发布时，在仍运行的测试评论中标注“old base”；这是结果说明，不是第二个状态标签。排队中的测试改用新基准。发布前，旧基准证据必须针对当前 main 重测。

候选包含两个或更多新开关时，发布前须做一次简短组合检查：全部新开关关闭时，旧地图回放必须完全一致；再打开拟发布的组合跑简短 A/B。分别有效不代表组合有效。

## 每份结果都解释原因

每条结果评论都以以下三行白话摘要开头，小规模运行和 smoke 也一样。`[test]`、`[check]` 等机器标签放在其后。

```text
What we tried: <用日常语言描述改动>.
Did it work: <yes / no / unclear，以及主要原因>.
Who decides now: <谁需要做什么>.
```

想法卡的胜负数据旁必须有“为什么”表，尽量同时给出基准与候选值。未测量的项目明确注明。地图家族指布局相似的一组地图，各家族分开列。

| 为什么 | 基准 | 候选 | 能说明什么 |
|---|---|---|---|
| 结束时我方最长 vs 对方最长 | 双方长度与差值 | 双方长度与差值 | 决定胜负的长度，相对对手是否改善？ |
| 总长度 | 双方 | 双方 | 其余增长去了哪里？ |
| 按地图家族分组的结果 | 各家族场数、胜场、长度 | 各家族场数、胜场、长度 | 提升是否广泛，还是掩盖了某类地图的退步？ |

胜负由最长的龙决定。10-03 的一次改动让我方最长变长，但对方增长更多；只说“我们长得更多”会误导。

摘要和表格下列出开关、基准/候选 commit、地图、种子、批次大小、按起始侧分组的结果、不确定性，以及能展示所声称行为的回放链接。AI 起草结论，指定的人决策。

## 批准与发布

| 想法来源 | meowbot 卡片所需 OK |
|---|---|
| 人的想法 | 作者加另一位队员 |
| AI 想法 | 任意一位队员的 OK；AI 推进候选视为作者的 OK |

批准只适用于该 PR 的确切修订；head commit 改变就重置批准。批准操作将候选 PR 合并进 `main`，提交该确切合并 commit。记录合并 commit、submission ID 和之前启用的 submission，以便回滚；每次 submission 都打 tag。

循环准备候选，但不自行上传。只有批准按钮或人能发起上传，smoke 上传也一样。两条路径都受冻结规则约束。

## 难分胜负的结果与可选 smoke 检查

“Inside noise” 指本地 A/B 差异太小，无法可靠区分于随机波动。作者可请求 smoke，即简短的线上行为检查。候选批准时须保留此请求，或由人明确发起上传。

上传候选后，对 DEV 队 `dev_test_1`（ID **545**）打约 60 场非排位赛。DEV 对局有独立的 **60 games/hour** 配额。与**当前基准（最新 main 发布版），每次发布后更新**比较。看选定回放中的行为，不以胜场数判断。领域负责人加另一位队员的 OK 决定保留或回滚。

下列工具位于旁边的 `unsw-swarm` 仓库，命令从那里运行。`BOT_DIR` 是所选 bot 的 `bot.toml` 所在目录；`CANDIDATE` 是保存的 smoke 名称；`BASE` 是当前 main 发布版的基准名称。带 `--confirm` 的命令会执行真实操作，必须走上述人/批准路径。

| 操作 | 命令 |
|---|---|
| 当前基准启用时记录基准 | `python3 tools/smoke.py baseline --name BASE --opp 545 --games 60 --confirm` |
| 预览候选上传和对局 | `python3 tools/smoke.py plan BOT_DIR --name CANDIDATE --opp 545 --games 60 --baseline BASE` |
| 上传并运行已授权的 smoke | `python3 tools/smoke.py start BOT_DIR --name CANDIDATE --opp 545 --games 60 --baseline BASE --confirm` |
| 收集结果和精选回放 | `python3 tools/smoke.py report CANDIDATE` |
| 一条命令回滚 | `python3 tools/smoke.py rollback CANDIDATE --confirm` |

回滚会重新启用保存的上一份 submission。记录基准也消耗 DEV 配额，不能假定基准和候选都能在一小时内跑完。当前 smoke 工具在保存的基准与候选不兼容时不提供比较，包括回滚目标不是所保存的当前基准的情况。报告此限制，不能把缺失的比较当作证据。main 更新后须更新基准；smoke 不能替代以当前 main 为基准的本地检查。

## 冻结与硬规则

| 时间（KST） | 规则 |
|---|---|
| 从 **2026-10-08 20:00** 起 | 禁止新 submission，包括 smoke 上传；只允许回滚到之前的 submission。 |
| **2026-10-09 15:00** | 资格赛提交截止。 |

禁止针对单张地图硬编码或针对固定地图集调参：资格赛使用未见地图。行为不能依赖地图朝向。

重构（不打算改变行为的代码整理）须在旧 10 张地图上保持回放完全一致。实际修复在打开开关时可以改变行为，但不能在这些地图上明显退步；列出退步幅度供作者判断。关闭开关时仍须通过一致性检查。

循环从不请求排位赛。只有需要人行动时才在 Discord 提醒：回答问题、看回放、批准或对结果做决定。日常进度留在看板。meowbot 的 `/loop` 和 `/board` 显示卡片状态。

## 还有哪些接线未完成

这是已确认的循环规范，不代表所有工具已实现。`work/board.py` 仍用 `loop:ready` 排队、`loop:running` 认领，把标签放在摘要前，并把本地 HEAD 记作基准。它需要实现上述状态流转、优先级、摘要顺序和实际发布基准。Issue 模板的 `status:untested` 仍有效。

meowbot 已记录按作者区分的 OK 规则和真实合并，但 `UPLOAD_ENABLED = False` 表示当前上传是模拟的。接线时，状态显示和仅在人需行动时提醒的规则必须遵循本规范。`tools/smoke_pick.py` 当前需要已下载的线上回放；本地机制检查需提供兼容输入或适配器。不能因接线缺失而自动通过 Zhe 的看回放步骤。
