#include "helper.hpp"

#include <algorithm>
#include <cstdint>
#include <deque>
#include <vector>

namespace {

using unswbc::Direction;
using unswbc::EdgeType;
using unswbc::Position;

constexpr int BLOCKED_FOREVER = 1 << 28;

constexpr bool DEBUG_LOG = false;
constexpr int TIE_SEED = 0;

constexpr bool USE_VORONOI = false;
constexpr bool VORONOI_ALLIES = true;
constexpr bool AVOID_ALLY_HEADS = false;

constexpr std::uint8_t EDGE_UNKNOWN = 0;
constexpr std::uint8_t EDGE_OPEN = 1;
constexpr std::uint8_t EDGE_KELP = 2;
constexpr std::uint8_t EDGE_PORTAL = 3;

constexpr double WEIGHT_SPACE = 1.5;
constexpr double WEIGHT_TERRITORY = 1.5;
constexpr double UNSEEN_DISCOUNT = 0.5;
constexpr double PENALTY_TIGHT = 400.0;
constexpr double PENALTY_TRAPPED = 5000.0;
constexpr double TARGET_REWARD = 260.0;
constexpr double TARGET_DECAY = 16.0;
constexpr double WEIGHT_PEARL = 1.0;
constexpr double WEIGHT_SOON = 0.45;
constexpr double WEIGHT_UNSEEN = 0.20;
constexpr double PENALTY_NO_TAIL = 0.0;
constexpr double PENALTY_ENEMY_HEAD = 450.0;
constexpr double SCORE_PORTAL = -100000.0;
constexpr double SCORE_REJECT = -1e15;

struct Survey {
    int area_seen = 0;
    int area_unseen = 0;
    int own_seen = 0;
    int own_unseen = 0;
    int dist_pearl = -1;
    int dist_soon = -1;
    int dist_unseen = -1;
    bool reaches_tail = false;
};

class Bot {
  public:
    Bot(unswbc::Controller& controller, unswbc::Game& game) : ct(controller), gm(game) {
        auto const [map_width, map_height] = game.get_map_size();
        width = map_width;
        height = map_height;
        cells = width * height;

        north_edge.assign(cells, EDGE_UNKNOWN);
        west_edge.assign(cells, EDGE_UNKNOWN);
        pearl_here.assign(cells, 0);
        pearl_timer.assign(cells, -2);
        seen_round.assign(cells, -1);
        enter_time.assign(cells, 0);
        rival_dist.assign(cells, 0);
        rival_stamp.assign(cells, 0);
        visit_stamp.assign(cells, 0);
        step_count.assign(cells, 0);
        eaten_count.assign(cells, 0);
        bfs_queue.resize(static_cast<std::size_t>(cells));
    }

    void take_turn() {
        observe();
        ct.make_move(pick_direction());
    }

  private:
    int index_of(Position position) const { return position.y * width + position.x; }

    static Direction dir_of(Direction::Value value) { return Direction(value); }

    std::uint8_t edge_at(Position position, Direction direction) const {
        switch (direction.value) {
        case Direction::NORTH: return north_edge[index_of(position)];
        case Direction::SOUTH: return north_edge[index_of(position.add_dir(dir_of(Direction::SOUTH)))];
        case Direction::WEST:  return west_edge[index_of(position)];
        default:               return west_edge[index_of(position.add_dir(dir_of(Direction::EAST)))];
        }
    }

    void remember_edge(Position position, Direction direction, unswbc::Edge const& edge) {
        std::uint8_t const code = edge.get_edge_type() == EdgeType::KELP     ? EDGE_KELP
                                : edge.get_edge_type() == EdgeType::PORTAL ? EDGE_PORTAL
                                                                          : EDGE_OPEN;
        switch (direction.value) {
        case Direction::NORTH: north_edge[index_of(position)] = code; break;
        case Direction::SOUTH: north_edge[index_of(position.add_dir(dir_of(Direction::SOUTH)))] = code; break;
        case Direction::WEST:  west_edge[index_of(position)] = code; break;
        default:               west_edge[index_of(position.add_dir(dir_of(Direction::EAST)))] = code; break;
        }
    }

    int torus_gap(int a, int b, int size) const {
        int const raw = std::abs(a - b);
        return std::min(raw, size - raw);
    }

    bool is_neighbour(Position a, Position b) const {
        int const dx = torus_gap(a.x, b.x, width);
        int const dy = torus_gap(a.y, b.y, height);
        return dx + dy == 1;
    }

