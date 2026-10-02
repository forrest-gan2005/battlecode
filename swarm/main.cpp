#include "helper.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdlib>
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
constexpr int THREAT_REACH_MIN = 2;
constexpr int THREAT_REACH_MAX = 6;
constexpr double THREAT_LENGTH_SCALE = 4.0;
constexpr int SMALL_UNIT_THREAT_REACH = 1;
constexpr int SPRINT_ESCAPE_MIN_LENGTH = 8;
constexpr double SPRINT_ESCAPE_COST = 400.0;
constexpr int SPRINT_ESCAPE_MAX_EVALS = 4;


constexpr int SPLIT_LAST_ROUND = 495;
constexpr int SPLIT_MIN_LENGTH = 4;
constexpr bool SPLIT_IN_HALF = false;
constexpr int SPLIT_SOFT_LIMIT = 60;

constexpr bool USE_FEEDER_SACRIFICE = true;
constexpr bool USE_SONAR_LEADER = true;
constexpr int ENDGAME_ROUND = 500;
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

constexpr int FEEDER_FRESH_ROUNDS = 5;

constexpr int FEEDER_DIE_DIST = 3;
constexpr int FEEDER_FRONT_CLEAR = 3;
constexpr int FEEDER_ENEMY_CLEAR = 4;
constexpr double ZONE_PEARL_PENALTY = 600.0;

constexpr double LEADER_ENDGAME_PEARL_MULT = 4.0;
constexpr double FEEDER_REWARD = 3000.0;
constexpr double FEEDER_DECAY = 60.0;
constexpr double LEADER_HEAD_MULT = 2.0;

constexpr bool USE_TRADE_ATTACK = true;
constexpr int TRADE_MAX_LENGTH = 4;
constexpr int TRADE_MIN_UNITS = 1;

constexpr int TRADE_TARGET_MIN_PARTS = 5;

constexpr int RAM_MAX_STEPS = 3;
constexpr double TRADE_REWARD = 2500.0;
constexpr double TRADE_DECAY = 80.0;

constexpr bool USE_ESCAPE_SPLIT = true;

constexpr int ESCAPE_MIN_LENGTH = 4;
constexpr double ESCAPE_ROOM_MAX = 4.0;
constexpr double ESCAPE_MARGIN = 4.0;



constexpr bool USE_DEAD_END_HARVEST = true;
constexpr double HARVEST_SEGMENT_VALUE = 150.0;

constexpr int HARVEST_MIN_NET = 1;

constexpr int HARVEST_MAX_LENGTH = 6;
constexpr int HARVEST_INSIDE_SLACK = 2;

constexpr bool NO_MOVE_ESCAPE_FIRST = true;

constexpr int LONG_SAFE_MIN_LENGTH = 8;
constexpr double LONG_THREAT_VETO = 1e6;
constexpr bool LONG_DODGE_SPLIT = true;
constexpr int DODGE_MIN_LENGTH = 12;
constexpr int SPRINT_THREAT_REACH = 6;

constexpr int CONTEST_MAX_LENGTH = 4;
constexpr int CONTEST_SLACK = 1;
constexpr double CHILD_MIN_ROOM = 4.0;
constexpr int ESCAPE_RESERVE = 2;



constexpr int SONAR_COORD_MAX = 127;

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

constexpr int SOON_SLACK = 6;
constexpr double WEIGHT_UNSEEN = 0.20;
constexpr double PENALTY_NO_TAIL = 600.0;
constexpr double PENALTY_ENEMY_HEAD = 450.0;
constexpr double SCORE_PORTAL = -1e9;

