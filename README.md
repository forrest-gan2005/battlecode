# C-- Battlecode 机器人

## 目录
- `v61/`：当前天梯生效版本（服务器标签 v61）。
- `mybot2/`：开发版。所有新行为都做成 `main.cpp` 顶部的 `constexpr` 开关，默认关闭；`v61` = 开发版 + `work/v60toggles.txt` 的开关 + `POCKET_CAP=48,QUEEN_HOME_CLOSED=true`。
- `work/`：测试与分析脚本、实验日志 `plan.md`。
- `maps/`、`tune_maps/`、`tune_runs/*`：官方图、从回放还原的新图（`tune_runs/newmaps`）、生成的开发集 / 留出集 / 新鲜集。
- `swarm/`：陪练机器人。

## 本地 A/B 测试
```
cd work
python3 -m venv bc123 && bc123/bin/pip install unswbc==1.2.3
export PATH=$PWD/bc123/bin:$PATH NOSANDBOX=1 FAST=1 WORKERS=4
SEED0=3000 python3 ab3.py "$(cat newset.txt),$(cat official.txt)" v61 8 out.json "TAG@mybot2:开关1=值,开关2=值"
python3 paired.py 基线.json 基线标签 out.json
```
`ab3.py` 按开关组合编译变体（`tune_runs/ab2/TAG`），与对手目录对打并输出胜场；`paired.py` 按同地图同种子配对比较。

## 约定
- 机器人代码不写注释，不针对具体地图硬编码。
- 提交前检查 64×64 地图沙箱单回合点数（`unswbc run --sandbox`）不超过约 60M。
- 每次提交到比赛服务器后打对应的 git tag（v61、v62 …）。