    void observe() {
        round = gm.get_round_num();
        length = ct.get_length();
        head = ct.get_position();

        trail.push_front(head);
        while (static_cast<int>(trail.size()) > length) {
            trail.pop_back();
        }

        for (int const touched : dirty) {
            enter_time[touched] = 0;
        }
        dirty.clear();
        other_heads.clear();
        enemy_heads.clear();
        own_parts.clear();

        for (auto const& tile : ct.get_tiles()) {
            Position const position = tile.get_position();
            int const index = index_of(position);

            pearl_here[index] = tile.has_pearl() ? 1 : 0;
            pearl_timer[index] = tile.get_pearl_time();
            seen_round[index] = round;

            for (Direction const direction : Direction::get_direction_list()) {
                remember_edge(position, direction, tile.get_edge(direction));
            }

            auto const* part = tile.get_dragon();
            if (!part) {
                continue;
            }
            if (part->get_id() != ct.get_id()) {
                mark_blocked(index);
            } else {
                own_parts.push_back(index);
            }
            if (part->is_head() && part->get_id() != ct.get_id()) {
                other_heads.push_back(position);
                if (part->get_team() != ct.get_team()) {
                    enemy_heads.push_back(position);
                }
            }
        }

        for (std::size_t offset = 0; offset < trail.size(); offset++) {
            int const index = index_of(trail[offset]);
            int const free_at = length - static_cast<int>(offset) + 1;
            if (enter_time[index] == 0) {
                dirty.push_back(index);
            }
            enter_time[index] = std::max(enter_time[index], free_at);
        }

        for (int const index : own_parts) {
            if (enter_time[index] == 0) {
                mark_blocked(index);
            }
        }

        tail_index = static_cast<int>(trail.size()) == length ? index_of(trail.back()) : -1;
        map_rivals();
    }

    void map_rivals() {
        rival_mark++;
        int queue_head = 0;
        int queue_tail = 0;

        if (!USE_VORONOI) {
            return;
        }

        for (Position const& rival : VORONOI_ALLIES ? other_heads : enemy_heads) {
            int const index = index_of(rival);
            if (rival_stamp[index] == rival_mark) {
                continue;
            }
            rival_stamp[index] = rival_mark;
            rival_dist[index] = 0;
            bfs_queue[queue_tail++] = rival;
        }

        while (queue_head < queue_tail) {
            Position const position = bfs_queue[queue_head++];
            int const index = index_of(position);
            int const steps = rival_dist[index];

            for (Direction const direction : Direction::get_direction_list()) {
                std::uint8_t const edge = edge_at(position, direction);
                if (edge == EDGE_KELP || edge == EDGE_PORTAL) {
                    continue;
                }
                Position const next = position.add_dir(direction);
                int const next_index = index_of(next);
                if (rival_stamp[next_index] == rival_mark || enter_time[next_index] != 0) {
                    continue;
                }
                rival_stamp[next_index] = rival_mark;
                rival_dist[next_index] = steps + 1;
                bfs_queue[queue_tail++] = next;
            }
        }
    }

    int rival_steps(int index) const {
        return rival_stamp[index] == rival_mark ? rival_dist[index] : BLOCKED_FOREVER;
    }

    void mark_blocked(int index) {
        if (enter_time[index] == 0) {
            dirty.push_back(index);
        }
        enter_time[index] = BLOCKED_FOREVER;
    }

    Survey survey_from(Position start) {
        Survey result;
        visit_mark++;

        int queue_head = 0;
        int queue_tail = 0;

        int const start_index = index_of(start);
        visit_stamp[start_index] = visit_mark;
        step_count[start_index] = 1;
        eaten_count[start_index] = pearl_here[start_index];
        bfs_queue[queue_tail++] = start;

        while (queue_head < queue_tail) {
            Position const position = bfs_queue[queue_head++];
            int const index = index_of(position);
            int const steps = step_count[index];
            int const eaten = eaten_count[index];

            bool const mine_first = steps < rival_steps(index);
            if (seen_round[index] < 0) {
                result.area_unseen++;
                result.own_unseen += mine_first ? 1 : 0;
            } else {
                result.area_seen++;
                result.own_seen += mine_first ? 1 : 0;
            }
            if (index == tail_index) {
                result.reaches_tail = true;
            }
            if (mine_first && result.dist_pearl < 0 && pearl_here[index]) {
                result.dist_pearl = steps;
            }
            if (mine_first && result.dist_soon < 0 && seen_round[index] >= 0 && pearl_timer[index] >= 0) {
                int const spawns_in = pearl_timer[index] - (round - seen_round[index]);
                if (spawns_in <= steps + 1) {
                    result.dist_soon = steps;
                }
            }
            if (result.dist_unseen < 0 && seen_round[index] < 0) {
                result.dist_unseen = steps;
            }

            for (Direction const direction : Direction::get_direction_list()) {
                std::uint8_t const edge = edge_at(position, direction);
                if (edge == EDGE_KELP || edge == EDGE_PORTAL) {
                    continue;
                }
                Position const next = position.add_dir(direction);
                int const next_index = index_of(next);
                if (visit_stamp[next_index] == visit_mark) {
                    continue;
                }
                int const free_at = enter_time[next_index];
                if (free_at >= BLOCKED_FOREVER || steps + 1 - eaten < free_at) {
                    continue;
                }
                visit_stamp[next_index] = visit_mark;
                step_count[next_index] = steps + 1;
                eaten_count[next_index] = eaten + pearl_here[next_index];
                bfs_queue[queue_tail++] = next;
            }
        }
        return result;
    }