constexpr double PORTAL_LEAP_PENALTY = 150.0;
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
    int pearls = 0;
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
        trade_target_stamp.assign(cells, -1);
        threat_stamp.assign(cells, 0);
        threat_depth.assign(cells, 0);
        threat_depth_small.assign(cells, 0);
        bfs_parent.assign(cells, -1);
        bfs_via.assign(cells, 'N');
        rival_dist.assign(cells, 0);
        rival_stamp.assign(cells, 0);
        ally_dist.assign(cells, 0);
        ally_stamp.assign(cells, 0);
        visit_stamp.assign(cells, 0);
        step_count.assign(cells, 0);
        eaten_count.assign(cells, 0);
        bfs_queue.resize(static_cast<std::size_t>(cells));
        sonar_tag = controller.get_team().value == unswbc::Team::A ? 0x2 : 0x1;
        sonar_enabled = USE_SONAR_LEADER && width <= SONAR_COORD_MAX + 1 && height <= SONAR_COORD_MAX + 1;
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

        
        Direction const best = pick_direction();

        std::vector<Direction> path;
        if (ram_path(path)) {
            ct.make_moves(path);
            remember_path(path);
            return;
        }

        
        
        if (NO_MOVE_ESCAPE_FIRST && !any_enterable) {
            int const escape = escape_child_size();
            if (escape > 0) {
                ct.do_split(escape);
                return;
            }
        }

        if (LONG_DODGE_SPLIT && cornered && tail_index >= 0 && threat_at(tail_index) == 0) {
            int const tail_part = length - unswbc::Constants::MIN_SIZE;
            if (ct.can_split(tail_part) && tail_room() >= CHILD_MIN_ROOM) {
                ct.do_split(tail_part);
                return;
            }
        }

        harvesting_now = chosen_harvest || harvest_round == round - 1;
        if (chosen_harvest) {
            harvest_round = round;
        }
        int const escape = harvesting_now ? escape_child_size() : 0;
        if (escape > 0) {
            ct.do_split(escape);
            return;
        }

        int const child = split_child_size();
        if (child > 0) {
            ct.do_split(child);
            return;
        }

        int const late_escape = harvesting_now ? 0 : escape_child_size();
        if (late_escape > 0) {
            if (DEBUG_SPLIT) {
                ct.output_log("ESC len", length, "room", chosen_room);
            }
            ct.do_split(late_escape);
            return;
        }
        if (sprint_escape(path)) {
            ct.make_moves(path);
            remember_path(path);
            return;
        }
        ct.make_move(best);
    }

    
    void remember_path(std::vector<Direction> const& path) {
        pending_path.clear();
        Position cell = head;
        for (Direction const direction : path) {
            int const next = step_index(cell, direction);
            if (next < 0) {
                pending_path.clear();
                return;
            }
            cell = position_of(next);
            pending_path.push_back(cell);
        }
    }

  private:
    int split_child_size() {
        if (round > SPLIT_LAST_ROUND || length < SPLIT_MIN_LENGTH || is_leader()) {
            return 0;
        }
        if (round > LEADER_GROW_ROUND && length > SPLIT_MIN_LENGTH) {
            return 0;
        }
        if (ct.get_unit_count() >= SPLIT_SOFT_LIMIT) {
            return 0;
        }
        
        
        if (harvesting_now) {
            return 0;
        }
        int const child = SPLIT_IN_HALF ? length / 2 : unswbc::Constants::MIN_SIZE;
        if (!ct.can_split(child)) {
            return 0;
        }
        
        if (tail_index < 0) {
            return child;
        }
        
        
        if (!child_has_exit() || tail_room() < CHILD_MIN_ROOM) {
            return 0;
        }
        
        if (child_spans_portal(child)) {
            return 0;
        }
        return child;
    }

    bool child_has_exit() const {
        Position const tail = trail.back();
        for (Direction const direction : Direction::get_direction_list()) {
            int const next = step_index(tail, direction);
            if (next >= 0 && enter_time[next] == 0) {
                return true;
            }
        }
        return false;
    }

    bool child_spans_portal(int child) const {
        for (int k = length - child; k + 1 < length; k++) {
            if (manhattan(trail[static_cast<std::size_t>(k)], trail[static_cast<std::size_t>(k) + 1]) != 1) {
                return true;
            }
        }
        return false;
    }

    int escape_child_size() {
        if (!USE_ESCAPE_SPLIT || length < ESCAPE_MIN_LENGTH) {
            return 0;
        }
        
        
        bool const no_move = !any_enterable;
        bool const boxed = chosen_scored && chosen_room <= ESCAPE_ROOM_MAX && !chosen_reaches_tail;
        if (!no_move && !boxed) {
            return 0;
        }
        int const child = length - 2;
        if (!ct.can_split(child)) {
            return 0;
        }
        if (length < LONG_SAFE_MIN_LENGTH && ct.get_unit_count() >= gm.get_unit_limit() - ESCAPE_RESERVE) {
            return 0;
        }
        if (no_move) {
            
            return child;
        }
        
        if (tail_index < 0) {
            return 0;
        }
        if (defer_escape()) {
            return 0;
        }
        double const behind = tail_room();

        if (DEBUG_SPLIT) {
            ct.output_log("TRAP len", length, "room", chosen_room, "units", ct.get_unit_count(), "trail",
                          static_cast<int>(trail.size()), "behind", behind);
        }
        return behind >= chosen_room + ESCAPE_MARGIN ? child : 0;
    }

    
    
    
    
    bool harvestable(int pocket_pearls, double pocket_room, bool inside) {
        int const min_size = unswbc::Constants::MIN_SIZE;
        if (!USE_DEAD_END_HARVEST || !USE_ESCAPE_SPLIT || is_feeder() || is_leader() || tail_index < 0) {
            return false;
        }
        
        if (inside ? length > HARVEST_MAX_LENGTH + HARVEST_INSIDE_SLACK || pocket_pearls < 1
                   : length > HARVEST_MAX_LENGTH || pocket_pearls - min_size < HARVEST_MIN_NET) {
            return false;
        }
        if (length + pocket_pearls < 2 * min_size || length + pocket_pearls <= pocket_room) {
            return false;
        }
        if (ct.get_unit_count() >= gm.get_unit_limit() - ESCAPE_RESERVE) {
            return false;
        }
        if (behind_round != round) {
            behind_round = round;
            behind_room = tail_room();
        }
        return behind_room >= length + 2.0;
    }

    
    
    bool defer_escape() {
        if (!USE_DEAD_END_HARVEST || !chosen_harvest || chosen_pearls <= 0 || chosen_index < 0) {
            return false;
        }
        if (pearl_here[chosen_index]) {
            return true;
        }
        if (static_cast<int>(trail.size()) < 2) {
            return false;
        }
        Survey const next = survey_from(trail[trail.size() - 2], true, false);
        double const next_room = next.area_seen + UNSEEN_DISCOUNT * next.area_unseen - 1.0;
        return next_room >= chosen_room + ESCAPE_MARGIN;
    }

    double tail_room() {
        
        Survey const survey = survey_from(trail.back(), true, false);
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

    void observe() {
        round = gm.get_round_num();
        length = ct.get_length();
        head = ct.get_position();

        if (!pending_path.empty()) {
            if (pending_path.back() == head) {
                for (std::size_t k = 0; k + 1 < pending_path.size(); k++) {
                    if (trail.empty() || !(trail.front() == pending_path[k])) {
                        trail.push_front(pending_path[k]);
                    }
                }
            }
            pending_path.clear();
        }
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
        enemy_heads.clear();
        enemy_head_ids.clear();
        own_parts.clear();
        expire_leader();
        
        hear_exact(ct.get_id(), length, round, head, ct.get_dir());
        hear_sonar();

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
                count_part(part->get_id());
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
                    enemy_head_ids.push_back(part->get_id());
                }
            }
        }

        extend_trail_from_vision();

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
            hear_sighting(ally_head_ids[k], visible_parts(ally_head_ids[k]), ally_heads[k], ally_head_dirs[k]);
        }
        compute_drop_cells();
        pick_feed_target();
        refresh_leader_zone();
        map_rivals();
        map_threats();
        mark_trade_targets();
    }

    
    
    void extend_trail_from_vision() {
        while (static_cast<int>(trail.size()) < length) {
            Position const last = trail.back();
            int const last_index = index_of(last);
            bool found = false;
            for (Direction const direction : Direction::get_direction_list()) {
                int const behind = step_index(last, direction);
                if (behind < 0) {
                    continue;
                }
                Position const cell = position_of(behind);
                auto const* tile = ct.get_tile(cell);
                auto const* part = tile ? tile->get_dragon() : nullptr;
                if (!part || part->get_id() != ct.get_id() || part->is_head()) {
                    continue;
                }
                if (step_index(cell, part->get_dir()) != last_index) {
                    continue;
                }
                if (std::find(trail.begin(), trail.end(), cell) != trail.end()) {
                    continue;
                }
                trail.push_back(cell);
                found = true;
                break;
            }
            if (!found) {
                return;
            }
        }
    }

    void count_part(int id) {
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
                                   ((static_cast<std::uint64_t>(pos.x) & 0x7F) << 37) |
                                   ((static_cast<std::uint64_t>(pos.y) & 0x7F) << 44) |
                                   ((static_cast<std::uint64_t>(face_code(facing)) & 0x3) << 51) |
                                   ((sonar_tag & 0x3) << 53);
        return body | (static_cast<std::uint64_t>(sonar_checksum(body)) << 55);
    }

    bool unpack_leader(std::uint64_t message, int& id, int& len, int& when, Position& pos,
                       Direction& facing) const {
        std::uint64_t const body = message & ((1ULL << 55) - 1);
        if (((body >> 53) & 0x3) != sonar_tag) {
            return false;
        }
        if (sonar_checksum(body) != static_cast<std::uint8_t>(message >> 55)) {
            return false;
        }
        id = static_cast<int>(body & 0xFFFF);
        len = static_cast<int>((body >> 16) & 0xFFF);
        when = static_cast<int>((body >> 28) & 0x1FF);
        pos = Position{static_cast<int>((body >> 37) & 0x7F), static_cast<int>((body >> 44) & 0x7F)};
        int const face = static_cast<int>((body >> 51) & 0x3);
        facing = dir_of(face == 0   ? Direction::NORTH
                        : face == 1 ? Direction::EAST
                        : face == 2 ? Direction::SOUTH
                                    : Direction::WEST);
        return id >= 0 && len > 0 && len <= cells && when <= round && pos.x < width && pos.y < height;
    }

    bool plausible_report(int id, int len, int when, Position pos) const {
        return id >= 0 && len > 0 && len <= cells && when >= 0 && when <= round && round - when <= SONAR_STALE &&
               pos.x >= 0 && pos.y >= 0 && pos.x < width && pos.y < height;
    }

    void forget_leader() {
        known_leader_id = -1;
        known_leader_len = 0;
        known_leader_round = -1;
    }

    void expire_leader() {
        if (known_leader_id >= 0 && known_leader_id != ct.get_id() && known_leader_round >= 0 &&
            round - known_leader_round > SONAR_STALE) {
            forget_leader();
        }
    }

    
    
    void hear_exact(int id, int len, int when, Position pos, Direction facing) {
        if (!plausible_report(id, len, when, pos)) {
            return;
        }
        if (id == known_leader_id) {
            if (when >= known_leader_round) {
                known_leader_len = len;
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

    
    void hear_sighting(int id, int visible, Position pos, Direction facing) {
        if (id == known_leader_id) {
            known_leader_len = std::max(known_leader_len, visible);
            known_leader_pos = pos;
            known_leader_dir = facing;
            return;
        }
        if (visible > known_leader_len) {
            known_leader_id = id;
            known_leader_len = visible;
            known_leader_round = round;
            known_leader_pos = pos;
            known_leader_dir = facing;
        }
    }

    void hear_sonar() {
        if (!sonar_enabled) {
            return;
        }
        for (std::uint64_t const message : ct.get_sonar_messages()) {
            int id = -1;
            int len = 0;
            int when = -1;
            Position pos{};
            Direction facing = dir_of(Direction::NORTH);
            
            if (unpack_leader(message, id, len, when, pos, facing) && id != ct.get_id()) {
                hear_exact(id, len, when, pos, facing);
            }
        }
    }

    void broadcast_leader() {
        if (!sonar_enabled || known_leader_id < 0) {
            return;
        }
        std::uint64_t const message =
            pack_leader(known_leader_id, known_leader_len, known_leader_round, known_leader_pos, known_leader_dir);
        for (Direction const direction : Direction::get_direction_list()) {
            ct.send_sonar(direction, message);
        }
    }

    bool leader_in_vision() const {
        for (int const id : ally_head_ids) {
            if (id == known_leader_id) {
                return true;
            }
        }
        return false;
    }

    bool leader_info_fresh() const {
        return leader_in_vision() || (known_leader_round >= 0 && round - known_leader_round <= FEEDER_FRESH_ROUNDS);
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

    
    
    void compute_drop_cells() {
        drop_cells.clear();
        if (known_leader_id < 0 || known_leader_id == ct.get_id()) {
            return;
        }
        Direction const facing = live_leader_dir();
        Position along = live_leader_head();
        for (int step = 1; step <= FEEDER_DROP_MAX; step++) {
            int const ahead = step_index(along, facing);
            if (ahead < 0) {
                return;
            }
            along = position_of(ahead);
            if (step < FEEDER_DROP_MIN) {
                continue;
            }
            Direction const sides[2] = {facing.get_left(), facing.get_right()};
            for (Direction const side : sides) {
                int const cell = step_index(along, side);
                if (cell < 0 || enter_time[cell] >= BLOCKED_FOREVER || pearl_here[cell]) {
                    continue;
                }
                Position const position = position_of(cell);
                if (in_leader_keep_off(position) || on_leader_ray(position)) {
                    continue;
                }
                drop_cells.push_back(cell);
            }
        }
    }

    bool on_drop_cell(Position cell) const {
        int const index = index_of(cell);
        return std::find(drop_cells.begin(), drop_cells.end(), index) != drop_cells.end();
    }

    
    void pick_feed_target() {
        bool const was_feeding = feed_id >= 0 && feed_id == known_leader_id;
        feed_index = -1;
        feed_id = -1;
        if (!USE_FEEDER_SACRIFICE || round <= ENDGAME_ROUND || known_leader_id < 0 ||
            known_leader_id == ct.get_id() || known_leader_len < 2 || length * 2 > known_leader_len ||
            ct.get_unit_count() <= FEEDER_KEEP_UNITS) {
            return;
        }
        if (manhattan(head, live_leader_head()) > FEEDER_APPROACH) {
            return;
        }
        if (!was_feeding && ct.get_id() % FEEDER_THROTTLE != (round / FEEDER_THROTTLE_PERIOD) % FEEDER_THROTTLE) {
            return;
        }
        feed_id = known_leader_id;
        int best_dist = BLOCKED_FOREVER;
        for (int const cell : drop_cells) {
            int const dist = manhattan(head, position_of(cell));
            if (dist < best_dist) {
                best_dist = dist;
                feed_index = cell;
            }
        }
        if (feed_index < 0) {
            
            feed_index = index_of(live_leader_head());
        }
    }

    
    bool blocks_leader_front(Position cell) const {
        Position const origin = live_leader_head();
        Direction const facing = live_leader_dir();
        int const along = forward_along(cell, origin, facing);
        return across_axis(cell, origin, facing) == 0 && along > 0 && along <= FEEDER_FRONT_CLEAR;
    }

    bool beside_visible_leader() const {
        return leader_in_vision() && manhattan(head, live_leader_head()) <= FEEDER_DIE_DIST &&
               !blocks_leader_front(head);
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

    
    
    
    
    void map_threats() {
        threat_mark++;
        for (std::size_t k = 0; k < enemy_heads.size(); k++) {
            int const parts = visible_parts(enemy_head_ids[k]);
            bool const small = parts < TRADE_TARGET_MIN_PARTS;
            int const reach = std::clamp(parts, THREAT_REACH_MIN, THREAT_REACH_MAX);
            visit_mark++;
            int queue_head = 0;
            int queue_tail = 0;
            int const origin = index_of(enemy_heads[k]);
            visit_stamp[origin] = visit_mark;
            step_count[origin] = 0;
            bfs_queue[queue_tail++] = enemy_heads[k];
            while (queue_head < queue_tail) {
                Position const position = bfs_queue[queue_head++];
                int const steps = step_count[index_of(position)];
                if (steps >= reach) {
                    continue;
                }
                for (Direction const direction : Direction::get_direction_list()) {
                    int const next = step_index(position, direction);
                    if (next < 0 || visit_stamp[next] == visit_mark) {
                        continue;
                    }
                    if (enter_time[next] != 0 && enter_time[next] != 2) {
                        continue;
                    }
                    visit_stamp[next] = visit_mark;
                    step_count[next] = steps + 1;
                    int const depth = reach - steps;
                    if (threat_stamp[next] != threat_mark) {
                        threat_stamp[next] = threat_mark;
                        threat_depth[next] = 0;
                        threat_depth_small[next] = 0;
                    }
                    threat_depth[next] = std::max(threat_depth[next], depth);
                    if (small && steps + 1 <= SMALL_UNIT_THREAT_REACH) {
                        threat_depth_small[next] = std::max(threat_depth_small[next], 1);
                    }
                    bfs_queue[queue_tail++] = position_of(next);
                }
            }
        }
    }

    int threat_at(int index) const {
        if (threat_stamp[index] != threat_mark) {
            return 0;
        }
        return length <= TRADE_MAX_LENGTH ? threat_depth_small[index] : threat_depth[index];
    }

    void mark_trade_targets() {
        trade_targets = 0;
        if (!USE_TRADE_ATTACK) {
            return;
        }
        bool const at_cap = ct.get_unit_count() >= std::min(gm.get_unit_limit(), SPLIT_SOFT_LIMIT) - 1;
        for (std::size_t k = 0; k < enemy_heads.size(); k++) {
            int const parts = visible_parts(enemy_head_ids[k]);
            bool const worth = parts >= length;
            if (worth) {
                trade_target_stamp[index_of(enemy_heads[k])] = round;
                trade_targets++;
            }
        }
    }

    
    bool ram_path(std::vector<Direction>& path) {
        if (!is_trader()) {
            return false;
        }
        int const reach = std::min(length - 1, RAM_MAX_STEPS);
        visit_mark++;
        int queue_head = 0;
        int queue_tail = 0;
        int const start = index_of(head);
        visit_stamp[start] = visit_mark;
        step_count[start] = 0;
        bfs_queue[queue_tail++] = head;
        while (queue_head < queue_tail) {
            Position const position = bfs_queue[queue_head++];
            int const index = index_of(position);
            int const steps = step_count[index];
            if (steps >= reach) {
                continue;
            }
            for (Direction const direction : Direction::get_direction_list()) {
                int const next = step_index(position, direction);
                if (next < 0 || visit_stamp[next] == visit_mark) {
                    continue;
                }
                if (is_trade_target_cell(next)) {
                    path.clear();
                    path.push_back(direction);
                    for (int at = index; at != start; at = bfs_parent[at]) {
                        path.insert(path.begin(), Direction(bfs_via[at]));
                    }
                    return true;
                }
                if (enter_time[next] != 0) {
                    continue;
                }
                visit_stamp[next] = visit_mark;
                step_count[next] = steps + 1;
                bfs_parent[next] = index;
                bfs_via[next] = static_cast<char>(direction.value);
                bfs_queue[queue_tail++] = position_of(next);
            }
        }
        return false;
    }

    
    bool sprint_escape(std::vector<Direction>& path) {
        if (length < SPRINT_ESCAPE_MIN_LENGTH || !chosen_scored || chosen_index < 0 || threat_at(chosen_index) == 0) {
            return false;
        }
        double best = chosen_score;
        bool found = false;
        int evals = 0;
        int const start = index_of(head);
        for (Direction const first : Direction::get_direction_list()) {
            if (edge_at(head, first) == EDGE_PORTAL) {
                continue;
            }
            int const c1 = step_index(head, first);
            if (c1 < 0 || enter_time[c1] > 1) {
                continue;
            }
            Position const p1 = position_of(c1);
            for (Direction const second : Direction::get_direction_list()) {
                if (second == first.get_opposite() || edge_at(p1, second) == EDGE_PORTAL) {
                    continue;
                }
                int const c2 = step_index(p1, second);
                if (c2 < 0 || c2 == start || threat_at(c2) > 0) {
                    continue;
                }
                
                int const free_at = enter_time[c2];
                bool const enterable = free_at == 0 || (free_at == 2 && !pearl_here[c1]);
                if (!enterable) {
                    continue;
                }
                if (evals++ >= SPRINT_ESCAPE_MAX_EVALS) {
                    return found;
                }
                double const score = score_step(position_of(c2)) - SPRINT_ESCAPE_COST;
                if (score > best) {
                    best = score;
                    path = {first, second};
                    found = true;
                }
            }
        }
        return found;
    }

    Survey survey_from(Position start, bool strict_bodies = false, bool expand_unseen = true) {
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
            bool const contest = length <= CONTEST_MAX_LENGTH && steps <= theirs + CONTEST_SLACK &&
                                 ally_race_steps(index) >= steps;
            if ((share >= 1.0 || contest) && result.dist_pearl < 0 && pearl_here[index] &&
                !in_leader_pearl_zone(index)) {
                result.dist_pearl = steps;
            }
            if (share > 0.0 && pearl_here[index] && !in_leader_pearl_zone(index)) {
                result.pearls++;
            }
            if (share >= 1.0 && result.dist_soon < 0 && seen_round[index] >= 0 && pearl_timer[index] >= 0 &&
                !in_leader_pearl_zone(index)) {
                int const spawns_in = pearl_timer[index] - (round - seen_round[index]);
                if (spawns_in <= steps + SOON_SLACK) {
                    
                    result.dist_soon = steps + std::max(0, spawns_in - steps);
                }
            }
            if (result.dist_unseen < 0 && seen_round[index] < 0) {
                result.dist_unseen = steps;
            }
            if (!expand_unseen && seen_round[index] < 0) {
                continue;
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
                    if (result.dist_trade < 0 && is_trade_target_cell(next_index)) {
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

    bool can_step_to(std::vector<Position> const& heads, Position cell) const {
        int const dest = index_of(cell);
        for (Position const& origin : heads) {
            for (Direction const direction : Direction::get_direction_list()) {
                if (step_index(origin, direction) == dest) {
                    return true;
                }
            }
        }
        return false;
    }

    bool enemy_can_step_to(Position cell) const { return can_step_to(enemy_heads, cell); }

    bool is_ally_head(Position position) const {
        for (Position const& ally : ally_heads) {
            if (ally == position) {
                return true;
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

    bool is_trade_target_cell(int index) const { return trade_target_stamp[index] == round; }
    bool is_leader() const {
        return round > LEADER_GROW_ROUND && known_leader_id == ct.get_id();
    }

    bool is_trader() const {
        return USE_TRADE_ATTACK && round <= ENDGAME_ROUND && length <= TRADE_MAX_LENGTH && !is_leader() &&
               ct.get_unit_count() >= TRADE_MIN_UNITS && trade_targets > 0;
    }

    bool can_scout_portals() const {
        
        return USE_PORTALS && USE_PORTAL_SCOUT && length <= PORTAL_SCOUT_MAX_LENGTH && !is_feeder() &&
               !is_leader() && tail_index >= 0;
    }

    bool leads_to_unknown(Position position, Direction direction) const {
        return edge_at(position, direction) == EDGE_PORTAL && portal_exit(position, direction) < 0;
    }

    bool is_feeder() const {
        return USE_FEEDER_SACRIFICE && feed_index >= 0;
    }

    bool ready_to_die() const {
        if (!is_feeder()) {
            return false;
        }
        for (Position const& enemy : enemy_heads) {
            if (manhattan(head, enemy) <= FEEDER_ENEMY_CLEAR) {
                return false;
            }
        }
        return (on_drop_cell(head) && leader_info_fresh()) || beside_visible_leader();
    }

    double score_step(Position destination) {
        Survey const survey = survey_from(destination);

        double const room = survey.area_seen + UNSEEN_DISCOUNT * survey.area_unseen;
        double const territory = survey.own_seen + UNSEEN_DISCOUNT * survey.own_unseen;
        last_room = room;
        last_seen_room = survey.area_seen;
        last_reaches_tail = survey.reaches_tail;
        double const space = WEIGHT_SPACE * room + WEIGHT_TERRITORY * territory;

        double const room_wanted = 3.0 * length + 8.0;
        double cramped = 0.0;
        if (room < room_wanted) {
            cramped += PENALTY_TIGHT * (room_wanted - room);
        }
        if (room < length + 2.0) {
            cramped += PENALTY_TRAPPED * (length + 2.0 - room);
        }
        if (tail_index >= 0 && !survey.reaches_tail) {
            cramped += PENALTY_NO_TAIL;
        }
        last_space = space;
        last_cramped = cramped;
        last_pearls = survey.pearls;
        last_dead_end = tail_index >= 0 && !survey.reaches_tail && room < room_wanted;
        double score = space - cramped;

        double const pearl_weight = is_leader() && round > ENDGAME_ROUND ? WEIGHT_PEARL * LEADER_ENDGAME_PEARL_MULT
                                                                          : WEIGHT_PEARL;
        last_bonus = std::max({target_bonus(survey.dist_pearl, pearl_weight),
                               target_bonus(survey.dist_soon, WEIGHT_SOON),
                               target_bonus(survey.dist_unseen, WEIGHT_UNSEEN),
                               target_bonus(survey.dist_portal, WEIGHT_PORTAL_SCOUT)});
        score += last_bonus;

        if (!is_leader() && pearl_here[index_of(destination)] && in_leader_pearl_zone(index_of(destination))) {
            score -= ZONE_PEARL_PENALTY;
        }
        if (AVOID_ALLY_HEADS && can_step_to(ally_heads, destination)) {
            score -= PENALTY_ENEMY_HEAD;
        }
        if (!is_trader()) {
            int const depth = threat_at(index_of(destination));
            if (depth > 0) {
                double penalty = PENALTY_HEAD_RACE * std::max(0.5, length / THREAT_LENGTH_SCALE) * (0.5 + 0.5 * depth);
                if (is_leader()) {
                    penalty *= LEADER_HEAD_MULT;
                }
                score -= penalty;
            }
        }

        if (is_feeder() && survey.dist_feed >= 0) {
            score += std::max(0.0, FEEDER_REWARD - FEEDER_DECAY * survey.dist_feed);
        }
        if (is_trader() && survey.dist_trade >= 0) {
            score += std::max(0.0, TRADE_REWARD - TRADE_DECAY * survey.dist_trade);
        }
        return score;
    }

    
    double score_portal_step(Direction direction, bool& usable) {
        usable = false;
        if (!USE_PORTALS) {
            return SCORE_PORTAL;
        }
        int const exit = portal_exit(head, direction);
        if (exit >= 0 && enter_time[exit] > 1) {
            return SCORE_REJECT;
        }
        if (exit < 0) {
            return SCORE_PORTAL;
        }
        double const score = score_step(position_of(exit)) - PORTAL_LEAP_PENALTY;
        if (length > PORTAL_SCOUT_MAX_LENGTH && last_seen_room < length + PORTAL_SAFETY_MARGIN) {
            return SCORE_PORTAL;
        }
        usable = true;
        return score;
    }

    Direction pick_direction() {
        Direction best = dir_of(Direction::NORTH);
        double best_score = SCORE_REJECT * 2.0;
        chosen_room = 0.0;
        chosen_scored = false;
        chosen_reaches_tail = false;
        chosen_index = -1;
        chosen_score = SCORE_REJECT * 2.0;
        any_enterable = false;
        chosen_pearls = 0;
        chosen_harvest = false;

        auto const directions = Direction::get_direction_list();
        std::array<double, 4> scores{};
        std::array<double, 4> rooms{};
        std::array<bool, 4> blind{};
        std::array<bool, 4> scored{};   
        std::array<bool, 4> reaches{};
        std::array<int, 4> dests{};
        dests.fill(-1);
        std::array<double, 4> spaces{};
        std::array<double, 4> others{};
        std::array<int, 4> pearls{};
        std::array<bool, 4> dead{};
        std::array<bool, 4> harvest{};
        double best_open_space = SCORE_REJECT;
        std::array<bool, 4> closed{};
        std::array<bool, 4> imminent{};
        double best_base = SCORE_REJECT;
        bool const scouting = can_scout_portals();

        for (std::size_t k = 0; k < directions.size(); k++) {
            Direction const direction = directions[k];
            std::uint8_t const edge = edge_at(head, direction);
            double score = SCORE_REJECT;

            last_room = 0.0;
            last_reaches_tail = false;
            if (edge == EDGE_PORTAL) {
                bool usable = false;
                score = score_portal_step(direction, usable);
                dests[k] = usable ? portal_exit(head, direction) : -1;
                scored[k] = usable;
                any_enterable = any_enterable || usable;
                blind[k] = scouting && !usable && leads_to_unknown(head, direction);
            } else if (edge != EDGE_KELP) {
                Position const destination = head.add_dir(direction);
                dests[k] = index_of(destination);
                bool const enterable = enter_time[index_of(destination)] <= 1;
                any_enterable = any_enterable || enterable;
                if (is_feeder() && (in_leader_keep_off(destination) || on_leader_ray(destination))) {
                    score = SCORE_REJECT;
                } else if (enterable) {
                    score = score_step(destination);
                    scored[k] = true;
                    best_base = std::max(best_base, score - last_bonus);
                    spaces[k] = last_space;
                    others[k] = score - last_space + last_cramped - last_bonus;
                    pearls[k] = last_pearls;
                    dead[k] = last_dead_end;
                    closed[k] = !last_reaches_tail && last_room < length + 2.0;
                    if (!last_dead_end) {
                        best_open_space = std::max(best_open_space, last_space);
                    }
                } else if (is_enemy_head(destination)) {
                    score = is_trader() && is_trade_target_cell(index_of(destination)) ? TRADE_REWARD
                                                                                      : SCORE_REJECT * 0.5;
                } else if (is_ally_head(destination)) {
                    
                    score = SCORE_REJECT * 1.5;
                }
            }
            scores[k] = score;
            rooms[k] = last_room;
            reaches[k] = last_reaches_tail;
        }

        
        
        for (std::size_t k = 0; k < directions.size(); k++) {
            if (dead[k] && scores[k] > SCORE_REJECT * 0.5 &&
                harvestable(pearls[k], rooms[k], best_open_space <= SCORE_REJECT * 0.5)) {
                double const space = best_open_space > SCORE_REJECT * 0.5 ? best_open_space : spaces[k];
                scores[k] = space + others[k] +
                            HARVEST_SEGMENT_VALUE * (pearls[k] - unswbc::Constants::MIN_SIZE);
                harvest[k] = true;
            }
        }

        cornered = false;
        if (length >= LONG_SAFE_MIN_LENGTH) {
            std::array<int, 4> level{};
            level.fill(-2);
            int best_level = -2;
            bool any_scored = false;
            bool all_imminent = true;
            for (std::size_t k = 0; k < directions.size(); k++) {
                if (!scored[k] || dests[k] < 0 || scores[k] <= SCORE_REJECT * 0.5) {
                    continue;
                }
                any_scored = true;
                imminent[k] = enemy_can_step_to(position_of(dests[k]));
                all_imminent = all_imminent && imminent[k];
                level[k] = closed[k] || dead[k] ? -1 : std::min(rival_steps(dests[k]), SPRINT_THREAT_REACH + 1);
                best_level = std::max(best_level, level[k]);
            }
            for (std::size_t k = 0; k < directions.size(); k++) {
                if (level[k] > -2 && level[k] < best_level) {
                    scores[k] -= LONG_THREAT_VETO * (best_level - level[k]);
                }
            }
            cornered = any_scored && all_imminent && length >= DODGE_MIN_LENGTH;
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
                chosen_scored = scored[k];
                chosen_reaches_tail = reaches[k];
                chosen_index = dests[k];
                chosen_score = score;
                chosen_pearls = pearls[k];
                chosen_harvest = harvest[k];
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
    std::vector<int> dirty;
    std::vector<Position> other_heads;
    std::vector<Position> ally_heads;
    std::vector<int> ally_head_ids;
    std::vector<Direction> ally_head_dirs;
    std::vector<int> seen_ids;
    std::vector<int> seen_parts;
    std::vector<int> drop_cells;
    int feed_index = -1;
    int feed_id = -1;
    int known_leader_id = -1;
    int known_leader_len = 0;
    int known_leader_round = -1;
    std::uint64_t sonar_tag = 0x2;
    bool sonar_enabled = false;
    Position known_leader_pos{};
    Direction known_leader_dir = dir_of(Direction::NORTH);
    bool zone_active = false;
    Position zone_head{};
    std::vector<Position> enemy_heads;
    std::vector<int> enemy_head_ids;
    std::vector<int> trade_target_stamp;
    int trade_targets = 0;
    std::vector<int> threat_stamp;
    std::vector<int> threat_depth;
    std::vector<int> threat_depth_small;
    int threat_mark = 0;
    std::vector<int> bfs_parent;
    std::vector<char> bfs_via;
    std::vector<Position> pending_path;
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
    double chosen_score = 0.0;
    int chosen_index = -1;
    bool chosen_scored = false;
    bool chosen_reaches_tail = false;
    bool any_enterable = false;
    double last_room = 0.0;
    double last_bonus = 0.0;
    double last_space = 0.0;
    double last_cramped = 0.0;
    int last_pearls = 0;
    bool last_dead_end = false;
    int chosen_pearls = 0;
    bool chosen_harvest = false;
    bool harvesting_now = false;
    bool cornered = false;
    int harvest_round = -1;
    int behind_round = -1;
    double behind_room = 0.0;
    double last_seen_room = 0.0;
    bool last_reaches_tail = false;

    std::vector<int> visit_stamp;
    std::vector<int> step_count;
    std::vector<int> eaten_count;
    std::vector<Position> bfs_queue;
    int visit_mark = 0;
};


Direction fallback_direction(unswbc::Controller const& controller) {
    Position const here = controller.get_position();
    auto const* here_tile = controller.get_tile(here);
    for (Direction const direction : Direction::get_direction_list()) {
        if (here_tile && !here_tile->get_edge(direction).is_passable()) {
            continue;
        }
        if (here_tile && here_tile->get_edge(direction).is_portal()) {
            continue;
        }
        auto const* ahead = controller.get_tile(here.add_dir(direction));
        if (ahead && !ahead->get_dragon()) {
            return direction;
        }
    }
    return Direction(Direction::NORTH);
}

}

int main() {
    auto [controller, game] = unswbc::init();
    Bot bot(controller, game);

    while (unswbc::update(controller, game)) {
        try {
            bot.take_turn();
        } catch (...) {
            controller.make_move(fallback_direction(controller));
        }
        unswbc::end_turn();
    }
}