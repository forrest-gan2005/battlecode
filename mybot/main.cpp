#include "helper.hpp"

#include <algorithm>
#include <array>
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
constexpr bool DEBUG_SPLIT = false;
constexpr bool DEBUG_STATS = false;

constexpr bool USE_VORONOI = true;
constexpr bool VORONOI_ALLIES = false;
constexpr bool AVOID_ALLY_HEADS = true;
constexpr double CONTESTED_SHARE = 0.5;
constexpr double PENALTY_HEAD_RACE = 450.0;

constexpr int SPLIT_LAST_ROUND = 400;
constexpr int SPLIT_MIN_LENGTH = 4;
constexpr bool SPLIT_IN_HALF = false;
constexpr int SPLIT_SOFT_LIMIT = 60;

constexpr bool USE_FEEDER_SACRIFICE = true;
constexpr bool USE_SONAR_LEADER = true;
constexpr int ENDGAME_ROUND = 400;
constexpr int LEADER_GROW_ROUND = 300;
constexpr bool LEADER_ZONE_EARLY = true;
constexpr int FEEDER_KEEP_UNITS = 3;
constexpr int FEEDER_APPROACH = 15;
constexpr int FEEDER_DROP_MIN = 4;
constexpr int FEEDER_DROP_MAX = 8;
constexpr int FEEDER_KEEP_OFF = 2;
constexpr int FEEDER_THROTTLE = 3;
constexpr int FEEDER_THROTTLE_PERIOD = 5;
constexpr int LEADER_PEARL_RADIUS = 9;
constexpr int SONAR_STALE = 25;
constexpr double FEEDER_REWARD = 3000.0;
constexpr double FEEDER_DECAY = 60.0;
constexpr double LEADER_HEAD_MULT = 2.0;

constexpr bool USE_TRADE_ATTACK = true;
constexpr int TRADE_MAX_LENGTH = 3;
constexpr int TRADE_MIN_UNITS = 8;
constexpr double TRADE_REWARD = 2500.0;
constexpr double TRADE_DECAY = 80.0;

constexpr bool USE_ESCAPE_SPLIT = true;
constexpr int ESCAPE_MIN_LENGTH = 25;
constexpr double ESCAPE_ROOM_MAX = 4.0;
constexpr double ESCAPE_MARGIN = 4.0;

constexpr bool USE_PORTALS = true;
constexpr int PORTAL_NONE = -1;
constexpr int PORTAL_UNKNOWN = -2;
constexpr int PORTAL_SCOUT_MAX_LENGTH = 6;
constexpr double PORTAL_SAFETY_MARGIN = 6.0;

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
constexpr double PENALTY_NO_TAIL = 600.0;
constexpr double PENALTY_ENEMY_HEAD = 450.0;
constexpr double SCORE_PORTAL = -100000.0;
constexpr bool USE_PORTAL_SCOUT = true;
constexpr double WEIGHT_PORTAL_SCOUT = 0.40;
constexpr double SCORE_REJECT = -1e15;