    double target_bonus(int distance, double weight) const {
        if (distance < 0) {
            return 0.0;
        }
        return std::max(0.0, weight * (TARGET_REWARD - TARGET_DECAY * distance));
    }

    bool is_enemy_head(Position position) const {
        for (Position const& enemy : enemy_heads) {
            if (enemy == position) {
                return true;
            }
        }
        return false;
    }

    double score_step(Position destination) {
        Survey const survey = survey_from(destination);

        double const room = survey.area_seen + UNSEEN_DISCOUNT * survey.area_unseen;
        double const territory = survey.own_seen + UNSEEN_DISCOUNT * survey.own_unseen;
        double score = WEIGHT_SPACE * room + WEIGHT_TERRITORY * territory;

        double const room_wanted = 3.0 * length + 8.0;
        if (room < room_wanted) {
            score -= PENALTY_TIGHT * (room_wanted - room);
        }
        if (room < length + 2.0) {
            score -= PENALTY_TRAPPED * (length + 2.0 - room);
        }

        if (tail_index >= 0 && !survey.reaches_tail) {
            score -= PENALTY_NO_TAIL;
        }

        score += std::max({target_bonus(survey.dist_pearl, WEIGHT_PEARL),
                           target_bonus(survey.dist_soon, WEIGHT_SOON),
                           target_bonus(survey.dist_unseen, WEIGHT_UNSEEN)});

        for (Position const& rival : AVOID_ALLY_HEADS ? other_heads : enemy_heads) {
            if (is_neighbour(destination, rival)) {
                score -= PENALTY_ENEMY_HEAD;
            }
        }
        return score;
    }

    Direction pick_direction() {
        Direction best = dir_of(Direction::NORTH);
        double best_score = SCORE_REJECT * 2.0;
        int tie_breaker = 0;

        for (Direction const direction : Direction::get_direction_list()) {
            std::uint8_t const edge = edge_at(head, direction);
            double score = SCORE_REJECT;

            if (edge == EDGE_PORTAL) {
                score = SCORE_PORTAL;
            } else if (edge != EDGE_KELP) {
                Position const destination = head.add_dir(direction);
                if (enter_time[index_of(destination)] <= 1) {
                    score = score_step(destination);
                } else if (is_enemy_head(destination)) {
                    score = SCORE_REJECT * 0.5;
                }
            }

            score += 0.25 * ((TIE_SEED * 101 + ct.get_id() * 31 + round * 17 + tie_breaker * 7) % 5);
            tie_breaker++;

            if (DEBUG_LOG) {
                ct.output_log("r", round, "len", length, "trail", static_cast<int>(trail.size()), "dir",
                              direction, "edge", static_cast<int>(edge), "enter",
                              enter_time[index_of(head.add_dir(direction))], "score", score);
            }

            if (score > best_score) {
                best_score = score;
                best = direction;
            }
        }
        return best;
    }

    unswbc::Controller& ct;
    unswbc::Game& gm;

    int width = 0;
    int height = 0;
    int cells = 0;
    int round = 0;
    int length = unswbc::Constants::INITIAL_LENGTH;
    Position head{};

    std::vector<std::uint8_t> north_edge;
    std::vector<std::uint8_t> west_edge;
    std::vector<std::uint8_t> pearl_here;
    std::vector<int> pearl_timer;
    std::vector<int> seen_round;

    std::vector<int> enter_time;
    std::vector<int> dirty;
    std::vector<Position> other_heads;
    std::vector<Position> enemy_heads;
    std::vector<int> own_parts;
    std::deque<Position> trail;
    int tail_index = -1;

    std::vector<int> rival_dist;
    std::vector<int> rival_stamp;
    int rival_mark = 0;

    std::vector<int> visit_stamp;
    std::vector<int> step_count;
    std::vector<int> eaten_count;
    std::vector<Position> bfs_queue;
    int visit_mark = 0;
};

}

int main() {
    auto [controller, game] = unswbc::init();
    Bot bot(controller, game);

    while (unswbc::update(controller, game)) {
        try {
            bot.take_turn();
        } catch (...) {
            controller.make_move(Direction(Direction::NORTH));
        }
        unswbc::end_turn();
    }
}
