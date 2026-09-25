// 陪练 bot：照实战对手的回放行为写的蜂群。
// 见 4 就分裂、贪心吃视野内最近的珍珠、敌头在冲刺射程内就自杀冲刺、没有记忆也不用声呐。
// 只用来做本地 A/B，不是要提交的 bot。
#include "helper.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace {

using unswbc::Direction;
using unswbc::Position;

constexpr int RAM_MAX_STEPS = 5;          // 对手冲刺撞头绝大多数在 2 到 5 步
constexpr int SPLIT_LAST_ROUND = 480;
constexpr int VISION = unswbc::Constants::VISION_SIZE;

struct Local {
    // 7x7 视野的局部索引：(lx, ly) in 0..6, 头在 (3,3)
    std::array<Position, VISION * VISION> pos{};
    std::array<bool, VISION * VISION> free{};        // 没有任何龙身、可以站
    std::array<int, VISION * VISION> enemy_head{};   // >0: 敌头的可见节数（同 id 的部件数）
    std::array<bool, VISION * VISION> pearl{};
};

int lidx(int lx, int ly) { return ly * VISION + lx; }

Direction dir_of(Direction::Value v) { return Direction(v); }

}  // namespace

int main() {
    auto [ct, game] = unswbc::init();
    std::uint32_t rng = 12345u + static_cast<std::uint32_t>(ct.get_id()) * 2654435761u;
    auto next_rand = [&rng]() { rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; return rng; };

    while (unswbc::update(ct, game)) {
        int const round = game.get_round_num();
        int const length = ct.get_length();
        Position const head = ct.get_position();
        auto const& tiles = ct.get_tiles();

        // 每个可见 id 的节数
        std::vector<std::pair<int, int>> parts;
        for (auto const& tile : tiles) {
            auto const* part = tile.get_dragon();
            if (!part) continue;
            bool found = false;
            for (auto& p : parts) if (p.first == part->get_id()) { p.second++; found = true; break; }
            if (!found) parts.push_back({part->get_id(), 1});
        }
        auto parts_of = [&](int id) { for (auto const& p : parts) if (p.first == id) return p.second; return 0; };

        Local L;
        auto wrap = [](int v, int n) { return (v % n + n) % n; };
        for (int ly = 0; ly < VISION; ly++) {
            for (int lx = 0; lx < VISION; lx++) {
                Position const p(wrap(head.x + lx - 3, game.width), wrap(head.y + ly - 3, game.height));
                int const k = lidx(lx, ly);
                L.pos[k] = p;
                auto const* tile = ct.get_tile(p);
                auto const* part = tile ? tile->get_dragon() : nullptr;
                L.free[k] = tile && !part;
                L.pearl[k] = tile && tile->has_pearl();
                L.enemy_head[k] = (part && part->is_head() && part->get_team().value != ct.get_team().value)
                                      ? parts_of(part->get_id()) : 0;
            }
        }
        // 局部邻接：海草和传送门边都不走（陪练不认传送门）
        auto neighbour = [&](int k, Direction d) -> int {
            int lx = k % VISION, ly = k / VISION;
            auto const* tile = ct.get_tile(L.pos[k]);
            if (!tile) return -1;
            auto const& edge = tile->get_edge(d);
            if (!edge.is_passable() || edge.is_portal()) return -1;
            auto const [dx, dy] = d.get_offset();
            lx += dx; ly += dy;
            if (lx < 0 || ly < 0 || lx >= VISION || ly >= VISION) return -1;
            return lidx(lx, ly);
        };
        auto const dirs = Direction::get_direction_list();
        int const start = lidx(3, 3);

        // BFS：从头出发只走空格；记录父指针，用来找珍珠路径和冲刺路径
        std::array<int, VISION * VISION> dist{}; dist.fill(-1);
        std::array<int, VISION * VISION> parent{}; parent.fill(-1);
        std::array<char, VISION * VISION> via{}; via.fill('N');
        std::vector<int> queue; queue.push_back(start); dist[start] = 0;
        int ram_target = -1;
        for (std::size_t qi = 0; qi < queue.size(); qi++) {
            int const k = queue[qi];
            for (Direction const d : dirs) {
                int const n = neighbour(k, d);
                if (n < 0 || dist[n] >= 0) continue;
                if (L.enemy_head[n] > 0) {
                    // 敌头：能一路冲到就是候选目标（目标本身不入队）
                    int const steps = dist[k] + 1;
                    bool const at_cap = ct.get_unit_count() >= game.get_unit_limit();
                    bool const worth = at_cap || L.enemy_head[n] >= length - 1;
                    if (steps <= std::min(RAM_MAX_STEPS, length) && worth && ram_target < 0) {
                        ram_target = n; parent[n] = k; via[n] = static_cast<char>(d.value); dist[n] = steps;
                    }
                    continue;
                }
                if (!L.free[n]) continue;
                dist[n] = dist[k] + 1; parent[n] = k; via[n] = static_cast<char>(d.value);
                queue.push_back(n);
            }
        }
        auto path_to = [&](int target) {
            std::string path;
            for (int k = target; k != start; k = parent[k]) path.insert(path.begin(), via[k]);
            return path;
        };

        // 1. 分裂
        if (round <= SPLIT_LAST_ROUND && ct.can_split(2) && length >= 4) {
            ct.do_split(2);
            unswbc::end_turn();
            continue;
        }
        // 2. 自杀冲刺
        if (ram_target >= 0) {
            std::string const path = path_to(ram_target);
            std::vector<Direction> moves;
            for (char c : path) moves.push_back(Direction(c));
            ct.make_moves(moves);
            unswbc::end_turn();
            continue;
        }
        // 3. 最近的珍珠，否则找空间最大的方向
        int best = -1;
        for (int k = 0; k < VISION * VISION; k++) {
            if (L.pearl[k] && dist[k] > 0 && (best < 0 || dist[k] < dist[best])) best = k;
        }
        Direction move = dir_of(Direction::NORTH);
        if (best >= 0) {
            move = Direction(path_to(best)[0]);
        } else {
            // 评估四个方向：从目标格能到的空格数（局部 BFS），加一点随机
            int best_score = -1;
            for (std::size_t di = 0; di < dirs.size(); di++) {
                int const n = neighbour(start, dirs[di]);
                if (n < 0 || !L.free[n]) continue;
                std::array<int, VISION * VISION> seen{}; seen.fill(0);
                std::vector<int> q; q.push_back(n); seen[n] = 1; int area = 0;
                for (std::size_t qi = 0; qi < q.size(); qi++) {
                    area++;
                    for (Direction const d : dirs) {
                        int const m = neighbour(q[qi], d);
                        if (m < 0 || seen[m] || !L.free[m]) continue;
                        seen[m] = 1; q.push_back(m);
                    }
                }
                int score = area * 4 + static_cast<int>(next_rand() % 3);
                if (score > best_score) { best_score = score; move = dirs[di]; }
            }
            if (best_score < 0) {
                // 没路了：挑一个不是友军头的方向死，别把队友也撞死
                for (Direction const d : dirs) {
                    int const n = neighbour(start, d);
                    auto const* tile = n >= 0 ? ct.get_tile(L.pos[n]) : nullptr;
                    auto const* part = tile ? tile->get_dragon() : nullptr;
                    bool const ally_head = part && part->is_head() && part->get_team().value == ct.get_team().value;
                    if (!ally_head) { move = d; break; }
                }
            }
        }
        ct.make_move(move);
        unswbc::end_turn();
    }
}