struct Survey {
    int area_seen = 0;
    int area_unseen = 0;
    double own_seen = 0;
    double own_unseen = 0;
    int dist_pearl = -1;
    int dist_soon = -1;
    int dist_unseen = -1;
    int dist_feed = -1;
    int dist_trade = -1;
    int dist_portal = -1;
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
        north_portal.assign(cells, PORTAL_NONE);
        west_portal.assign(cells, PORTAL_NONE);
        pearl_here.assign(cells, 0);
        pearl_timer.assign(cells, -2);
        seen_round.assign(cells, -1);
        enter_time.assign(cells, 0);
        ally_body_stamp.assign(cells, -1);
        feed_body_stamp.assign(cells, -1);
        enemy_head_stamp.assign(cells, -1);
        rival_dist.assign(cells, 0);
        rival_stamp.assign(cells, 0);
        ally_dist.assign(cells, 0);
        ally_stamp.assign(cells, 0);
        visit_stamp.assign(cells, 0);
        step_count.assign(cells, 0);
        eaten_count.assign(cells, 0);
        bfs_queue.resize(static_cast<std::size_t>(cells));
        sonar_tag = controller.get_team().value == unswbc::Team::A ? 0xA : 0x5;
    }

    void take_turn() {
        observe();

        if (DEBUG_STATS) {
            ct.output_log("STAT", length);
        }

        broadcast_leader();

        if (ready_to_die()) {
            ct.output_log("FEEDDIE", length, known_leader_id, known_leader_len);
            return;
        }

        int const child = split_child_size();
        if (child > 0) {
            ct.do_split(child);
            return;
        }

        Direction const best = pick_direction();
        int const escape = escape_child_size();
        if (escape > 0) {
            if (DEBUG_SPLIT) {
                ct.output_log("ESC len", length, "room", chosen_room);
            }
            ct.do_split(escape);
            return;
        }
        ct.make_move(best);
    }

  private:
    int split_child_size() const {
        if (round > SPLIT_LAST_ROUND || length < SPLIT_MIN_LENGTH || is_leader()) {
            return 0;
        }
        if (round > LEADER_GROW_ROUND && length > SPLIT_MIN_LENGTH) {
            return 0;
        }
        if (ct.get_unit_count() >= SPLIT_SOFT_LIMIT) {
            return 0;
        }
        int const child = SPLIT_IN_HALF ? length / 2 : unswbc::Constants::MIN_SIZE;
        return ct.can_split(child) ? child : 0;
    }

    int escape_child_size() {
        if (!USE_ESCAPE_SPLIT || length < ESCAPE_MIN_LENGTH || chosen_room > ESCAPE_ROOM_MAX) {
            return 0;
        }
        int const child = length - 2;
        bool const legal = tail_index >= 0 && ct.can_split(child);
        double const behind = legal ? tail_room() : -1.0;

        if (DEBUG_SPLIT && length >= 20) {
            ct.output_log("TRAP len", length, "room", chosen_room, "units", ct.get_unit_count(), "trail",
                          static_cast<int>(trail.size()), "legal", legal ? 1 : 0, "behind", behind);
        }

        if (!legal) {
            return 0;
        }
        return behind >= chosen_room + ESCAPE_MARGIN ? child : 0;
    }

    double tail_room() {
        strict_bodies = true;
        Survey const survey = survey_from(trail.back());
        strict_bodies = false;
        return survey.area_seen + UNSEEN_DISCOUNT * survey.area_unseen - 1.0;
    }

    int index_of(Position position) const { return position.y * width + position.x; }

    Position position_of(int index) const { return Position{index % width, index / width}; }

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
        auto const [index, horizontal] = canonical_edge(position, direction);
        (horizontal ? north_edge : west_edge)[index] = code;
        if (code == EDGE_PORTAL) {
            remember_portal(index, horizontal, edge.get_portal_id());
        }
    }

    std::pair<int, bool> canonical_edge(Position position, Direction direction) const {
        switch (direction.value) {
        case Direction::NORTH: return {index_of(position), true};
        case Direction::SOUTH: return {index_of(position.add_dir(dir_of(Direction::SOUTH))), true};
        case Direction::WEST:  return {index_of(position), false};
        default:               return {index_of(position.add_dir(dir_of(Direction::EAST))), false};
        }
    }

    void remember_portal(int index, bool horizontal, int id) {
        if (id < 0) {
            return;
        }
        (horizontal ? north_portal : west_portal)[index] = id;
        if (static_cast<std::size_t>(id) >= portal_edges.size()) {
            portal_edges.resize(static_cast<std::size_t>(id) + 1, {PORTAL_NONE, PORTAL_NONE});
        }
        int const key = 2 * index + (horizontal ? 0 : 1);
        auto& slot = portal_edges[static_cast<std::size_t>(id)];
        if (slot[0] == key || slot[1] == key) {
            return;
        }
        if (slot[0] == PORTAL_NONE) {
            slot[0] = key;
        } else if (slot[1] == PORTAL_NONE) {
            slot[1] = key;
        }
    }

    int portal_exit(Position position, Direction direction) const {
        auto const [index, horizontal] = canonical_edge(position, direction);
        int const id = (horizontal ? north_portal : west_portal)[index];
        if (id < 0 || static_cast<std::size_t>(id) >= portal_edges.size()) {
            return id < 0 ? PORTAL_NONE : PORTAL_UNKNOWN;
        }
        auto const& slot = portal_edges[static_cast<std::size_t>(id)];
        int const key = 2 * index + (horizontal ? 0 : 1);
        int const other = slot[0] == key ? slot[1] : slot[1] == key ? slot[0] : PORTAL_NONE;
        if (other < 0) {
            return PORTAL_UNKNOWN;
        }
        bool const other_horizontal = other % 2 == 0;
        if (other_horizontal != horizontal) {
            return PORTAL_UNKNOWN;
        }
        Position const cell = position_of(other / 2);
        if (horizontal) {
            return index_of(direction.value == Direction::NORTH ? cell.add_dir(dir_of(Direction::NORTH))
                                                                : cell);
        }
        return index_of(direction.value == Direction::WEST ? cell.add_dir(dir_of(Direction::WEST)) : cell);
    }

    int step_index(Position position, Direction direction) const {
        std::uint8_t const edge = edge_at(position, direction);
        if (edge == EDGE_KELP) {
            return -1;
        }
        if (edge == EDGE_PORTAL) {
            int const exit = USE_PORTALS ? portal_exit(position, direction) : PORTAL_NONE;
            return exit >= 0 ? exit : -1;
        }
        return index_of(position.add_dir(direction));
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

        if (trail.empty() || !(trail.front() == head)) {
            trail.push_front(head);
        }
        while (static_cast<int>(trail.size()) > length) {
            trail.pop_back();
        }

        for (int const touched : dirty) {
            enter_time[touched] = 0;
        }
        dirty.clear();
        other_heads.clear();
        ally_heads.clear();
        ally_head_ids.clear();
        ally_head_dirs.clear();
        seen_ids.clear();
        seen_parts.clear();
        ally_body_ids.clear();
        ally_body_indices.clear();
        enemy_heads.clear();
        own_parts.clear();
        hear_sonar();
        hear_leader(ct.get_id(), length, round, head, ct.get_dir());

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
                if (part->get_team() == ct.get_team()) {
                    count_ally_part(part->get_id());
                    if (!part->is_head()) {
                        ally_body_stamp[index] = round;
                        ally_body_ids.push_back(part->get_id());
                        ally_body_indices.push_back(index);
                    }
                }
            } else {
                own_parts.push_back(index);
            }
            if (part->is_head() && part->get_id() != ct.get_id()) {
                other_heads.push_back(position);
                if (part->get_team() == ct.get_team()) {
                    ally_heads.push_back(position);
                    ally_head_ids.push_back(part->get_id());
                    ally_head_dirs.push_back(part->get_dir());
                } else {
                    enemy_heads.push_back(position);
                    enemy_head_stamp[index] = round;
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
        for (std::size_t k = 0; k < ally_head_ids.size(); k++) {
            hear_leader(ally_head_ids[k], visible_parts(ally_head_ids[k]), round, ally_heads[k],
                        ally_head_dirs[k]);
        }
        pick_feed_target();
        stamp_feed_body();
        refresh_leader_zone();
        map_rivals();
    }

    void count_ally_part(int id) {
        for (std::size_t slot = 0; slot < seen_ids.size(); slot++) {
            if (seen_ids[slot] == id) {
                seen_parts[slot]++;
                return;
            }
        }
        seen_ids.push_back(id);
        seen_parts.push_back(1);
    }

    int visible_parts(int id) const {
        for (std::size_t slot = 0; slot < seen_ids.size(); slot++) {
            if (seen_ids[slot] == id) {
                return seen_parts[slot];
            }
        }
        return 0;
    }

    static int face_code(Direction facing) {
        return facing.value == Direction::NORTH ? 0 : facing.value == Direction::EAST ? 1
                                                  : facing.value == Direction::SOUTH   ? 2
                                                                                       : 3;
    }

    static std::uint8_t sonar_checksum(std::uint64_t body) {
        std::uint8_t sum = 0;
        for (int shift = 0; shift < 56; shift += 8) {
            sum ^= static_cast<std::uint8_t>(body >> shift);
        }
        return sum;
    }

    std::uint64_t pack_leader(int id, int len, int when, Position pos, Direction facing) const {
        std::uint64_t const body = (static_cast<std::uint64_t>(id) & 0xFFFF) |
                                   ((static_cast<std::uint64_t>(len) & 0xFFF) << 16) |
                                   ((static_cast<std::uint64_t>(when) & 0x1FF) << 28) |
                                   ((static_cast<std::uint64_t>(pos.x) & 0x3F) << 37) |
                                   ((static_cast<std::uint64_t>(pos.y) & 0x3F) << 43) |
                                   ((static_cast<std::uint64_t>(face_code(facing)) & 0x3) << 49) |
                                   ((sonar_tag & 0xF) << 51);
        return body | (static_cast<std::uint64_t>(sonar_checksum(body)) << 55);
    }

    bool unpack_leader(std::uint64_t message, int& id, int& len, int& when, Position& pos,
                       Direction& facing) const {
        std::uint64_t const body = message & ((1ULL << 55) - 1);
        if (((body >> 51) & 0xF) != sonar_tag) {
            return false;
        }
        if (sonar_checksum(body) != static_cast<std::uint8_t>(message >> 55)) {
            return false;
        }
        id = static_cast<int>(body & 0xFFFF);
        len = static_cast<int>((body >> 16) & 0xFFF);
        when = static_cast<int>((body >> 28) & 0x1FF);
        pos = Position{static_cast<int>((body >> 37) & 0x3F), static_cast<int>((body >> 43) & 0x3F)};
        int const face = static_cast<int>((body >> 49) & 0x3);
        facing = dir_of(face == 0   ? Direction::NORTH
                        : face == 1 ? Direction::EAST
                        : face == 2 ? Direction::SOUTH
                                    : Direction::WEST);
        return id >= 0 && len > 0 && len <= cells && when <= round && pos.x < width && pos.y < height;
    }

    void hear_leader(int id, int len, int when, Position pos, Direction facing) {
        if (id < 0 || len <= 0 || len > cells || when < 0 || when > round || round - when > SONAR_STALE ||
            pos.x < 0 || pos.y < 0 || pos.x >= width || pos.y >= height) {
            return;
        }
        if (id == known_leader_id && len >= known_leader_len) {
            known_leader_len = len;
            if (when >= known_leader_round) {
                known_leader_round = when;
                known_leader_pos = pos;
                known_leader_dir = facing;
            }
            return;
        }
        if (len > known_leader_len || (len == known_leader_len && when > known_leader_round)) {
            known_leader_id = id;
            known_leader_len = len;
            known_leader_round = when;
            known_leader_pos = pos;
            known_leader_dir = facing;
        }
    }

    void hear_sonar() {
        if (known_leader_id >= 0 && known_leader_id != ct.get_id() && known_leader_round >= 0 &&
            round - known_leader_round > SONAR_STALE) {
            known_leader_id = -1;
            known_leader_len = 0;
            known_leader_round = -1;
        }
        if (!USE_SONAR_LEADER) {
            return;
        }
        for (std::uint64_t const message : ct.get_sonar_messages()) {
            int id = -1;
            int len = 0;
            int when = -1;
            Position pos{};
            Direction facing = dir_of(Direction::NORTH);
            if (unpack_leader(message, id, len, when, pos, facing)) {
                hear_leader(id, len, when, pos, facing);
            }
        }
    }

    void broadcast_leader() {
        if (!USE_SONAR_LEADER || known_leader_id < 0) {
            return;
        }
        std::uint64_t const message =
            pack_leader(known_leader_id, known_leader_len, known_leader_round, known_leader_pos, known_leader_dir);
        for (Direction const direction : Direction::get_direction_list()) {
            ct.send_sonar(direction, message);
        }
    }

    int manhattan(Position a, Position b) const {
        return torus_gap(a.x, b.x, width) + torus_gap(a.y, b.y, height);
    }

    Position live_leader_head() const {
        for (std::size_t k = 0; k < ally_head_ids.size(); k++) {
            if (ally_head_ids[k] == known_leader_id) {
                return ally_heads[k];
            }
        }
        return known_leader_pos;
    }

    Direction live_leader_dir() const {
        for (std::size_t k = 0; k < ally_head_ids.size(); k++) {
            if (ally_head_ids[k] == known_leader_id) {
                return ally_head_dirs[k];
            }
        }
        return known_leader_dir;
    }

    int forward_along(Position cell, Position origin, Direction facing) const {
        if (facing.value == Direction::EAST) {
            return (cell.x - origin.x + width) % width;
        }
        if (facing.value == Direction::WEST) {
            return (origin.x - cell.x + width) % width;
        }
        if (facing.value == Direction::SOUTH) {
            return (cell.y - origin.y + height) % height;
        }
        return (origin.y - cell.y + height) % height;
    }

    int across_axis(Position cell, Position origin, Direction facing) const {
        if (facing.value == Direction::EAST || facing.value == Direction::WEST) {
            return torus_gap(cell.y, origin.y, height);
        }
        return torus_gap(cell.x, origin.x, width);
    }

    bool on_leader_ray(Position cell) const {
        if (known_leader_id < 0) {
            return false;
        }
        Position const origin = live_leader_head();
        Direction const facing = live_leader_dir();
        int const along = forward_along(cell, origin, facing);
        return across_axis(cell, origin, facing) == 0 && along > 0 && along <= FEEDER_DROP_MAX;
    }

    bool in_leader_keep_off(Position cell) const {
        if (known_leader_id < 0 || known_leader_id == ct.get_id()) {
            return false;
        }
        return manhattan(cell, live_leader_head()) <= FEEDER_KEEP_OFF;
    }

    Position walk(Position start, Direction facing, int steps) const {
        Position cell = start;
        for (int i = 0; i < steps; i++) {
            cell = cell.add_dir(facing);
        }
        return cell;
    }

    void pick_feed_target() {
        feed_index = -1;
        feed_id = -1;
        if (!USE_FEEDER_SACRIFICE || round <= ENDGAME_ROUND || known_leader_id < 0 ||
            known_leader_id == ct.get_id() || known_leader_len < 2 || length * 2 > known_leader_len ||
            ct.get_unit_count() <= FEEDER_KEEP_UNITS) {
            return;
        }
        Position const origin = live_leader_head();
        if (manhattan(head, origin) > FEEDER_APPROACH) {
            return;
        }
        if (ct.get_id() % FEEDER_THROTTLE != (round / FEEDER_THROTTLE_PERIOD) % FEEDER_THROTTLE) {
            return;
        }
        Direction const facing = live_leader_dir();
        int best_dist = BLOCKED_FOREVER;
        for (int step = FEEDER_DROP_MIN; step <= FEEDER_DROP_MAX; step++) {
            Position const along = walk(origin, facing, step);
            Direction const sides[2] = {facing.get_left(), facing.get_right()};
            for (Direction const side : sides) {
                Position const cell = along.add_dir(side);
                if (in_leader_keep_off(cell) || on_leader_ray(cell)) {
                    continue;
                }
                int const index = index_of(cell);
                if (enter_time[index] >= BLOCKED_FOREVER) {
                    continue;
                }
                int const dist = manhattan(head, cell);
                if (dist < best_dist) {
                    best_dist = dist;
                    feed_index = index;
                    feed_id = known_leader_id;
                }
            }
        }
    }

    void refresh_leader_zone() {
        zone_active = false;
        if (round <= (LEADER_ZONE_EARLY ? LEADER_GROW_ROUND : ENDGAME_ROUND) || known_leader_id < 0 ||
            known_leader_id == ct.get_id()) {
            return;
        }
        for (std::size_t k = 0; k < ally_head_ids.size(); k++) {
            if (ally_head_ids[k] == known_leader_id) {
                zone_head = ally_heads[k];
                zone_active = true;
                return;
            }
        }
        zone_head = known_leader_pos;
        zone_active = true;
    }

    bool in_leader_pearl_zone(int index) const {
        if (!zone_active) {
            return false;
        }
        Position const cell = position_of(index);
        return torus_gap(cell.x, zone_head.x, width) + torus_gap(cell.y, zone_head.y, height) <=
               LEADER_PEARL_RADIUS;
    }

    void stamp_feed_body() {
        if (feed_id < 0) {
            return;
        }
        for (std::size_t slot = 0; slot < ally_body_ids.size(); slot++) {
            if (ally_body_ids[slot] == feed_id) {
                feed_body_stamp[ally_body_indices[slot]] = round;
            }
        }
    }

    void flood_heads(std::vector<Position> const& heads, std::vector<int>& dist, std::vector<int>& stamp,
                     int mark) {
        int queue_head = 0;
        int queue_tail = 0;
        for (Position const& origin : heads) {
            int const index = index_of(origin);
            if (stamp[index] == mark) {
                continue;
            }
            stamp[index] = mark;
            dist[index] = 0;
            bfs_queue[queue_tail++] = origin;
        }
        while (queue_head < queue_tail) {
            Position const position = bfs_queue[queue_head++];
            int const index = index_of(position);
            int const steps = dist[index];
            for (Direction const direction : Direction::get_direction_list()) {
                int const next_index = step_index(position, direction);
                if (next_index < 0 || stamp[next_index] == mark || enter_time[next_index] != 0) {
                    continue;
                }
                stamp[next_index] = mark;
                dist[next_index] = steps + 1;
                bfs_queue[queue_tail++] = position_of(next_index);
            }
        }
    }

    void map_rivals() {
        if (!USE_VORONOI) {
            return;
        }
        rival_mark++;
        flood_heads(enemy_heads, rival_dist, rival_stamp, rival_mark);
        ally_mark++;
        flood_heads(VORONOI_ALLIES ? other_heads : ally_heads, ally_dist, ally_stamp, ally_mark);
    }

    int rival_steps(int index) const {
        return rival_stamp[index] == rival_mark ? rival_dist[index] : BLOCKED_FOREVER;
    }

    int ally_race_steps(int index) const {
        return ally_stamp[index] == ally_mark ? ally_dist[index] : BLOCKED_FOREVER;
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

        bool const scouting = can_scout_portals();
        while (queue_head < queue_tail) {
            Position const position = bfs_queue[queue_head++];
            int const index = index_of(position);
            int const steps = step_count[index];
            int const eaten = eaten_count[index];

            int const theirs = rival_steps(index);
            double share = steps < theirs ? 1.0 : steps == theirs ? CONTESTED_SHARE : 0.0;
            if (ally_race_steps(index) < steps) {
                share = 0.0;
            }
            if (seen_round[index] < 0) {
                result.area_unseen++;
                result.own_unseen += share;
            } else {
                result.area_seen++;
                result.own_seen += share;
            }
            if (index == tail_index) {
                result.reaches_tail = true;
            }
            if (result.dist_feed < 0 && index == feed_index) {
                result.dist_feed = steps;
            }
            if (share >= 1.0 && result.dist_pearl < 0 && pearl_here[index] && !in_leader_pearl_zone(index)) {
                result.dist_pearl = steps;
            }
            if (share >= 1.0 && result.dist_soon < 0 && seen_round[index] >= 0 && pearl_timer[index] >= 0 &&
                !in_leader_pearl_zone(index)) {
                int const spawns_in = pearl_timer[index] - (round - seen_round[index]);
                if (spawns_in <= steps + 1) {
                    result.dist_soon = steps;
                }
            }
            if (result.dist_unseen < 0 && seen_round[index] < 0) {
                result.dist_unseen = steps;
            }

            for (Direction const direction : Direction::get_direction_list()) {
                int const next_index = step_index(position, direction);
                if (next_index < 0) {
                    if (scouting && result.dist_portal < 0 && leads_to_unknown(position, direction)) {
                        result.dist_portal = steps + 1;
                    }
                    continue;
                }
                if (visit_stamp[next_index] == visit_mark) {
                    continue;
                }
                int const free_at = enter_time[next_index];
                if (free_at >= BLOCKED_FOREVER || steps + 1 - eaten < free_at) {
                    if (result.dist_feed < 0 && next_index == feed_index) {
                        result.dist_feed = steps + 1;
                    }
                    if (result.dist_trade < 0 && is_enemy_head_cell(next_index)) {
                        result.dist_trade = steps + 1;
                    }
                    continue;
                }
                if (strict_bodies && free_at != 0) {
                    continue;
                }
                visit_stamp[next_index] = visit_mark;
                step_count[next_index] = steps + 1;
                eaten_count[next_index] = eaten + pearl_here[next_index];
                bfs_queue[queue_tail++] = position_of(next_index);
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

    bool enemy_can_step_to(Position cell) const {
        int const dest = index_of(cell);
        for (Position const& enemy : enemy_heads) {
            for (Direction const direction : Direction::get_direction_list()) {
                if (step_index(enemy, direction) == dest) {
                    return true;
                }
            }
        }
        return false;
    }

    bool is_enemy_head(Position position) const {
        for (Position const& enemy : enemy_heads) {
            if (enemy == position) {
                return true;
            }
        }
        return false;
    }

    bool is_ally_body(int index) const { return ally_body_stamp[index] == round; }
    bool is_feed_body(int index) const { return feed_body_stamp[index] == round; }
    bool is_enemy_head_cell(int index) const { return enemy_head_stamp[index] == round; }
    bool is_leader() const {
        return round > LEADER_GROW_ROUND && known_leader_id == ct.get_id();
    }

    bool is_trader() const {
        return USE_TRADE_ATTACK && round <= ENDGAME_ROUND && length <= TRADE_MAX_LENGTH && !is_leader() &&
               ct.get_unit_count() >= TRADE_MIN_UNITS;
    }

    bool can_scout_portals() const {
        return USE_PORTALS && USE_PORTAL_SCOUT && length <= PORTAL_SCOUT_MAX_LENGTH && !is_feeder() &&
               !is_leader();
    }

    bool leads_to_unknown(Position position, Direction direction) const {
        return edge_at(position, direction) == EDGE_PORTAL && portal_exit(position, direction) < 0;
    }

    bool is_feeder() const {
        return USE_FEEDER_SACRIFICE && feed_index >= 0;
    }

    bool on_drop_cell(Position cell) const {
        if (known_leader_id < 0 || known_leader_id == ct.get_id()) {
            return false;
        }
        if (in_leader_keep_off(cell) || on_leader_ray(cell)) {
            return false;
        }
        Position const origin = live_leader_head();
        Direction const facing = live_leader_dir();
        int const along = forward_along(cell, origin, facing);
        return across_axis(cell, origin, facing) == 1 && along >= FEEDER_DROP_MIN && along <= FEEDER_DROP_MAX;
    }

    bool ready_to_die() const { return is_feeder() && on_drop_cell(head); }

    double score_step(Position destination) {
        Survey const survey = survey_from(destination);

        double const room = survey.area_seen + UNSEEN_DISCOUNT * survey.area_unseen;
        double const territory = survey.own_seen + UNSEEN_DISCOUNT * survey.own_unseen;
        last_room = room;
        last_seen_room = survey.area_seen;
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

        last_bonus = std::max({target_bonus(survey.dist_pearl, WEIGHT_PEARL),
                               target_bonus(survey.dist_soon, WEIGHT_SOON),
                               target_bonus(survey.dist_unseen, WEIGHT_UNSEEN),
                               target_bonus(survey.dist_portal, WEIGHT_PORTAL_SCOUT)});
        score += last_bonus;

        if (AVOID_ALLY_HEADS) {
            for (Position const& ally : ally_heads) {
                if (is_neighbour(destination, ally)) {
                    score -= PENALTY_ENEMY_HEAD;
                }
            }
        }
        if (!is_trader() && enemy_can_step_to(destination)) {
            score -= is_leader() ? PENALTY_HEAD_RACE * LEADER_HEAD_MULT : PENALTY_HEAD_RACE;
        }

        if (is_feeder() && survey.dist_feed >= 0) {
            score += std::max(0.0, FEEDER_REWARD - FEEDER_DECAY * survey.dist_feed);
        }
        if (is_trader() && survey.dist_trade >= 0) {
            score += std::max(0.0, TRADE_REWARD - TRADE_DECAY * survey.dist_trade);
        }
        return score;
    }

    double score_portal_step(Direction direction) {
        if (!USE_PORTALS) {
            return SCORE_PORTAL;
        }
        int const exit = portal_exit(head, direction);
        if (exit < 0 || enter_time[exit] > 1) {
            return SCORE_PORTAL;
        }
        double const score = score_step(position_of(exit));
        if (length > PORTAL_SCOUT_MAX_LENGTH && last_seen_room < length + PORTAL_SAFETY_MARGIN) {
            return SCORE_PORTAL;
        }
        return score;
    }

    Direction pick_direction() {
        Direction best = dir_of(Direction::NORTH);
        double best_score = SCORE_REJECT * 2.0;
        chosen_room = 0.0;

        auto const directions = Direction::get_direction_list();
        std::array<double, 4> scores{};
        std::array<double, 4> rooms{};
        std::array<bool, 4> blind{};
        double best_base = SCORE_REJECT;
        bool const scouting = can_scout_portals();

        for (std::size_t k = 0; k < directions.size(); k++) {
            Direction const direction = directions[k];
            std::uint8_t const edge = edge_at(head, direction);
            double score = SCORE_REJECT;

            last_room = 0.0;
            if (edge == EDGE_PORTAL) {
                score = score_portal_step(direction);
                blind[k] = scouting && score <= SCORE_PORTAL && leads_to_unknown(head, direction);
            } else if (edge != EDGE_KELP) {
                Position const destination = head.add_dir(direction);
                if (is_feeder() && (in_leader_keep_off(destination) || on_leader_ray(destination))) {
                    score = SCORE_REJECT;
                } else if (enter_time[index_of(destination)] <= 1) {
                    score = score_step(destination);
                    best_base = std::max(best_base, score - last_bonus);
                } else if (is_enemy_head(destination)) {
                    score = is_trader() ? TRADE_REWARD : SCORE_REJECT * 0.5;
                }
            }
            scores[k] = score;
            rooms[k] = last_room;
        }

        for (std::size_t k = 0; k < directions.size(); k++) {
            Direction const direction = directions[k];
            double score = scores[k];
            if (blind[k] && best_base > SCORE_REJECT * 0.5) {
                score = best_base + target_bonus(1, WEIGHT_PORTAL_SCOUT);
            }

            score += 0.25 * ((TIE_SEED * 101 + ct.get_id() * 31 + round * 17 + static_cast<int>(k) * 7) % 5);

            if (DEBUG_LOG) {
                ct.output_log("r", round, "len", length, "trail", static_cast<int>(trail.size()), "dir",
                              direction, "edge", static_cast<int>(edge_at(head, direction)), "enter",
                              enter_time[index_of(head.add_dir(direction))], "score", score);
            }

            if (score > best_score) {
                best_score = score;
                best = direction;
                chosen_room = rooms[k];
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
    std::vector<int> north_portal;
    std::vector<int> west_portal;
    std::vector<std::array<int, 2>> portal_edges;
    std::vector<std::uint8_t> pearl_here;
    std::vector<int> pearl_timer;
    std::vector<int> seen_round;

    std::vector<int> enter_time;
    std::vector<int> ally_body_stamp;
    std::vector<int> feed_body_stamp;
    std::vector<int> enemy_head_stamp;
    std::vector<int> dirty;
    std::vector<Position> other_heads;
    std::vector<Position> ally_heads;
    std::vector<int> ally_head_ids;
    std::vector<Direction> ally_head_dirs;
    std::vector<int> seen_ids;
    std::vector<int> seen_parts;
    std::vector<int> ally_body_ids;
    std::vector<int> ally_body_indices;
    int feed_index = -1;
    int feed_id = -1;
    int known_leader_id = -1;
    int known_leader_len = 0;
    int known_leader_round = -1;
    std::uint64_t sonar_tag = 0xA;
    Position known_leader_pos{};
    Direction known_leader_dir = dir_of(Direction::NORTH);
    bool zone_active = false;
    Position zone_head{};
    std::vector<Position> enemy_heads;
    std::vector<int> own_parts;
    std::deque<Position> trail;
    int tail_index = -1;

    std::vector<int> rival_dist;
    std::vector<int> rival_stamp;
    int rival_mark = 0;
    std::vector<int> ally_dist;
    std::vector<int> ally_stamp;
    int ally_mark = 0;

    double chosen_room = 0.0;
    double last_room = 0.0;
    double last_bonus = 0.0;
    double last_seen_room = 0.0;
    bool strict_bodies = false;

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
