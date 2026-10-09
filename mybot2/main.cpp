#include "helper.hpp"
#include "sonar_codec.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <deque>
#include <set>
#include <tuple>
#include <vector>

namespace {

using unswbc::Direction;
using unswbc::EdgeType;
using unswbc::Position;

constexpr int BLOCKED_FOREVER = 1 << 28;

constexpr bool DEBUG_LOG = false;
constexpr int TIE_SEED = 0;
constexpr double HEADING_TIE = 0.0;
constexpr int HEADING_TIE_ROUNDS = 0;

constexpr double CONTESTED_SHARE = 0.5;
constexpr double PENALTY_HEAD_RACE = 450.0;
constexpr int THREAT_REACH_MIN = 2;
constexpr int THREAT_REACH_MAX = 6;
constexpr double THREAT_LENGTH_SCALE = 4.0;
constexpr int SMALL_UNIT_THREAT_REACH = 1;
constexpr int SPRINT_ESCAPE_MIN_LENGTH = 8;
constexpr double SPRINT_ESCAPE_COST = 400.0;
constexpr int SPRINT_ESCAPE_MAX_EVALS = 4;
constexpr int BIG_ESCAPE_STEPS = 0;
constexpr int BIG_ESCAPE_MIN_LENGTH = 15;
constexpr int BIG_ESCAPE_EVALS = 6;
constexpr bool BIG_ESCAPE_LATE = false;
constexpr int BIG_TRUE_REACH = 0;
constexpr int BIG_TRUE_MARGIN = 1;

constexpr int SPLIT_LAST_ROUND = 495;
constexpr int SPLIT_MIN_LENGTH = 4;
constexpr bool SPLIT_PORTAL_OK = false;
constexpr int SPLIT_SOFT_LIMIT = 60;

constexpr int ENDGAME_ROUND = 400;
constexpr int LEADER_GROW_ROUND = 300;
constexpr int LEADER_GROW_ROUND_BIG = 150;
constexpr int FEEDER_KEEP_UNITS = 3;
constexpr int FEEDER_APPROACH = 15;
constexpr bool FD_APPROACH_SCALE = false;
constexpr int FD_APPROACH_BASE_SPAN = 100;
constexpr int FD_APPROACH_DIV = 4;
constexpr bool FD_RALLY_BIG = false;
constexpr int FD_RALLY_FRESH = 25;
constexpr int FEEDER_DROP_MIN = 4;
constexpr int FEEDER_DROP_MAX = 8;
constexpr int FEEDER_KEEP_OFF = 2;
constexpr int LEADER_PEARL_RADIUS = 9;
constexpr int SONAR_STALE = 25;

constexpr int FEEDER_FRESH_ROUNDS = 5;

constexpr int FEEDER_DIE_DIST = 3;
constexpr int FEEDER_FRONT_CLEAR = 3;
constexpr int FEEDER_ENEMY_CLEAR = 4;
constexpr double ZONE_PEARL_PENALTY = 600.0;
constexpr bool ZONE_NEARER = false;
constexpr bool FEEDER_EAT = false;
constexpr bool SPLIT_ROUND0 = false;
constexpr bool EAT_BEFORE_SPLIT = false;
constexpr bool CRAMPED_EAT = false;
constexpr int QUEEN_SURE_LEN = 0;
constexpr int QUEEN_SURE_STEPS = 3;

constexpr double LEADER_ENDGAME_PEARL_MULT = 4.0;

constexpr int FEED_CAP_UNITS = 56;
constexpr int FEED_CAP_ROUND = 200;

constexpr double ROUTE_VETO = 2500.0;
constexpr double ROUTE_OVERRIDE = 1e7;


constexpr bool BARREN_ESCAPE = true;
constexpr int BARREN_MIN_SEEN = 40;
constexpr double BARREN_MAX_SPAWN = 0.06;
constexpr int BARREN_REGION_CAP = 600;
constexpr int BARREN_ROUNDS = 100;
constexpr double FEEDER_REWARD = 3000.0;
constexpr double FEEDER_DECAY = 60.0;
constexpr double LEADER_HEAD_MULT = 2.0;

constexpr int TRADE_MAX_LENGTH = 4;
constexpr int TRADE_MIN_UNITS = 8;

constexpr int TRADE_TARGET_MIN_PARTS = 5;

constexpr int RAM_MAX_STEPS = 4;
constexpr int AGGRESSIVE_MAX_CELLS = 1200;
constexpr int AGGRESSIVE_TRADE_MIN_UNITS = 1;
constexpr int AGGRESSIVE_RAM_MAX_STEPS = 3;
constexpr int TRADE_LOCAL_EDGE = 1;
constexpr int TRADE_SHORT_BY = 0;
constexpr bool LUNGE_PEARL = false;
constexpr int ATTACK_MIN_UNITS = 0;
constexpr int DEFEND_MIN_PARTS = 10;
constexpr int DEFEND_RADIUS = 6;
constexpr double TRADE_REWARD = 2500.0;
constexpr double TRADE_DECAY = 80.0;
constexpr double EAT_BONUS = 300.0;
constexpr bool EAT_FIRST = false;
constexpr int LOOK_DEPTH = 8;
constexpr bool QUEEN_MODE = true;
constexpr int QUEEN_SPLIT_ROUND = 200;
constexpr int QUEEN_SPLIT_CLEAR = 0;
constexpr int QUEEN_LEAD_BONUS = 1000;
constexpr bool QUEEN_PESSIMIST = false;
constexpr double QUEEN_THREAT_MULT = 1.0;
constexpr int QUEEN_REACH_MAX = 8;
constexpr int QUEEN_GUARD_RADIUS = 0;
constexpr double QUEEN_GUARD_PENALTY = 1500.0;
// Card #36: queen dead-end penalty and room margin, tail out of sight counts as unreachable, known-tile room check.
constexpr bool QUEEN_DEAD_END = true;
constexpr double QUEEN_DEAD_PENALTY = QUEEN_DEAD_END ? 6000.0 : 0.0;
constexpr double QUEEN_KNOWN_STEP = 400.0;
constexpr int QUEEN_DEFEND_RADIUS = 0;
constexpr int QUEEN_DEFEND_STEPS = 0;
constexpr int QUEEN_HUNT_STEPS = 12;
constexpr int QUEEN_CHASE_DIST = 0;
constexpr int QUEEN_AVENGE = 0;
constexpr int QUEEN_WAR = 0;
constexpr bool WAR_FEED_FIRST = false;
constexpr int QUEEN_CHASE_FRESH = 8;
constexpr int SPRINT_FREE_DIV = 4;
constexpr bool STRIDE = true;
constexpr double STRIDE_MARGIN = -50;
constexpr int STRIDE_BUDGET = 12000;
constexpr int STRIDE_CAP = 1500;
constexpr bool QUEEN_WAIT = true;
constexpr int QW_MIN_LENGTH = 4;
constexpr bool QW_ANY_BLOCK = true;
constexpr int QW_END_ROOM = 0;
constexpr bool QW_LOG = false;
constexpr bool QUEEN_SAFETY = true;
constexpr double QS_THREAT_MULT = 4.0;
constexpr double QS_HIT_PENALTY = 3e8;
constexpr double QS_PAY_PENALTY = 2e8;
constexpr int QS_PAY_REACH = 3;
constexpr int QUEEN_FAR_HEADS = 0;
constexpr int QUEEN_EDGE_REACH = 0;
constexpr int CUT_BODY_LEN = 0;
constexpr bool CUT_BODY_STRIDE = false;
constexpr bool REACH_EATS = false;
constexpr int QS_ESCAPE_EVALS = 6;
constexpr int QS_KEEP_LEN = 0;
constexpr int QS_KEEP_MIN_UNITS = 0;
constexpr int QS_KEEP_ROUND = 0;
constexpr int QS_KEEP_CLEAR = 0;
constexpr bool QUEEN_DEAD_ALL = false;
constexpr bool QUEEN_EXIT_KEEP = false;
constexpr bool QUEEN_EXIT_STRICT = false;
constexpr bool MATE_UNPIN = false;
constexpr bool POCKET_KEEP_OUT = false;
constexpr int QUEEN_CORRIDOR_GUARD = 0;
constexpr bool SHORT_EVADE = false;
constexpr int SHORT_EVADE_PAID = 0;
constexpr bool SHORT_EVADE_ANY = false;
constexpr bool PORTAL_ID_GUARD = false;
// Card #54: dragons of LS_MIN_LENGTH+ take the queen's ring veto; an enemy reaches its free steps plus LS_PAY_STEPS paid.
constexpr bool LONG_SAFETY = false;
constexpr int LS_MIN_LENGTH = 31;
constexpr int LS_PAY_STEPS = 1;
constexpr int LS_ESCAPE_COST = 2;
constexpr int STRIDE_MAX = 6;
constexpr bool STRIDE_SEEN = true;
constexpr bool STRIDE_SAFE_END = true;
constexpr int STRIDE_SAFE_RADIUS = 2;
constexpr int STRIDE_SAFE_UNSEEN = 4;
constexpr bool TURN_DIST = false;
constexpr bool SHARE_SIGHT = false;
constexpr int CELL_BUDGET = 12000;
constexpr bool QUEEN_HUNT = false;
constexpr int QUEEN_KEEP = 0;
constexpr bool QUEEN_DEFEND_LATE = false;
constexpr bool QUEEN_NO_PORTAL = true;
constexpr int QUEEN_PORTAL_ROUND = 0;
constexpr bool QUEEN_LEAD_LATE = true;
constexpr int QUEEN_LEAD_ROUND = 0;
constexpr int QUEEN_QUIET_ROUND = 100;
constexpr int QUEEN_GAME_FEED_ROUND = 300;
constexpr int QUEEN_SAFE_ROUND = 300;
constexpr int QUEEN_SAFE_SPAN = 0;
constexpr bool QUEEN_PORTAL_ALL = false;
constexpr bool QUEEN_PORTAL_LAST = false;
constexpr bool QUEEN_HOME_CLOSED = true;
// Card #48: the queen takes no feeding role on any map (feeder, local drop, rally, assassin, endgame hunt).
constexpr bool QUEEN_NO_FEED = true;
constexpr int QUEEN_HUNT_MAX_LEN = 0;
constexpr int HOME_CHECK_ROUND = 200;
constexpr double HOME_MAX_FRAC = 0.5;
constexpr int HOME_MIN_CELLS = 40;
constexpr bool QUEEN_TRADE_SMALL = false;
constexpr int QUEEN_MIN_CELLS = 600;
constexpr bool SYM_INFER = false;
constexpr int SURVEY_CAP = 0;
constexpr int QUEEN_ROOM = QUEEN_DEAD_END ? 8 : 0;
constexpr bool QUEEN_ALLY_BLOCK = false;
constexpr int ALLY_BLOCK_MAX_LEN = 0;
constexpr int POCKET_CAP = 48;
constexpr int POCKET_DIV = 2;
constexpr double POCKET_PENALTY = 1000.0;
constexpr bool POCKET_LOOP = false;
constexpr int NO_TAIL_ROOM = 0;
constexpr bool CENTER_PATH = false;
constexpr int QUEEN_GUARD_CELLS = 0;
constexpr bool POCKET_PORTAL_BAN = false;
constexpr double QG_THREAT_MULT = 6.0;
constexpr bool QG_PESSIMIST = true;
constexpr int QG_GUARD_RADIUS = 5;
constexpr double QG_DEAD_PENALTY = 6000.0;
constexpr int QG_SPLIT_CLEAR = 6;
constexpr int QG_KEEP = 0;
constexpr int QG_HOME_RADIUS = 0;
constexpr double QG_HOME_PENALTY = 60.0;
constexpr int QUEEN_HOME_LEASH = 0;
constexpr double QUEEN_HOME_SLOPE = 150.0;
constexpr bool QUEEN_HERD = false;
constexpr double HERD_PULL = 120.0;
constexpr int HERD_MIN_UNITS = 12;
constexpr double HERD_BEHIND = 0.0;
constexpr bool QG_SAFEZONE = false;
constexpr int QG_SAFEZONE_CHECKS = 2;
constexpr int QG_SAFEZONE_GAP = 4;
constexpr int QG_SAFEZONE_ROOM = 3;
constexpr double QG_SAFEZONE_FRAC = 0.1;
constexpr double QG_SAFEZONE_PENALTY = 3000.0;
constexpr int QG_SAFEZONE_PROBE = 12;
constexpr bool QG_SAFEZONE_LOG = false;
constexpr bool QG_CORNER = false;
constexpr int QG_CORNER_RADIUS = 2;
constexpr int QG_CORNER_REACH = 40;
constexpr int QG_CORNER_DANGER = 4;
constexpr int QG_CORNER_EVERY = 10;
constexpr double QG_CORNER_PENALTY = 1000.0;
constexpr bool QG_CORNER_LOG = false;
constexpr int QUEEN_GIVE_WAY = 0;
constexpr double QUEEN_GIVE_WAY_PENALTY = 3000.0;
constexpr bool QUEEN_BRAIN = false;
constexpr int QB_MAX_STEPS = 5;
constexpr int QB_MAX_PAID = 2;
constexpr int QB_REACH_CAP = 6;
constexpr int QB_MARGIN_CAP = 3;
constexpr int QB_GHOST_AGE = 3;
constexpr int QB_SPLIT_MARGIN = 2;
constexpr int QB_ROOM = 10;
constexpr int QB_EVAL_MAX = 800;
constexpr int QB_BFS_CAP = 80;
constexpr double QB_W_MARGIN = 3000.0;
constexpr double QB_W_ROOM = 4000.0;
constexpr double QB_DEAD = 8000.0;
constexpr double QB_W_TAIL = 1000.0;
constexpr double QB_W_OPT = 800.0;
constexpr double QB_W_UNSEEN = 300.0;
constexpr double QB_W_EAT = 1500.0;
constexpr double QB_W_PAID = 1200.0;
constexpr double QB_W_PEARL = 150.0;
constexpr double QB_W_ALLY = 1000.0;
constexpr bool QB_TIMED_ROOM = false;
constexpr double QB_W_DANGER = 0.0;
constexpr int QB_DANGER_ROUNDS = 20;
constexpr int QB_DANGER_RADIUS = 6;
constexpr double QB_W_ESCORT = 0.0;
constexpr int QB_ESCORT_RADIUS = 5;
constexpr bool QB_ROBUST_EXITS = false;
constexpr double QB_ONE_EXIT = 4000.0;
constexpr double LOOK_PEARL = 80.0;
constexpr double LOOK_DISCOUNT = 0.85;
constexpr double LOOK_SOON = 0.5;
constexpr int LEADER_GUARD_ROUNDS = 0;
constexpr int LEADER_GUARD_RADIUS = 6;
constexpr double LEADER_GUARD_PENALTY = 2000.0;
constexpr bool UNSEEN_CLAIM = false;
constexpr bool HARVEST_SPLIT = false;
constexpr bool HARVEST_PORTAL = false;
constexpr bool TARGET_REACHABLE = false;
constexpr bool SPAWN_CLEAR = false;
constexpr int SPAWN_CLEAR_MAX = 4;
constexpr bool SPAWN_CLEAR_ALL = false;
constexpr double SPAWN_CLEAR_PENALTY = 300.0;
constexpr int FEED_BOOT_LEN = 0;
constexpr int QUEEN_BOOT_LEN = 0;
constexpr double PEARL_FAR_DECAY = 0.0;
constexpr bool SMALL_SPRINT_THREAT = false;
constexpr double SMALL_THREAT_MULT = 1.0;
constexpr bool HOT_FAST = false;
constexpr bool BARREN_BY_RATE = false;
constexpr bool BARREN_KNOWN = false;
constexpr bool NO_REVERSE = false;
constexpr int RALLY_FRESH = 0;
constexpr int RALLY_END_FRESH = 0;
constexpr int LC_LEAD_ROUND = 0;
constexpr int LC_FEED_ROUND = 0;
constexpr double LC_LEAD_MULT = 1.0;
constexpr int LC_ENEMY_LEAD = 0;
constexpr int LC_ENEMY_FEED = 0;
constexpr int ASSASSIN_MOD = 0;
constexpr int ASSASSIN_MIN = 4;
constexpr int ASSASSIN_MAX = 6;
constexpr int ASSASSIN_TARGET = 8;
constexpr int ASSASSIN_FRESH = 30;
constexpr double CROWD_MARGIN = 0.0;
constexpr int CORPSE_SLACK = 0;
constexpr int CORPSE_FRESH = 15;
constexpr int STAFF_CELLS = 16;
constexpr int STAFF_REGION_MAX = 120;
constexpr int IDLE_ESCAPE = 0;
constexpr int IDLE_REGION_MAX = 40;
constexpr bool IDLE_STRICT = false;
constexpr int IDLE_LOG = 0;
constexpr double FAR_GAIN = 2;
constexpr int FAR_RANGE = 80;
constexpr int FAR_IDLE = 0;
constexpr double EXPLORE_GAIN = 0.0;
constexpr int EXPLORE_RANGE = 60;
constexpr int EXPLORE_ROUNDS = 200;
constexpr int FEED_LOCAL = 0;
constexpr int FEED_LOCAL_MIN = 4;
constexpr int FEED_EARLY_ROUND = 0;
constexpr int FEED_EARLY_MAX = 2;
constexpr bool TRADE_EVEN = false;
constexpr int LEADER_FULL_UNITS = 0;
constexpr int LEADER_FULL_KEEP = 10;
constexpr int INC_PERIOD = 0;
constexpr int INC_RADIUS = 30;
constexpr double INC_HOT_RATE = 1.0;
constexpr double INC_SPAWN_RATE = 0.05;
constexpr double INC_PEARL_RATE = 0.3;
constexpr double INC_DIST_W = 0.03;
constexpr double INC_MARGIN = 0.5;
constexpr int INC_ALLY_MEMORY = 10;
constexpr int INC_MAX_LENGTH = 6;
constexpr double HOT_FAR_DECAY = 0.0;
constexpr bool SMALL_THREAT_OUTNUMBERED = false;
constexpr double PORTAL_FAR_DECAY = 0.0;
constexpr int PORTAL_FAR_ROUNDS = 0;
constexpr int HUNT_MIN_PARTS = 10;
constexpr int HUNT_MARGIN = 4;
constexpr int HUNT_SMALL_RATIO = 0;
constexpr int HUNT_MAX_LENGTH = 10;
constexpr int HUNT_MAX_STEPS = 8;
constexpr bool HUNT_GUARD = true;
constexpr int END_HUNT_MIN_PARTS = 6;
constexpr int END_HUNT_RATIO = 2;
constexpr int FEED_LEN_RATIO = 2;

constexpr int ESCAPE_MIN_LENGTH = 4;
constexpr int ESCAPE_TAIL_CLEAR = 2;
constexpr double ESCAPE_ROOM_MAX = 4.0;
constexpr double ESCAPE_MARGIN = 4.0;

constexpr double HARVEST_SEGMENT_VALUE = 150.0;

constexpr int HARVEST_MIN_NET = 1;

constexpr int HARVEST_MAX_LENGTH = 6;
constexpr int HARVEST_INSIDE_SLACK = 2;

constexpr int LONG_SAFE_MIN_LENGTH = 8;
constexpr double LONG_THREAT_VETO = 1e6;
constexpr int DODGE_MIN_LENGTH = 12;
constexpr int BIG_GUARD_MIN_LENGTH = 15;
constexpr int BIG_REACH_BONUS = 2;
constexpr int BIG_SPRINT_EVALS = 8;
constexpr int GHOST_ROUNDS = 3;
constexpr int BIG_DEAD_LEVEL = 2;

constexpr int CONTEST_MAX_LENGTH = 4;
constexpr int CONTEST_SLACK = 1;
constexpr double CHILD_MIN_ROOM = 4.0;
constexpr int ESCAPE_RESERVE = 2;

constexpr int SONAR_COORD_MAX = 127;

constexpr int PORTAL_NONE = -1;
constexpr int PORTAL_UNKNOWN = -2;
constexpr int PORTAL_SCOUT_MAX_LENGTH = 6;
constexpr double PORTAL_SAFETY_MARGIN = 6.0;
constexpr int PORTAL_GUARD_LENGTH = 10;
constexpr int PORTAL_GUARD_ENEMY_CLEAR = 4;
constexpr int PORTAL_GUARD_LEADER_MIN = 6;

constexpr std::uint8_t EDGE_UNKNOWN = 0;
constexpr std::uint8_t EDGE_OPEN = 1;
constexpr std::uint8_t EDGE_KELP = 2;
constexpr std::uint8_t EDGE_PORTAL = 3;

constexpr double WEIGHT_SPACE = 1.5;
constexpr double WEIGHT_TERRITORY = 1.5;
constexpr double UNSEEN_DISCOUNT = 0.5;
constexpr double TERRITORY_DECAY = 0.0;
constexpr double BARREN_TERRITORY = 0.3;
constexpr double TERRITORY_TIME_SCALE = 80.0;
constexpr double RATE_EXP = 0.0;
constexpr double RATE_REF_GAP = 100.0;
constexpr double RATE_CAP = 4.0;
constexpr double PENALTY_TIGHT = 400.0;
constexpr double PENALTY_TRAPPED = 5000.0;
constexpr double TARGET_REWARD = 260.0;
constexpr double TARGET_DECAY = 40.0;
constexpr double WEIGHT_PEARL = 2.0;
constexpr double WEIGHT_SOON = 0.45;

constexpr int SOON_SLACK = 6;
constexpr int HOT_TIMER = 4;
constexpr int HOT_MIN_GAP = 6;
constexpr int HOT_MAX_GAP = 25;
constexpr int HOT_FALSE_TIMER = 8;
constexpr int HOT_ENEMY_SLACK = 1;
constexpr double WEIGHT_HOT = 1.2;
constexpr double CENTER_PULL = 40.0;
constexpr int CENTER_ROUNDS = 60;
constexpr int CENTER_MAX_LENGTH = 4;
constexpr int CENTER_MAX_CELLS = 1000;
constexpr int CENTER_SMALL_CELLS = 700;
constexpr int CENTER_SMALL_ROUNDS = 30;
constexpr int CENTER_OUTNUMBER_MARGIN = 0;
constexpr bool TR_CENTER_ORIENT = false;
constexpr bool TR_STALL_RELEASE = true;
constexpr int TR_STALL_ROUNDS = 12;
constexpr int TR_STALL_ROOM = 6;
constexpr int TR_STALL_SEEK = 30;
// Card #55: outnumbered (herself counted, a draw counts, enemy heads of the last GHOST_ROUNDS rounds too), the queen
// falls back to a spot where she lately saw more of ours than theirs; to her start tile only when she remembers none.
constexpr bool QUEEN_FALLBACK = false;
constexpr int QF_GUARD_RADIUS = 5;
constexpr int QF_MEMORY = 40;
constexpr int QF_HOLD = 2;
constexpr int QF_SPOTS = 4;
constexpr int QF_MERGE = 6;
constexpr int QF_CROWD = 3;
constexpr double QF_PULL = 30000.0;
constexpr double QF_TIE_PULL = 300.0;
constexpr int QF_TIE_SPAN = 2;
constexpr bool QH_SCOUT = true;
constexpr int QH_MAX_LEN = 4;
constexpr int QH_REVENGE_ROUND = 100;
constexpr int QH_QUIET = 20;
constexpr int QH_FRESH = 20;
constexpr int QH_SPAWN_SLACK = 2;
constexpr std::uint64_t QH_PING_KIND = 0x2B5;
constexpr bool SN_TAIL_MOUTH = true;
constexpr double WEIGHT_UNSEEN = 0.20;
constexpr double PENALTY_NO_TAIL = 600.0;
constexpr double PENALTY_ENEMY_HEAD = 450.0;
constexpr double SCORE_PORTAL = -1e9;

constexpr double PORTAL_LEAP_PENALTY = 150.0;
constexpr double PORTAL_LEAP_SMALL = 0.0;
constexpr int BOX_MAX_CELLS = 40;
constexpr double WEIGHT_PORTAL_SCOUT = 0.40;
constexpr int PORTAL_SCOUT_MIN_LEN = 0;
constexpr double SCORE_REJECT = -1e15;

struct Ghost {
    int id = -1;
    Position pos{};
    int round = -1;
    int parts = 0;
    bool shared = false;
    char face = 0;
};

// Card #54: an enemy's size as this dragon has seen it, kept all game.
struct Foe {
    int id = -1;
    int whole = 0;  // most parts with its whole body in view
    int most = 0;   // most parts in one round
    int last = 0;   // parts at the last sighting
    bool cut = false;  // its body ran out of view then
    int round = -1;
};

struct Mate {
    int id = -1;
    int cell = -1;
    int round = -1;
};

struct Herd {
    bool on = false;
    std::vector<Mate> mates;
    std::vector<int> dist;
    std::vector<int> queue;
    std::vector<std::pair<int, int>> foes;
    int ahead = 0;
};

struct Spot {
    int cell = -1;
    int margin = 0;
    int round = -1;
};

struct StrideEnd {
    double room = 0.0;
    bool reaches_tail = false;
    bool pearl = false;
    int eaten = 0;
};

struct StrideRisk {
    int reach = 0;
    int unseen = 0;
    int shut = 0;
};

struct Survey {
    int area_seen = 0;
    int area_unseen = 0;
    double own_seen = 0;
    double own_unseen = 0;
    int dist_pearl = -1;
    int dist_soon = -1;
    int dist_hot = -1;
    int dist_unseen = -1;
    int dist_feed = -1;
    int dist_route = -1;
    int dist_trade = -1;
    int dist_portal = -1;
    int pearls = 0;
    bool reaches_tail = false;
    double ally_load = 0.0;
};

struct ShortEvade {
    std::unordered_map<int, int> lengths;
    std::array<double, 4> scores{};
    std::array<int, 4> dests{};
    std::array<bool, 4> open{};
    bool attack = false;
};

struct PocketChoice {
    bool scored = false;
    bool attack = false;
    std::array<double, 4> scores{};
    std::array<bool, 4> open{};
};

struct Unpin {
    bool near = false;
    bool scored = false;
    std::array<double, 4> scores{};
    std::array<bool, 4> open{};
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
        hot.assign(cells, 0);
        low_seen.assign(cells, -1000);
        timer_max.assign(cells, -1);
        occupied_round.assign(cells, -1000);
        corpse_round.assign(cells, -1);
        fast_seen.assign(cells, -1000);
        enter_time.assign(cells, 0);
        trade_target_stamp.assign(cells, -1);
        hunt_stamp.assign(cells, -1);
        threat_stamp.assign(cells, 0);
        threat_depth.assign(cells, 0);
        threat_depth_small.assign(cells, 0);
        ally_part_stamp.assign(cells, -1);
        bfs_parent.assign(cells, -1);
        bfs_via.assign(cells, 'N');
        rival_dist.assign(cells, 0);
        rival_stamp.assign(cells, 0);
        ally_dist.assign(cells, 0);
        ally_stamp.assign(cells, 0);
        visit_stamp.assign(cells, 0);
        step_count.assign(cells, 0);
        eaten_count.assign(cells, 0);
        bfs_queue.resize(static_cast<std::size_t>(cells) * 2);
        bfs_beyond.resize(static_cast<std::size_t>(cells) * 2);
        beyond_portal.assign(cells, 0);
        sonar_tag = controller.get_team().value == unswbc::Team::A ? 0x2 : 0x1;
        sonar_key = sonar_codec::make_key(width, height, sonar_tag);
        sonar_enabled = width <= SONAR_COORD_MAX + 1 && height <= SONAR_COORD_MAX + 1;
        aggressive = cells <= AGGRESSIVE_MAX_CELLS;
        grow_round = aggressive ? LEADER_GROW_ROUND : LEADER_GROW_ROUND_BIG;
        if (LC_LEAD_ROUND > 0) {
            grow_round = LC_LEAD_ROUND;
        }
        feed_round = LC_FEED_ROUND > 0 ? LC_FEED_ROUND : ENDGAME_ROUND;
        bool const long_map = TR_CENTER_ORIENT ? std::max(width, height) >= 2 * std::min(width, height) : width >= 2 * height;
        center_map = cells <= CENTER_MAX_CELLS && (long_map || cells <= CENTER_SMALL_CELLS);
        center_rounds = long_map ? CENTER_ROUNDS : CENTER_SMALL_ROUNDS;
        center_margin = long_map ? cells : CENTER_OUTNUMBER_MARGIN;
        feeder_approach = FEEDER_APPROACH + (FD_APPROACH_SCALE ? std::max(0, width + height - FD_APPROACH_BASE_SPAN) / FD_APPROACH_DIV : 0);
        rally_fresh = FD_RALLY_BIG && width + height > FD_APPROACH_BASE_SPAN ? FD_RALLY_FRESH : RALLY_FRESH;
    }

    void split_off(int child) {
        turn_split = child;
        ct.do_split(child);
    }

    void take_turn() {
        act_dirs.clear();
        turn_split = 0;
        if (PORTAL_SCOUT_MIN_LEN > 0) {
            *portal_scout_choice() = PocketChoice{};
        }
        if (POCKET_KEEP_OUT) {
            *pocket_choice() = PocketChoice{};
        }
        if (QUEEN_CORRIDOR_GUARD > 0) {
            *corridor_choice() = PocketChoice{};
        }
        if (SHORT_EVADE) {
            evade_state()->open.fill(false);
            evade_state()->attack = false;
        }
        if (MATE_UNPIN) {
            Unpin& state = *unpin_state();
            state.near = false;
            for (auto const& tile : ct.get_tiles()) {
                auto const* part = tile.get_dragon();
                if (part && part->is_head() && part->get_team() == ct.get_team() &&
                    part->get_id() != ct.get_id() && manhattan(ct.get_position(), tile.get_position()) <= 2) {
                    state.near = true;
                    state.scored = false;
                    break;
                }
            }
        }
        act();
        if (QUEEN_WAR > 0 && war_hunt()) {
            if (QUEEN_EXIT_STRICT) {
                keep_queen_exit(true);
            }
            if (QUEEN_CORRIDOR_GUARD > 0) {
                guard_queen_corridor();
            }
            if (PORTAL_SCOUT_MIN_LEN > 0) {
                guard_portal_scout();
            }
            broadcast_leader();
            return;
        }
        if (SHORT_EVADE) {
            short_evade();
        }
        if (QUEEN_EXIT_KEEP) {
            keep_queen_exit();
        }
        if (MATE_UNPIN) {
            keep_mate_exit();
        }
        if (POCKET_KEEP_OUT) {
            keep_out_of_pocket();
        }
        if (QG_SAFEZONE) {
            zone_after_move();
        }
        if (QG_CORNER) {
            corner_after_move();
        }
        if (QUEEN_EXIT_STRICT) {
            keep_queen_exit(true);
        }
        if (QUEEN_CORRIDOR_GUARD > 0) {
            guard_queen_corridor();
        }
        if (PORTAL_SCOUT_MIN_LEN > 0) {
            guard_portal_scout();
        }
        broadcast_leader();
    }

    PocketChoice* portal_scout_choice() const {
        if (PORTAL_SCOUT_MIN_LEN > 0) {
            static PocketChoice state;
            return &state;
        }
        return nullptr;
    }

    bool portal_scout_open(Direction direction) const {
        if (edge_at(head, direction) != EDGE_OPEN) {
            return false;
        }
        Position const destination = head.add_dir(direction);
        int const cell = index_of(destination);
        auto const* tile = ct.get_tile(destination);
        if (!tile || tile->get_dragon() || enter_time[cell] != 0) {
            return false;
        }
        for (Direction const onward : Direction::get_direction_list()) {
            int const next = step_index(destination, onward);
            if (next < 0 || next == index_of(head) || next == cell) {
                continue;
            }
            auto const* free = ct.get_tile(position_of(next));
            bool const tail = next == tail_index && !tile->has_pearl();
            if (free && (tail || (!free->get_dragon() && enter_time[next] == 0))) {
                return true;
            }
        }
        return false;
    }

    void guard_portal_scout() {
        if (PORTAL_SCOUT_MIN_LEN > 0) {
            if (real_queen() || ct.get_length() >= PORTAL_SCOUT_MIN_LEN || turn_split != 0 || act_dirs.empty()) {
                return;
            }
            Position position = ct.get_position();
            bool blind = false;
            for (Direction const direction : act_dirs) {
                int const next = step_index(position, direction);
                if (edge_at(position, direction) == EDGE_PORTAL && (next < 0 || seen_round[next] < 0)) {
                    blind = true;
                    break;
                }
                if (next < 0) {
                    return;
                }
                position = position_of(next);
            }
            if (!blind) {
                return;
            }
            auto const directions = Direction::get_direction_list();
            if (!portal_scout_choice()->scored) {
                if (std::none_of(directions.begin(), directions.end(), [this](Direction direction) { return portal_scout_open(direction); })) {
                    return;
                }
                pick_direction();
            }
            PocketChoice const& choice = *portal_scout_choice();
            int best = -1;
            double score = SCORE_REJECT * 0.5;
            for (std::size_t k = 0; k < directions.size(); k++) {
                if (choice.open[k] && choice.scores[k] > score && portal_scout_open(directions[k])) {
                    best = static_cast<int>(k);
                    score = choice.scores[k];
                }
            }
            if (best >= 0) {
                act_dirs.assign(1, directions[static_cast<std::size_t>(best)]);
                remember_path(act_dirs);
                ct.make_moves(act_dirs);
            }
        }
    }

    PocketChoice* corridor_choice() const {
        if (QUEEN_CORRIDOR_GUARD > 0) {
            static PocketChoice state;
            return &state;
        }
        return nullptr;
    }

    void guard_queen_corridor() {
        if (QUEEN_CORRIDOR_GUARD > 0) {
            if (!real_queen() || turn_split != 0 || act_dirs.empty()) {
                return;
            }
            struct Move {
                std::vector<int> body;
                std::vector<int> eaten;
                int steps = 0;
            };
            Move start;
            start.body.assign(ct.get_length(), -1);
            if (!trail.empty() && trail.front() == ct.get_position()) {
                for (std::size_t k = 0; k < trail.size() && k < start.body.size(); k++) {
                    start.body[k] = index_of(trail[k]);
                }
            }
            start.body.front() = index_of(ct.get_position());
            for (std::size_t k = 1; k < start.body.size(); k++) {
                if (start.body[k - 1] < 0) {
                    break;
                }
                for (auto const& tile : ct.get_tiles()) {
                    auto const* part = tile.get_dragon();
                    int const cell = index_of(tile.get_position());
                    if (part && part->get_id() == ct.get_id() && !part->is_head() &&
                        step_index(tile.get_position(), part->get_dir()) == start.body[k - 1] &&
                        std::find(start.body.begin(), start.body.begin() + k, cell) == start.body.begin() + k) {
                        start.body[k] = cell;
                        break;
                    }
                }
            }
            auto occupied = [&](int cell, Move const& move) {
                if (std::find(move.body.begin(), move.body.end(), cell) != move.body.end()) {
                    return true;
                }
                auto const* tile = ct.get_tile(position_of(cell));
                auto const* part = tile ? tile->get_dragon() : nullptr;
                return part && (part->get_id() != ct.get_id() ||
                               std::find(start.body.begin(), start.body.end(), cell) == start.body.end());
            };
            auto unknown = [&](Position position, Direction direction) {
                std::uint8_t const edge = edge_at(position, direction);
                return edge == EDGE_UNKNOWN || (edge == EDGE_PORTAL && portal_exit(position, direction) < 0);
            };
            auto step = [&](Move& move, Direction direction, bool paid) {
                int const next = step_index(position_of(move.body.front()), direction);
                if (next < 0 || occupied(next, move) ||
                    (paid && move.body.size() <= unswbc::Constants::MIN_SIZE)) {
                    return false;
                }
                auto const* tile = ct.get_tile(position_of(next));
                bool const eat = tile && tile->has_pearl() &&
                                 std::find(move.eaten.begin(), move.eaten.end(), next) == move.eaten.end();
                move.body.insert(move.body.begin(), next);
                if (eat) {
                    move.eaten.push_back(next);
                } else {
                    move.body.pop_back();
                }
                if (paid) {
                    move.body.pop_back();
                }
                move.steps++;
                return true;
            };
            auto rejected = [&](Move const& proposed) {
                std::vector<int> free_cells;
                bool room = false;
                auto walk = [&](auto&& self, Move const& move, int depth) -> bool {
                    std::vector<Direction> forward_dirs;
                    for (Direction const direction : Direction::get_direction_list()) {
                        // An unproved continuation always keeps the original move.
                        if (unknown(position_of(move.body.front()), direction)) {
                            return false;
                        }
                        int const next = step_index(position_of(move.body.front()), direction);
                        if (next >= 0 && !occupied(next, move)) {
                            forward_dirs.push_back(direction);
                        }
                    }
                    if (forward_dirs.empty()) {
                        return true;
                    }
                    if (depth >= QUEEN_CORRIDOR_GUARD) {
                        return false;
                    }
                    room = room || forward_dirs.size() > 1;
                    for (Direction const direction : forward_dirs) {
                        int const next = step_index(position_of(move.body.front()), direction);
                        if (std::find(proposed.body.begin(), proposed.body.end(), next) == proposed.body.end() &&
                            std::find(free_cells.begin(), free_cells.end(), next) == free_cells.end()) {
                            free_cells.push_back(next);
                        }
                        if (room && free_cells.size() >= proposed.body.size() + 2) {
                            return false;
                        }
                        Move forward = move;
                        if (step(forward, direction, false) && !self(self, forward, depth + 1)) {
                            return false;
                        }
                    }
                    return true;
                };
                return walk(walk, proposed, 0);
            };
            int const free = (ct.get_length() + 3) / 4;
            Move proposed = start;
            for (Direction const direction : act_dirs) {
                if (unknown(position_of(proposed.body.front()), direction) ||
                    !step(proposed, direction, proposed.steps >= free)) {
                    return;
                }
            }
            if (!rejected(proposed)) {
                return;
            }
            if (!corridor_choice()->scored) {
                head = ct.get_position();
                length = ct.get_length();
                pick_direction();
            }
            PocketChoice const& choice = *corridor_choice();
            auto const directions = Direction::get_direction_list();
            int best = -1;
            double best_score = SCORE_REJECT * 0.5;
            for (std::size_t k = 0; k < directions.size(); k++) {
                if (!choice.open[k] || choice.scores[k] <= best_score) {
                    continue;
                }
                Move next = start;
                bool const uncertain = unknown(ct.get_position(), directions[k]);
                int const destination = step_index(ct.get_position(), directions[k]);
                if (destination >= 0 ? !step(next, directions[k], false) || (!uncertain && rejected(next))
                                     : !uncertain) {
                    continue;
                }
                best = static_cast<int>(k);
                best_score = choice.scores[k];
            }
            if (best >= 0) {
                act_dirs.assign(1, directions[static_cast<std::size_t>(best)]);
                remember_path(act_dirs);
                ct.make_moves(act_dirs);
                ct.output_log("QCORRIDOR", round, ct.get_id(), proposed.body.front(), act_dirs.front());
            }
        }
    }

    PocketChoice* pocket_choice() const {
        if (POCKET_KEEP_OUT) {
            static PocketChoice state;
            return &state;
        }
        if (!POCKET_KEEP_OUT) {
            return nullptr;
        }
    }

    void keep_out_of_pocket() {
        if (POCKET_KEEP_OUT) {
            PocketChoice const& choice = *pocket_choice();
            if (turn_split != 0 || act_dirs.empty() || choice.attack || !choice.scored) {
                return;
            }
            if (!real_queen() && ct.get_length() >= 4 &&
                act_dirs.size() <= static_cast<std::size_t>((ct.get_length() + 3) / 4)) {
                return;
            }
            struct Move {
                std::vector<int> body;
                std::vector<int> eaten;
                int steps = 0;
            };
            Move start;
            start.body.assign(ct.get_length(), -1);
            if (!trail.empty() && trail.front() == ct.get_position()) {
                for (std::size_t k = 0; k < trail.size() && k < start.body.size(); k++) {
                    start.body[k] = index_of(trail[k]);
                }
            }
            start.body.front() = index_of(ct.get_position());
            auto occupied = [&](int cell, Move const& move) {
                if (std::find(move.body.begin(), move.body.end(), cell) != move.body.end()) {
                    return true;
                }
                auto const* tile = ct.get_tile(position_of(cell));
                auto const* part = tile ? tile->get_dragon() : nullptr;
                return part && (part->get_id() != ct.get_id() ||
                               std::find(start.body.begin(), start.body.end(), cell) == start.body.end());
            };
            int const free = (ct.get_length() + 3) / 4;
            auto step = [&](Move& move, Direction direction) {
                bool const paid = move.steps >= free;
                if (paid && move.body.size() <= unswbc::Constants::MIN_SIZE) {
                    return false;
                }
                int const next = step_index(position_of(move.body.front()), direction);
                if (next < 0 || occupied(next, move)) {
                    return false;
                }
                auto const* tile = ct.get_tile(position_of(next));
                bool const eat = tile && tile->has_pearl() &&
                                 std::find(move.eaten.begin(), move.eaten.end(), next) == move.eaten.end();
                move.steps++;
                move.body.insert(move.body.begin(), next);
                if (eat) {
                    move.eaten.push_back(next);
                } else {
                    move.body.pop_back();
                }
                if (paid) {
                    move.body.pop_back();
                }
                return true;
            };
            auto rejected = [&](Move const& move) {
                if (!real_queen() && move.body.size() >= 4) {
                    return false;
                }
                Position const destination = position_of(move.body.front());
                for (Direction const direction : Direction::get_direction_list()) {
                    std::uint8_t const edge = edge_at(destination, direction);
                    int const next = step_index(destination, direction);
                    if (edge == EDGE_UNKNOWN || (edge == EDGE_PORTAL && next < 0) ||
                        (next >= 0 && !occupied(next, move))) {
                        return false;
                    }
                }
                return true;
            };
            Move proposed = start;
            for (Direction const direction : act_dirs) {
                if (!step(proposed, direction)) {
                    return;
                }
            }
            if (!rejected(proposed)) {
                return;
            }
            auto const directions = Direction::get_direction_list();
            int best = -1;
            double best_score = SCORE_REJECT * 0.5;
            for (std::size_t k = 0; k < directions.size(); k++) {
                if (!choice.open[k] || choice.scores[k] <= best_score) {
                    continue;
                }
                Move next = start;
                if (!step(next, directions[k])) {
                    if (edge_at(ct.get_position(), directions[k]) != EDGE_PORTAL ||
                        portal_exit(ct.get_position(), directions[k]) >= 0) {
                        continue;
                    }
                } else if (rejected(next)) {
                    continue;
                }
                best = static_cast<int>(k);
                best_score = choice.scores[k];
            }
            if (best >= 0) {
                act_dirs.assign(1, directions[static_cast<std::size_t>(best)]);
                remember_path(act_dirs);
                ct.make_moves(act_dirs);
            }
        }
    }

    ShortEvade* evade_state() const {
        if (SHORT_EVADE) {
            static ShortEvade state;
            return &state;
        }
        if (!SHORT_EVADE) {
            return nullptr;
        }
    }

    void short_evade() {
        if (SHORT_EVADE) {
            ShortEvade const& state = *evade_state();
            if (ct.get_id() <= 1 || real_queen() || is_leader() || length > 4 || turn_split != 0 ||
                act_dirs.empty() || state.attack || (!SHORT_EVADE_ANY && ally_heads.size() + 1 > enemy_heads.size())) {
                return;
            }
            int dest = index_of(head);
            for (Direction const direction : act_dirs) {
                dest = step_index(position_of(dest), direction);
                if (dest < 0 || is_trade_target_cell(dest) || hunt_stamp[dest] == round ||
                    is_enemy_head(position_of(dest))) {
                    return;
                }
            }
            std::vector<std::uint8_t> danger(cells, 0);
            std::vector<std::uint8_t> reached(cells, 0);
            for (std::size_t k = 0; k < enemy_heads.size(); k++) {
                int const id = enemy_head_ids[k];
                auto const found = state.lengths.find(id);
                int const parts = std::max(visible_parts(id), found == state.lengths.end() ? 0 : found->second);
                int const free = (parts + 3) / 4;
                int const reach = REACH_EATS ? free + SHORT_EVADE_PAID
                                             : SHORT_EVADE_PAID == 0 ? free : free + std::min(SHORT_EVADE_PAID, std::max(0, parts - unswbc::Constants::MIN_SIZE));
                visit_mark++;
                int queue_head = 0;
                int queue_tail = 1;
                int const origin = index_of(enemy_heads[k]);
                visit_stamp[origin] = visit_mark;
                step_count[origin] = 0;
                bfs_queue[0] = enemy_heads[k];
                if (REACH_EATS) {
                    eaten_count[origin] = 0;
                }
                while (queue_head < queue_tail) {
                    Position const position = bfs_queue[queue_head++];
                    int const steps = step_count[index_of(position)];
                    if (steps >= reach || (REACH_EATS && !reach_can_step(parts, free, steps, eaten_count[index_of(position)]))) {
                        continue;
                    }
                    for (Direction const direction : Direction::get_direction_list()) {
                        int const next = step_index(position, direction);
                        if (next < 0 || visit_stamp[next] == visit_mark || enter_time[next] != 0) {
                            continue;
                        }
                        visit_stamp[next] = visit_mark;
                        step_count[next] = steps + 1;
                        if (REACH_EATS) {
                            eaten_count[next] = eaten_count[index_of(position)] + reach_pearl(next);
                        }
                        reached[next] = 1;
                        if (ally_race_steps(next) >= steps + 1) {
                            danger[next] = 1;
                        }
                        bfs_queue[queue_tail++] = position_of(next);
                    }
                }
            }
            if (!danger[dest]) {
                return;
            }
            auto const directions = Direction::get_direction_list();
            int best = -1;
            double best_score = SCORE_REJECT * 0.5;
            for (std::size_t k = 0; k < directions.size(); k++) {
                int const next = state.dests[k];
                if (state.open[k] && next >= 0 && !reached[next] && !is_trade_target_cell(next) &&
                    state.scores[k] > best_score) {
                    best = static_cast<int>(k);
                    best_score = state.scores[k];
                }
            }
            if (best < 0) {
                return;
            }
            int const next = state.dests[static_cast<std::size_t>(best)];
            act_dirs.assign(1, directions[static_cast<std::size_t>(best)]);
            remember_path(act_dirs);
            ct.make_moves(act_dirs);
            ct.output_log("SEVADE", round, ct.get_id(), dest, next);
        }
    }

    void keep_queen_exit(bool strict = false) {
        if (QUEEN_EXIT_KEEP || QUEEN_EXIT_STRICT) {
            strict = QUEEN_EXIT_STRICT && strict;
            if (strict && (ct.get_id() <= 1 || ct.get_length() < 2 || ct.get_length() > 3 ||
                           turn_split != 0 || act_dirs.empty())) {
                return;
            }
            Position queen;
            int queen_seen = -1;
            for (auto const& tile : ct.get_tiles()) {
                for (Direction const direction : Direction::get_direction_list()) {
                    remember_edge(tile.get_position(), direction, tile.get_edge(direction));
                }
                auto const* part = tile.get_dragon();
                if (part && part->is_head() && part->get_team() == ct.get_team() && part->get_id() <= 1 &&
                    part->get_id() != ct.get_id()) {
                    queen = tile.get_position();
                    queen_seen = part->get_id();
                }
            }
            if (queen_seen < 0 || (act_dirs.empty() && turn_split == 0)) {
                return;
            }
            struct Move {
                std::vector<int> body;
                std::vector<int> eaten;
                std::vector<Direction> path;
                int killed = -1;
                bool dead = false;
                bool unknown = false;
            };
            Move start;
            start.body.assign(ct.get_length(), -1);
            if (!trail.empty() && trail.front() == ct.get_position()) {
                for (std::size_t k = 0; k < trail.size() && k < start.body.size(); k++) {
                    start.body[k] = index_of(trail[k]);
                }
            }
            start.body.front() = index_of(ct.get_position());
            if (strict) {
                for (std::size_t k = 1; k < start.body.size(); k++) {
                    if (start.body[k - 1] < 0) {
                        break;
                    }
                    for (auto const& tile : ct.get_tiles()) {
                        auto const* part = tile.get_dragon();
                        int const cell = index_of(tile.get_position());
                        if (part && part->get_id() == ct.get_id() && !part->is_head() &&
                            step_index(tile.get_position(), part->get_dir()) == start.body[k - 1] &&
                            std::find(start.body.begin(), start.body.begin() + k, cell) == start.body.begin() + k) {
                            start.body[k] = cell;
                            break;
                        }
                    }
                }
            }
            auto occupied = [&](int cell, Move const& move) {
                if (std::find(move.body.begin(), move.body.end(), cell) != move.body.end()) {
                    return true;
                }
                auto const* tile = ct.get_tile(position_of(cell));
                auto const* part = tile ? tile->get_dragon() : nullptr;
                if (!part || part->get_id() == move.killed) {
                    return false;
                }
                if (part->get_id() != ct.get_id()) {
                    return true;
                }
                return !move.dead && std::find(start.body.begin(), start.body.end(), cell) == start.body.end();
            };
            auto exits = [&](Move const& move) {
                if (move.killed == queen_seen) {
                    return 0;
                }
                int count = 0;
                for (Direction const direction : Direction::get_direction_list()) {
                    int const next = step_index(queen, direction);
                    if (next >= 0 && !occupied(next, move)) {
                        count++;
                    }
                }
                return count;
            };
            int const free = (ct.get_length() + 3) / 4;
            auto step = [&](Move& move, Direction direction) {
                bool const paid = static_cast<int>(move.path.size()) >= free;
                if (paid && move.body.size() <= unswbc::Constants::MIN_SIZE) {
                    move.dead = true;
                    move.body.clear();
                    return false;
                }
                int const next = step_index(position_of(move.body.front()), direction);
                if (next < 0) {
                    move.unknown = edge_at(position_of(move.body.front()), direction) == EDGE_PORTAL;
                    move.dead = !move.unknown;
                    if (move.dead) {
                        move.body.clear();
                    }
                    return false;
                }
                if (occupied(next, move)) {
                    auto const* tile = ct.get_tile(position_of(next));
                    auto const* part = tile ? tile->get_dragon() : nullptr;
                    bool ram = false;
                    if (part && part->get_id() != ct.get_id() && part->is_head() &&
                        std::find(move.body.begin(), move.body.end(), next) == move.body.end()) {
                        move.killed = part->get_id();
                        ram = part->get_team() != ct.get_team() || (strict && part->get_id() != queen_seen);
                    }
                    move.dead = true;
                    move.body.clear();
                    if (ram) {
                        move.path.push_back(direction);
                    }
                    return ram;
                }
                auto const* tile = ct.get_tile(position_of(next));
                bool const eat = tile && tile->has_pearl() &&
                                 std::find(move.eaten.begin(), move.eaten.end(), next) == move.eaten.end();
                move.path.push_back(direction);
                move.body.insert(move.body.begin(), next);
                if (eat) {
                    move.eaten.insert(std::lower_bound(move.eaten.begin(), move.eaten.end(), next), next);
                } else {
                    move.body.pop_back();
                }
                if (paid) {
                    move.body.pop_back();
                }
                return true;
            };
            Move proposed = start;
            bool near = manhattan(ct.get_position(), queen) <= 2;
            for (Direction const direction : act_dirs) {
                int const next = step_index(position_of(proposed.body.front()), direction);
                near = near || (next >= 0 && manhattan(position_of(next), queen) <= 1);
                if (!step(proposed, direction) || proposed.dead) {
                    break;
                }
            }
            if ((strict && !near) || proposed.unknown || exits(proposed) > 0) {
                return;
            }
            Move best;
            double best_score = SCORE_REJECT * 2.0;
            bool have = false;
            for (Direction const direction : Direction::get_direction_list()) {
                Move next = start;
                if (!step(next, direction) || exits(next) == 0) {
                    continue;
                }
                double const score = next.dead ? TRADE_REWARD : score_step(position_of(next.body.front()));
                if (!have || score > best_score) {
                    best_score = score;
                    best = std::move(next);
                    have = true;
                }
            }
            if (!have && exits(start) > 0 && (ct.can_split(unswbc::Constants::MIN_SIZE) && !(QUEEN_BOOT_LEN > 0 && queen_booting()))) {
                // Splitting retains every occupied tile, including the child's new head.
                act_dirs.clear();
                pending_path.clear();
                split_off(unswbc::Constants::MIN_SIZE);
                ct.output_log("QEXIT", round, ct.get_id(), "split");
                return;
            }
            if (!have) {
                bool can_open = false;
                for (Direction const direction : Direction::get_direction_list()) {
                    int const next = step_index(queen, direction);
                    if (next < 0) {
                        continue;
                    }
                    auto const* tile = ct.get_tile(position_of(next));
                    auto const* part = tile ? tile->get_dragon() : nullptr;
                    can_open = can_open || !part || part->get_id() == ct.get_id() ||
                               (part->get_team() != ct.get_team() &&
                                std::any_of(ct.get_tiles().begin(), ct.get_tiles().end(), [&](auto const& seen_tile) {
                                    auto const* seen_part = seen_tile.get_dragon();
                                    return seen_part && seen_part->is_head() && seen_part->get_id() == part->get_id();
                                }));
                }
                if (!can_open && !strict) {
                    return;
                }
                std::deque<Move> queue;
                if (can_open) {
                    queue.push_back(start);
                }
                std::set<std::tuple<int, std::vector<int>, std::vector<int>>> seen;
                while (!queue.empty() && !have) {
                    Move move = std::move(queue.front());
                    queue.pop_front();
                    for (Direction const direction : Direction::get_direction_list()) {
                        Move next = move;
                        if (!step(next, direction)) {
                            continue;
                        }
                        if (exits(next) > 0) {
                            best = std::move(next);
                            have = true;
                            break;
                        }
                        if (next.dead) {
                            continue;
                        }
                        int const used = std::min(free, static_cast<int>(next.path.size()));
                        if (seen.emplace(used, next.body, next.eaten).second) {
                            queue.push_back(std::move(next));
                        }
                    }
                }
            }
            if (!have && strict) {
                // Reversing through a portal still collides with the neck.
                pending_path.clear();
                for (Direction const direction : Direction::get_direction_list()) {
                    int const next = step_index(ct.get_position(), direction);
                    auto const* tile = next >= 0 ? ct.get_tile(position_of(next)) : nullptr;
                    auto const* part = tile ? tile->get_dragon() : nullptr;
                    if (next >= 0 && (std::find(start.body.begin(), start.body.end(), next) != start.body.end() ||
                                      (part && part->get_id() == ct.get_id()))) {
                        turn_split = 0;
                        act_dirs.assign(1, direction);
                        ct.make_moves(act_dirs);
                        ct.output_log("QSTRICT", round, ct.get_id(), "die", direction);
                        return;
                    }
                }
                turn_split = 0;
                act_dirs.assign(1, ct.get_dir().get_opposite());
                ct.make_moves(act_dirs);
                ct.output_log("QSTRICT", round, ct.get_id(), "die", act_dirs.front());
                return;
            }
            if (have) {
                turn_split = 0;
                act_dirs = best.path;
                remember_path(act_dirs);
                ct.make_moves(act_dirs);
                ct.output_log(strict ? "QSTRICT" : "QEXIT", round, ct.get_id(), "move", static_cast<int>(act_dirs.size()));
            }
        }
    }

    Unpin* unpin_state() const {
        if (MATE_UNPIN) {
            static Unpin state;
            return &state;
        }
        if (!MATE_UNPIN) {
            return nullptr;
        }
    }

    void keep_mate_exit() {
        if (MATE_UNPIN) {
            Unpin& state = *unpin_state();
            if (!state.near || (act_dirs.empty() && turn_split == 0)) {
                return;
            }
            struct Move {
                std::vector<int> body;
                std::vector<int> eaten;
                int steps = 0;
            };
            struct SeenMate {
                int id = -1;
                std::vector<int> body;
                bool complete = true;
            };
            std::vector<SeenMate> mates;
            for (auto const& tile : ct.get_tiles()) {
                auto const* part = tile.get_dragon();
                if (!part || !part->is_head() || part->get_team() != ct.get_team() ||
                    part->get_id() == ct.get_id() || manhattan(ct.get_position(), tile.get_position()) > 2) {
                    continue;
                }
                SeenMate mate;
                mate.id = part->get_id();
                mate.body.push_back(index_of(tile.get_position()));
                while (mate.body.size() <= ct.get_tiles().size()) {
                    int const last = mate.body.back();
                    int behind = -1;
                    bool hidden = false;
                    for (Direction const direction : Direction::get_direction_list()) {
                        int const cell = step_index(position_of(last), direction);
                        if (cell < 0) {
                            hidden = hidden || edge_at(position_of(last), direction) == EDGE_PORTAL;
                            continue;
                        }
                        auto const* seen = ct.get_tile(position_of(cell));
                        auto const* segment = seen ? seen->get_dragon() : nullptr;
                        hidden = hidden || !seen;
                        if (segment && segment->get_id() == mate.id && !segment->is_head() &&
                            step_index(position_of(cell), segment->get_dir()) == last &&
                            std::find(mate.body.begin(), mate.body.end(), cell) == mate.body.end()) {
                            behind = cell;
                            break;
                        }
                    }
                    if (behind < 0) {
                        mate.complete = !hidden && mate.body.size() >= unswbc::Constants::MIN_SIZE;
                        break;
                    }
                    mate.body.push_back(behind);
                }
                mates.push_back(std::move(mate));
            }
            Move start;
            start.body.assign(ct.get_length(), -1);
            if (!trail.empty() && trail.front() == ct.get_position()) {
                for (std::size_t k = 0; k < trail.size() && k < start.body.size(); k++) {
                    start.body[k] = index_of(trail[k]);
                }
            }
            start.body.front() = index_of(ct.get_position());
            auto occupied = [&](int cell, Move const& move, int mate_id, Move const& mate) {
                if (std::find(move.body.begin(), move.body.end(), cell) != move.body.end() ||
                    std::find(mate.body.begin(), mate.body.end(), cell) != mate.body.end()) {
                    return true;
                }
                auto const* tile = ct.get_tile(position_of(cell));
                auto const* part = tile ? tile->get_dragon() : nullptr;
                if (!part || part->get_id() == mate_id) {
                    return false;
                }
                return part->get_id() != ct.get_id() ||
                       std::find(start.body.begin(), start.body.end(), cell) == start.body.end();
            };
            int const free = (ct.get_length() + 3) / 4;
            auto step = [&](Move& move, Direction direction) {
                bool const paid = move.steps >= free;
                if (paid && move.body.size() <= unswbc::Constants::MIN_SIZE) {
                    return false;
                }
                int const cell = step_index(position_of(move.body.front()), direction);
                if (cell < 0 || occupied(cell, move, -1, Move{})) {
                    return false;
                }
                auto const* tile = ct.get_tile(position_of(cell));
                bool const eat = tile && tile->has_pearl() &&
                                 std::find(move.eaten.begin(), move.eaten.end(), cell) == move.eaten.end();
                move.steps++;
                move.body.insert(move.body.begin(), cell);
                if (eat) {
                    move.eaten.push_back(cell);
                } else {
                    move.body.pop_back();
                }
                if (paid) {
                    move.body.pop_back();
                }
                return true;
            };
            auto risk = [&](Move const& move) {
                int worst = 0;
                for (SeenMate const& seen : mates) {
                    Move mate;
                    mate.body = seen.body;
                    if (!seen.complete) {
                        mate.body.resize(std::max(mate.body.size(), static_cast<std::size_t>(
                            std::max(visible_parts(seen.id), static_cast<int>(unswbc::Constants::MIN_SIZE)))), -1);
                    }
                    for (int depth = 0; depth <= 4; depth++) {
                        int count = 0;
                        int only = -1;
                        bool unknown = false;
                        for (Direction const direction : Direction::get_direction_list()) {
                            std::uint8_t const edge = edge_at(position_of(mate.body.front()), direction);
                            int const cell = step_index(position_of(mate.body.front()), direction);
                            if (edge == EDGE_UNKNOWN || (edge == EDGE_PORTAL && cell < 0)) {
                                unknown = true;
                            }
                            if (cell >= 0 && !occupied(cell, move, seen.complete || depth > 0 ? seen.id : -1, mate)) {
                                count++;
                                only = cell;
                            }
                        }
                        if (unknown || count > 1) {
                            break;
                        }
                        if (count == 0) {
                            worst = std::max(worst, depth == 0 ? 2 : 1);
                            break;
                        }
                        if (depth == 4) {
                            break;
                        }
                        auto const* tile = ct.get_tile(position_of(only));
                        bool const eat = tile && tile->has_pearl() &&
                                         std::find(move.eaten.begin(), move.eaten.end(), only) == move.eaten.end() &&
                                         std::find(mate.eaten.begin(), mate.eaten.end(), only) == mate.eaten.end();
                        mate.body.insert(mate.body.begin(), only);
                        if (eat) {
                            mate.eaten.push_back(only);
                        } else {
                            mate.body.pop_back();
                        }
                    }
                }
                return worst;
            };
            Move proposed = start;
            for (Direction const direction : act_dirs) {
                if (!step(proposed, direction)) {
                    return;
                }
            }
            int const rejected = risk(proposed);
            if (rejected == 0) {
                return;
            }
            auto const directions = Direction::get_direction_list();
            if (!state.scored) {
                for (std::size_t k = 0; k < directions.size(); k++) {
                    Position const destination = head.add_dir(directions[k]);
                    std::uint8_t const edge = edge_at(head, directions[k]);
                    state.open[k] = edge != EDGE_KELP && edge != EDGE_PORTAL &&
                                    enter_time[index_of(destination)] <= 1 &&
                                    !(is_feeder() && !is_ally_head(destination) &&
                                      (in_leader_keep_off(destination) || on_leader_ray(destination)));
                    state.scores[k] = 0.0;
                }
            }
            int best = -1;
            int best_risk = rejected;
            double best_score = SCORE_REJECT * 0.5;
            for (std::size_t k = 0; k < directions.size(); k++) {
                if (!state.open[k]) {
                    continue;
                }
                Move next = start;
                if (!step(next, directions[k])) {
                    continue;
                }
                int const danger = risk(next);
                if (danger < best_risk || (best >= 0 && danger == best_risk && state.scores[k] > best_score)) {
                    best = static_cast<int>(k);
                    best_risk = danger;
                    best_score = state.scores[k];
                }
            }
            if (best >= 0) {
                turn_split = 0;
                act_dirs.assign(1, directions[static_cast<std::size_t>(best)]);
                remember_path(act_dirs);
                ct.make_moves(act_dirs);
                ct.output_log("UNPIN", round, ct.get_id(), rejected, best_risk);
            }
        }
    }

    void fallback_exit(Direction direction) {
        if (QUEEN_EXIT_KEEP) {
            head = ct.get_position();
            length = ct.get_length();
            act_dirs.assign(1, direction);
            turn_split = 0;
            pending_path.clear();
            ct.make_move(direction);
            keep_queen_exit();
        }
        if (POCKET_KEEP_OUT) {
            head = ct.get_position();
            length = ct.get_length();
            act_dirs.assign(1, direction);
            turn_split = 0;
            pending_path.clear();
            pocket_choice()->attack = false;
            ct.make_move(direction);
            keep_out_of_pocket();
        }
        if (QUEEN_EXIT_STRICT) {
            head = ct.get_position();
            length = ct.get_length();
            if (!QUEEN_EXIT_KEEP && !POCKET_KEEP_OUT) {
                act_dirs.assign(1, direction);
                turn_split = 0;
                pending_path.clear();
                ct.make_move(direction);
            }
            keep_queen_exit(true);
        }
        if (QUEEN_CORRIDOR_GUARD > 0) {
            head = ct.get_position();
            length = ct.get_length();
            if (!QUEEN_EXIT_KEEP && !POCKET_KEEP_OUT && !QUEEN_EXIT_STRICT) {
                act_dirs.assign(1, direction);
                turn_split = 0;
                pending_path.clear();
                ct.make_move(direction);
            }
            guard_queen_corridor();
        }
    }

    void act() {
        qs_plain = false;
        observe();
        if (WAR_FEED_FIRST && (war_hunt() || avenge_hunt())) {
            // Armed hunters use the unchanged feeding triggers first.
            if (ready_to_die()) {
                ct.output_log("FEEDDIE", length, known_leader_id, known_leader_len);
                return;
            }
            if (FEED_LOCAL > 0 && local_die()) {
                return;
            }
        }
        if (QUEEN_WAR > 0 && war_hunt() && war_act()) {
            return;
        }
        if (queen_home.x < 0 && real_queen()) {
            queen_home = head;
        }
        if (QUEEN_FALLBACK) {
            fallback_update();
        }
        if (QUEEN_HERD) {
            herd_update();
        }
        if (QUEEN_HOME_CLOSED && !home_closed && real_queen() && round <= HOME_CHECK_ROUND && round % 2 == 0) {
            int const size = home_region_size();
            if (size >= HOME_MIN_CELLS) {
                home_closed = true;
                queen_game = true;
            }
        }
        if (QUEEN_QUIET_ROUND > 0) {
            if (!enemy_heads.empty() && first_contact < 0) {
                first_contact = round;
            }
            if (is_queen() && first_contact < 0 && round >= QUEEN_QUIET_ROUND) {
                queen_game = true;
            }
            if (!enemy_heads.empty()) {
                last_contact = round;
            }
            if (QUEEN_SAFE_ROUND > 0 && is_queen() && round >= QUEEN_SAFE_ROUND && round - last_contact >= QUEEN_SAFE_SPAN) {
                queen_game = true;
            }
            if (QUEEN_GAME_FEED_ROUND > 0 && queen_game) {
                feed_round = std::min(feed_round, QUEEN_GAME_FEED_ROUND);
            }
        }
        if (QG_SAFEZONE) {
            zone_watch();
            zone_probe();
            if (real_queen() && zone_queen()) {
                return;
            }
        }
        if (QG_CORNER && real_queen()) {
            corner_update();
        }
        if (TARGET_REACHABLE) {
            target_prepare();
        }
        if (QUEEN_BRAIN && is_queen() && queen_act()) {
            return;
        }

        std::vector<Direction> hunt;
        if (hunt_path(hunt)) {
            if (QUEEN_AVENGE > 0 && avenge_hunt() && hunt_queen) {
                ct.output_log("QAVENGE", round, ct.get_id(), length, "ram", enemy_queen_pos.x, enemy_queen_pos.y);
            }
            ct.make_moves(hunt);
            act_dirs = hunt;
            remember_path(hunt);
            return;
        }

        if (ready_to_die()) {
            ct.output_log("FEEDDIE", length, known_leader_id, known_leader_len);
            return;
        }
        if (FEED_LOCAL > 0 && local_die()) {
            return;
        }

        
        escape_update();
        if (STAFF_CELLS > 0 && escape_target < 0) {
            staff_update();
        }
        if (IDLE_ESCAPE > 0 && escape_target < 0 && round - last_growth_round >= IDLE_ESCAPE) {
            idle_update();
        }
        if (INC_PERIOD > 0) {
            income_update();
        }
        route_target = escape_target;
        if (INC_PERIOD > 0 && route_target < 0 && inc_target >= 0) {
            route_target = inc_target;
        }
        if (QH_SCOUT && qh_on) {
            escape_through = qh_gate == index_of(head) ? qh_gate_dir : -1;
            route_target = qh_route;
        }
        if (QUEEN_MODE && route_target < 0 && !is_queen() && !is_feeder() && enemy_queen_round >= 0 &&
            round - enemy_queen_round <= QUEEN_CHASE_FRESH &&
            (QUEEN_AVENGE > 0 ? avenge_hunt() && manhattan(head, enemy_queen_pos) <= QUEEN_AVENGE
                              : manhattan(head, enemy_queen_pos) <= QUEEN_CHASE_DIST) &&
            manhattan(head, enemy_queen_pos) > 1) {
            route_target = index_of(enemy_queen_pos);
            if (QUEEN_AVENGE > 0) {
                ct.output_log("QAVENGE", round, ct.get_id(), length, "chase", enemy_queen_pos.x, enemy_queen_pos.y);
            }
        }
        if (route_target < 0 && is_assassin() && enemy_heads.empty() && manhattan(head, big_enemy_pos) > 2) {
            route_target = index_of(big_enemy_pos);
        }
        if ((rally_fresh > 0 || RALLY_END_FRESH > 0) && route_target < 0 && rally_ready()) {
            route_target = index_of(known_leader_pos);
        }
        if (QG_SAFEZONE && route_target < 0 && zone_target >= 0) {
            route_target = zone_target;
        }
        if (QG_CORNER && route_target < 0 && corner_target >= 0) {
            route_target = corner_target;
        }
        if (fallback_on()) {
            route_target = -1;
            escape_through = -1;
        }
        Direction best = pick_direction();
        if (IDLE_LOG > 0 && round - last_growth_round >= IDLE_LOG) {
            ct.output_log("IDLE", round, length, head.x, head.y, chosen_survey.dist_pearl, chosen_survey.dist_soon,
                          chosen_survey.dist_hot, chosen_survey.dist_unseen, chosen_survey.dist_portal, route_target);
        }

        std::vector<Direction> path;
        if (ram_path(path)) {
            ct.make_moves(path);
            act_dirs = path;
            remember_path(path);
            return;
        }

        if (hit_blocked && chosen_scored && chosen_index >= 0 && long_wary()) {
            if (long_stuck(path)) {
                return;
            }
        } else if (hit_blocked && chosen_scored && chosen_index >= 0) {
            int const keep = unswbc::Constants::MIN_SIZE;
            bool const exposed = hit_head || pay_head;
            if (hit_escape(path, false, 0)) {
                ct.make_moves(path);
                act_dirs = path;
                remember_path(path);
                return;
            }
            if (!exposed && (ct.can_split(keep) && !(QUEEN_BOOT_LEN > 0 && queen_booting())) && !(QS_KEEP_LEN > 0 && hit_escape(path, true, 0))) {
                split_off(keep);
                return;
            }
            if (hit_escape(path, true, 0)) {
                ct.make_moves(path);
                act_dirs = path;
                remember_path(path);
                return;
            }
            // Her own tile is in reach too: she keeps 2 and the rest leaves as a child.
            if (exposed && (ct.can_split(length - keep) && !(QUEEN_BOOT_LEN > 0 && queen_booting()))) {
                split_off(length - keep);
                return;
            }
            // A tile an enemy must pay for beats one it hits for free.
            if (pay_open && risk_at(chosen_index) < 2) {
                ct.make_move(best);
                act_dirs.assign(1, best);
                return;
            }
            if (hit_escape(path, false, 1) || hit_escape(path, true, 1)) {
                ct.make_moves(path);
                act_dirs = path;
                remember_path(path);
                return;
            }
            // Trapped: for this turn she moves as a plain dragon.
            qs_plain = true;
            map_threats();
            mark_trade_targets();
            mark_hunt_targets();
            if (hunt_path(path)) {
                ct.make_moves(path);
                act_dirs = path;
                remember_path(path);
                return;
            }
            best = pick_direction();
            if (ram_path(path)) {
                ct.make_moves(path);
                act_dirs = path;
                remember_path(path);
                return;
            }
        }

        if (QUEEN_SAFETY && queen_wary() && !any_enterable && (hit_head || pay_head) &&
            (ct.can_split(length - unswbc::Constants::MIN_SIZE) && !(QUEEN_BOOT_LEN > 0 && queen_booting()))) {
            split_off(length - unswbc::Constants::MIN_SIZE);
            return;
        }

        if (queen_wait()) {
            if (QW_LOG) {
                ct.output_log("QWAIT", round, head.x, head.y, length, any_enterable ? 1 : 0);
            }
            split_off(unswbc::Constants::MIN_SIZE);
            return;
        }

        
        
        if (!any_enterable) {
            int known = -1;
            int blind = -1;
            auto const directions = Direction::get_direction_list();
            for (std::size_t k = 0; k < directions.size(); k++) {
                if (edge_at(head, directions[k]) != EDGE_PORTAL) {
                    continue;
                }
                int const exit = portal_exit(head, directions[k]);
                if (exit >= 0 ? mouth_fresh(exit) : mouth_fresh(-1)) {
                    continue;
                }
                if (exit >= 0 && enter_time[exit] <= 1 && known < 0) {
                    known = static_cast<int>(k);
                } else if (exit < 0 && blind < 0) {
                    blind = static_cast<int>(k);
                }
            }
            int const pick = known >= 0 ? known : blind;
            if (pick >= 0) {
                Direction const through = directions[static_cast<std::size_t>(pick)];
                if (QUEEN_PORTAL_LAST && real_queen()) {
                    int const exit = portal_exit(head, through);
                    if ((exit < 0 || seen_round[exit] < 0) && queen_portal_alternative()) {
                        return;
                    }
                }
                ct.make_move(through);
                act_dirs.assign(1, through);
                return;
            }
        }

        if (!any_enterable) {
            int const escape = escape_child_size();
            if (escape > 0) {
                split_off(escape);
                return;
            }
        }

        if (long_escape(path)) {
            ct.make_moves(path);
            act_dirs = path;
            remember_path(path);
            return;
        }

        if (cornered && (is_big() || queen_wary()) && sprint_escape(path, true)) {
            ct.make_moves(path);
            act_dirs = path;
            remember_path(path);
            return;
        }

        if (cornered && !queen_wary() && tail_index >= 0 && threat_at(tail_index) == 0) {
            int const tail_part = length - unswbc::Constants::MIN_SIZE;
            if ((ct.can_split(tail_part) && !(QUEEN_BOOT_LEN > 0 && queen_booting())) && tail_room() >= CHILD_MIN_ROOM) {
                split_off(tail_part);
                return;
            }
        }

        harvesting_now = chosen_harvest || harvest_round == round - 1;
        if (chosen_harvest) {
            harvest_round = round;
        }
        int const escape = harvesting_now ? escape_child_size() : 0;
        if (escape > 0) {
            split_off(escape);
            return;
        }

        int const child = split_child_size();
        if (child > 0) {
            split_off(child);
            return;
        }

        int const late_escape = harvesting_now ? 0 : escape_child_size();
        if (late_escape > 0) {
            split_off(late_escape);
            return;
        }
        if (sprint_escape(path, false)) {
            ct.make_moves(path);
            act_dirs = path;
            remember_path(path);
            return;
        }
        if (STRIDE && SPRINT_FREE_DIV > 0 && sprint_free() >= 2 && chosen_scored && chosen_index >= 0 &&
            edge_at(head, best) != EDGE_PORTAL && !(QG_SAFEZONE && zone_mode == 1)) {
            std::vector<Direction> stride_path(1, best);
            extend_stride(stride_path);
            if (stride_path.size() > 1) {
                ct.make_moves(stride_path);
                act_dirs = stride_path;
                remember_path(stride_path);
                return;
            }
        }
        ct.make_move(best);
        act_dirs.assign(1, best);
    }

    bool queen_portal_alternative() {
        // A legal split or known clear step precedes a blind emergency portal.
        if (ct.can_split(unswbc::Constants::MIN_SIZE)) {
            split_off(unswbc::Constants::MIN_SIZE);
            return true;
        }
        for (Direction const direction : Direction::get_direction_list()) {
            int const next = step_index(head, direction);
            if (next < 0 || edge_at(head, direction) == EDGE_KELP ||
                (edge_at(head, direction) == EDGE_PORTAL && seen_round[next] < 0)) {
                continue;
            }
            auto const* tile = ct.get_tile(position_of(next));
            if (seen_round[next] < 0 || (tile && tile->get_dragon()) || enter_time[next] != 0 ||
                std::find(trail.begin(), trail.end(), position_of(next)) != trail.end()) {
                continue;
            }
            ct.make_move(direction);
            act_dirs.assign(1, direction);
            remember_path(act_dirs);
            return true;
        }
        return false;
    }

    double stride_value(int cell) {
        survey_cap_now = STRIDE_CAP;
        double value = score_step(position_of(cell));
        survey_cap_now = 0;
        if (LOOK_DEPTH > 0 && !is_feeder()) {
            value += look_gain(cell);
        }
        return value;
    }

    void extend_stride(std::vector<Direction>& path) {
        int const free_steps = std::min(sprint_free(), STRIDE_MAX);
        std::vector<std::pair<int, int>> saved_time;
        std::vector<std::pair<int, std::uint8_t>> saved_pearl;
        auto set_time = [&](int cell, int value) {
            saved_time.emplace_back(cell, enter_time[cell]);
            enter_time[cell] = value;
        };
        std::vector<int> cells(1, chosen_index);
        int eaten = pearl_here[chosen_index] ? 1 : 0;
        if (TARGET_REACHABLE) {
            target_state().ready = false;
        }
        if (pearl_here[chosen_index]) {
            saved_pearl.emplace_back(chosen_index, pearl_here[chosen_index]);
            pearl_here[chosen_index] = 0;
        }
        Position const origin = head;
        int const origin_threat = threat_at(chosen_index);
        int const origin_risk = std::min(risk_at(chosen_index), 1);
        double stop_value = stride_value(chosen_index);
        double stop_ground = last_survey.own_seen + UNSEEN_DISCOUNT * last_survey.own_unseen;
        // Body timers as they stand once the head has reached cells[count - 1].
        auto place = [&](std::size_t count, int eaten_now) {
            if (TARGET_REACHABLE) {
                target_state().ready = false;
            }
            int const moved = static_cast<int>(count);
            for (auto it = saved_time.rbegin(); it != saved_time.rend(); ++it) {
                enter_time[it->first] = it->second;
            }
            saved_time.clear();
            for (std::size_t offset = 0; offset < trail.size(); offset++) {
                int const index = index_of(trail[offset]);
                int const absolute = length - static_cast<int>(offset) + 1;
                set_time(index, std::max(1, absolute + eaten_now - moved));
            }
            for (std::size_t i = 0; i + 1 < count; i++) {
                int const absolute = static_cast<int>(i) + 2 + length;
                set_time(cells[i], std::max(1, absolute + eaten_now - moved));
            }
            set_time(cells[count - 1], length + eaten_now + 1);
        };
        std::vector<StrideEnd> ends;
        if (STRIDE_SAFE_END) {
            ends.push_back(StrideEnd{last_room, last_reaches_tail, eaten > 0, eaten});
        }
        for (int k = 2; k <= free_steps; k++) {
            place(cells.size(), eaten);
            int const here = cells.back();
            Position const position = position_of(here);
            int best_next = -1;
            Direction best_dir = best_dir_placeholder();
            double best_value = stop_value + STRIDE_MARGIN;
            double best_ground = stop_ground;
            double best_room = 0.0;
            bool best_tail = false;
            for (Direction const direction : Direction::get_direction_list()) {
                std::uint8_t const edge = edge_at(position, direction);
                if (edge == EDGE_KELP || edge == EDGE_PORTAL || edge == EDGE_UNKNOWN) {
                    continue;
                }
                int const next = index_of(position.add_dir(direction));
                if (STRIDE_SEEN && seen_round[next] != round) {
                    continue;
                }
                if (next == index_of(origin) || enter_time[next] > 1 || is_enemy_head(position_of(next)) ||
                    is_ally_head(position_of(next))) {
                    continue;
                }
                if (threat_at(next) > origin_threat || enemy_can_step_to(position_of(next)) || risk_at(next) > origin_risk) {
                    continue;
                }
                if (QUEEN_EDGE_REACH > 0 && real_queen() && !edge_reach(cells.front()) && edge_reach(next)) {
                    continue;
                }
                if (SHARE_SIGHT && enemy_near(position_of(next), 2)) {
                    continue;
                }
                if (CELL_BUDGET > 0 && turn_cells > CELL_BUDGET + STRIDE_BUDGET) {
                    break;
                }
                double value = stride_value(next);
                double const ground = last_survey.own_seen + UNSEEN_DISCOUNT * last_survey.own_unseen;
                if (EAT_FIRST && pearl_here[next] && (FEEDER_EAT || !is_feeder()) && !in_leader_pearl_zone(next) &&
                    last_pocket <= 0.0 && !last_dead_end && (last_reaches_tail || last_room >= length + 2.0) &&
                    threat_at(next) == 0 && risk_at(next) == 0 && ground < stop_ground) {
                    value += WEIGHT_TERRITORY * (stop_ground - ground);
                }
                if (value > best_value) {
                    best_value = value;
                    best_next = next;
                    best_dir = direction;
                    best_room = last_room;
                    best_tail = last_reaches_tail;
                    best_ground = ground;
                }
            }
            if (best_next < 0) {
                break;
            }
            path.push_back(best_dir);
            cells.push_back(best_next);
            stop_value = best_value;
            stop_ground = best_ground;
            bool const pearl = pearl_here[best_next] != 0;
            if (pearl_here[best_next]) {
                eaten++;
                saved_pearl.emplace_back(best_next, pearl_here[best_next]);
                pearl_here[best_next] = 0;
            }
            if (STRIDE_SAFE_END) {
                ends.push_back(StrideEnd{best_room, best_tail, pearl, eaten});
            }
        }
        if (STRIDE_SAFE_END && cells.size() > 1) {
            // Keep the longest stride whose end is no riskier than the plain single step.
            int const caution = stride_caution();
            if (caution == 2) {
                stride_reach_map();
            }
            std::size_t keep = 1;
            StrideRisk first{};
            for (std::size_t j = 0; j < cells.size(); j++) {
                place(j + 1, ends[j].eaten);
                StrideRisk const risk = stride_risk(cells[j], ends[j], index_of(origin), caution);
                if (j == 0) {
                    first = risk;
                } else if (risk.reach <= first.reach && risk.unseen <= first.unseen && risk.shut <= first.shut) {
                    keep = j + 1;
                }
            }
            path.erase(path.begin() + static_cast<std::ptrdiff_t>(keep), path.end());
        }
        for (auto it = saved_time.rbegin(); it != saved_time.rend(); ++it) {
            enter_time[it->first] = it->second;
        }
        if (TARGET_REACHABLE) {
            target_state().ready = false;
        }
        for (auto it = saved_pearl.rbegin(); it != saved_pearl.rend(); ++it) {
            pearl_here[it->first] = it->second;
        }
    }

    Direction best_dir_placeholder() const {
        return dir_of(Direction::NORTH);
    }

    // 0 = short, 1 = long, 2 = queen.
    int stride_caution() const {
        return real_queen() && !(QUEEN_SAFETY && qs_plain) ? 2 : length >= LONG_SAFE_MIN_LENGTH ? 1 : 0;
    }

    int cut_stride_reach(int id) const {
        // Match the queen's non-eating threat ring for an edge-cut body.
        if (std::find(edge_ids.begin(), edge_ids.end(), id) == edge_ids.end()) {
            return 0;
        }
        int const parts = queen_enemy_parts(id);
        return SPRINT_FREE_DIV > 0 ? (parts + SPRINT_FREE_DIV - 1) / SPRINT_FREE_DIV + parts - 1 : parts + 1;
    }

    // Queen only: every tile an enemy we know of can reach with free plus paid steps.
    void stride_reach_map() {
        ensure_queen_buffers();
        qk_mark++;
        auto full_reach = [](int parts) {
            int const size = std::max(parts, static_cast<int>(unswbc::Constants::MIN_SIZE));
            return (size + 3) / 4 + size - static_cast<int>(unswbc::Constants::MIN_SIZE);
        };
        for (std::size_t k = 0; k < enemy_heads.size(); k++) {
            if (QUEEN_SAFETY && enemy_head_ids[k] == enemy_queen_id) {
                continue;
            }
            int parts = visible_parts(enemy_head_ids[k]);
            for (Ghost const& ghost : ghosts) {
                if (ghost.id == enemy_head_ids[k]) {
                    parts = std::max(parts, ghost.parts);
                }
            }
            if (CUT_BODY_LEN > 0 && real_queen()) {
                parts = queen_enemy_parts(enemy_head_ids[k]);
            }
            if (CUT_BODY_STRIDE && CUT_BODY_LEN > 0 && real_queen()) {
                spread_kill(enemy_heads[k], std::max(full_reach(parts), cut_stride_reach(enemy_head_ids[k])));
            } else {
                spread_kill(enemy_heads[k], full_reach(parts));
            }
        }
        if (QUEEN_FAR_HEADS > 0 && real_queen()) {
            for (Ghost const& g : far_sight().heads) {
                spread_kill(g.pos, full_reach(g.parts));
            }
        }
        for (Ghost const& ghost : ghosts) {
            if ((ghost.round == round && !ghost.shared) || (QUEEN_SAFETY && ghost.id == enemy_queen_id)) {
                continue;
            }
            if (CUT_BODY_LEN > 0 && real_queen() && visible_parts(ghost.id) > 0) {
                if (CUT_BODY_STRIDE && CUT_BODY_LEN > 0 && real_queen()) {
                    spread_kill(ghost.pos, std::max(full_reach(queen_enemy_parts(ghost.id)), cut_stride_reach(ghost.id)) + round - ghost.round);
                } else {
                    spread_kill(ghost.pos, full_reach(queen_enemy_parts(ghost.id)) + round - ghost.round);
                }
            } else {
                spread_kill(ghost.pos, full_reach(ghost.parts) + round - ghost.round);
            }
        }
    }

    int stride_reach(int cell, int caution) const {
        int const depth = threat_at(cell);
        return caution == 2 ? std::max(depth, 1 - queen_margin(cell)) : depth;
    }

    int stride_unseen(int cell) const {
        std::vector<std::pair<int, int>> reached(1, {cell, 0});
        int unseen = 0;
        for (std::size_t at = 0; at < reached.size(); at++) {
            int const steps = reached[at].second;
            if (steps >= STRIDE_SAFE_RADIUS) {
                continue;
            }
            Position const position = position_of(reached[at].first);
            for (Direction const direction : Direction::get_direction_list()) {
                int const next = step_index(position, direction);
                if (next < 0 || enter_time[next] >= BLOCKED_FOREVER ||
                    std::any_of(reached.begin(), reached.end(), [next](auto const& seen) { return seen.first == next; })) {
                    continue;
                }
                reached.emplace_back(next, steps + 1);
                unseen += seen_round[next] != round ? 1 : 0;
            }
        }
        return unseen;
    }

    // Call with the body timers placed for a head resting on `cell`.
    StrideRisk stride_risk(int cell, StrideEnd const& end, int origin, int caution) const {
        StrideRisk risk;
        risk.reach = stride_reach(cell, caution);
        int const tolerated = caution == 2 ? 0 : std::max(0, STRIDE_SAFE_UNSEEN - length / 4);
        risk.unseen = std::max(0, stride_unseen(cell) - tolerated);
        bool exit = caution == 0;
        Position const position = position_of(cell);
        for (Direction const direction : Direction::get_direction_list()) {
            if (exit || edge_at(position, direction) != EDGE_OPEN) {
                continue;
            }
            int const next = index_of(position.add_dir(direction));
            if (next == origin || seen_round[next] != round || enter_time[next] > 1 || is_enemy_head(position_of(next)) ||
                is_ally_head(position_of(next))) {
                continue;
            }
            exit = stride_reach(next, caution) == 0 && !enemy_can_step_to(position_of(next));
        }
        risk.shut = (!end.reaches_tail && end.room < length + 2.0) || !exit ? 1 : 0;
        if (caution == 0 && end.pearl) {
            risk.unseen = 0;
            risk.shut = 0;
        }
        return risk;
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
        if (QG_SAFEZONE && zone_mode == 2) {
            return 0;
        }
        if (is_queen() && (round > QUEEN_SPLIT_ROUND || enemy_near(head, queen_guard() ? QG_SPLIT_CLEAR : QUEEN_SPLIT_CLEAR) ||
                           length - unswbc::Constants::MIN_SIZE < (queen_guard() ? QG_KEEP : QUEEN_KEEP))) {
            return 0;
        }
        if (round > SPLIT_LAST_ROUND || length < SPLIT_MIN_LENGTH || is_leader()) {
            return 0;
        }
        if (QH_SCOUT && qh_on && qh_in_view) {
            return 0;
        }
        if (ring_wary() && (hit_head || pay_head)) {
            return 0;
        }
        if (QS_KEEP_LEN > 0 &&
            (QS_KEEP_ROUND <= 0 || round >= QS_KEEP_ROUND || (QS_KEEP_CLEAR > 0 && enemy_near(head, QS_KEEP_CLEAR))) &&
            real_queen() && length - unswbc::Constants::MIN_SIZE < QS_KEEP_LEN &&
            (QS_KEEP_MIN_UNITS <= 0 || ct.get_unit_count() >= QS_KEEP_MIN_UNITS)) {
            return 0;
        }
        if (round > grow_round && length > SPLIT_MIN_LENGTH && !(board_short() && length < LEADER_FULL_KEEP)) {
            return 0;
        }
        if (ct.get_unit_count() >= SPLIT_SOFT_LIMIT) {
            return 0;
        }
        if (EAT_BEFORE_SPLIT && !real_queen()) {
            for (Direction const direction : Direction::get_direction_list()) {
                int const next = step_index(head, direction);
                if (next >= 0 && pearl_here[next] && seen_round[next] == round && enter_time[next] == 0) {
                    return 0;
                }
            }
        }
        
        
        if (harvesting_now && !HARVEST_SPLIT) {
            return 0;
        }
        int const child = unswbc::Constants::MIN_SIZE;
        if (!(ct.can_split(child) && !(QUEEN_BOOT_LEN > 0 && queen_booting()))) {
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
        for (Direction const direction : Direction::get_direction_list()) {
            if (edge_at(trail.back(), direction) == EDGE_PORTAL) {
                if (SPLIT_PORTAL_OK && round <= 100 && !real_queen() && length == SPLIT_MIN_LENGTH) {
                    for (Direction const exit : Direction::get_direction_list()) {
                        if (edge_at(trail.back(), exit) != EDGE_OPEN) {
                            continue;
                        }
                        int const next = index_of(trail.back().add_dir(exit));
                        if (seen_round[next] != round || enter_time[next] != 0 || threat_at(next) > 0 ||
                            enemy_can_step_to(position_of(next))) {
                            continue;
                        }
                        Survey const survey = survey_from(position_of(next), true, false);
                        if (survey.area_seen + UNSEEN_DISCOUNT * survey.area_unseen - 1.0 >= CHILD_MIN_ROOM) {
                            return child;
                        }
                    }
                }
                return 0;
            }
        }
        return child;
    }

    bool tail_threatened() const {
        if (ESCAPE_TAIL_CLEAR <= 0 || trail.empty()) {
            return false;
        }
        Position const tail = trail.back();
        for (Position const& enemy : enemy_heads) {
            if (manhattan(enemy, tail) <= ESCAPE_TAIL_CLEAR) {
                return true;
            }
        }
        for (Ghost const& ghost : ghosts) {
            if (manhattan(ghost.pos, tail) <= ESCAPE_TAIL_CLEAR + round - ghost.round) {
                return true;
            }
        }
        return false;
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
        if (length < ESCAPE_MIN_LENGTH) {
            return 0;
        }
        
        
        bool const no_move = !any_enterable;
        bool const boxed = chosen_scored && chosen_room <= ESCAPE_ROOM_MAX && !chosen_reaches_tail;
        if (!no_move && !boxed) {
            return 0;
        }
        if (is_queen() && !no_move) {
            return 0;
        }
        int const child = length - 2;
        if (!(ct.can_split(child) && !(QUEEN_BOOT_LEN > 0 && queen_booting()))) {
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
        if (defer_escape() || tail_threatened()) {
            return 0;
        }
        double const behind = tail_room();
        return behind >= chosen_room + ESCAPE_MARGIN ? child : 0;
    }

    
    bool harvestable(int pocket_pearls, double pocket_room, bool inside) {
        int const min_size = unswbc::Constants::MIN_SIZE;
        if (is_feeder() || is_leader() || dead_queen() || tail_index < 0) {
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
        if (!chosen_harvest || chosen_pearls <= 0 || chosen_index < 0) {
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

    int sym_north(int index, int kind) const {
        int const x = index % width;
        int const y = index / width;
        int const mx = kind != 1 ? width - 1 - x : x;
        int const my = kind != 0 ? (height - y) % height : y;
        return my * width + mx;
    }

    int sym_west(int index, int kind) const {
        int const x = index % width;
        int const y = index / width;
        int const mx = kind != 1 ? (width - x) % width : x;
        int const my = kind != 0 ? height - 1 - y : y;
        return my * width + mx;
    }

    int sym_tile(int index, int kind) const {
        int const x = index % width;
        int const y = index / width;
        int const mx = kind != 1 ? width - 1 - x : x;
        int const my = kind != 0 ? height - 1 - y : y;
        return my * width + mx;
    }

    static bool edges_clash(std::uint8_t a, std::uint8_t b) {
        return a != EDGE_UNKNOWN && b != EDGE_UNKNOWN && a != b;
    }

    void fill_from_mirror(int index, int kind) {
        int const north = sym_north(index, kind);
        if (north_edge[index] == EDGE_UNKNOWN && (north_edge[north] == EDGE_OPEN || north_edge[north] == EDGE_KELP)) {
            north_edge[index] = north_edge[north];
        }
        if (north_edge[north] == EDGE_UNKNOWN && (north_edge[index] == EDGE_OPEN || north_edge[index] == EDGE_KELP)) {
            north_edge[north] = north_edge[index];
        }
        int const west = sym_west(index, kind);
        if (west_edge[index] == EDGE_UNKNOWN && (west_edge[west] == EDGE_OPEN || west_edge[west] == EDGE_KELP)) {
            west_edge[index] = west_edge[west];
        }
        if (west_edge[west] == EDGE_UNKNOWN && (west_edge[index] == EDGE_OPEN || west_edge[index] == EDGE_KELP)) {
            west_edge[west] = west_edge[index];
        }
    }

    void update_symmetry() {
        if (sym_fixed < 0) {
            for (auto const& tile : ct.get_tiles()) {
                int const index = index_of(tile.get_position());
                for (int kind = 0; kind < 3; kind++) {
                    if (!sym_alive[kind]) {
                        continue;
                    }
                    int const mirror = sym_tile(index, kind);
                    bool clash = edges_clash(north_edge[index], north_edge[sym_north(index, kind)]) ||
                                 edges_clash(west_edge[index], west_edge[sym_west(index, kind)]);
                    if (!clash && seen_round[mirror] == round && pearl_timer[index] != pearl_timer[mirror]) {
                        clash = true;
                    }
                    if (clash) {
                        sym_alive[kind] = false;
                    }
                }
            }
            int alive = 0;
            int last = -1;
            for (int kind = 0; kind < 3; kind++) {
                if (sym_alive[kind]) {
                    alive++;
                    last = kind;
                }
            }
            if (alive == 1) {
                sym_fixed = last;
                for (int index = 0; index < width * height; index++) {
                    fill_from_mirror(index, sym_fixed);
                }
            }
            return;
        }
        for (auto const& tile : ct.get_tiles()) {
            fill_from_mirror(index_of(tile.get_position()), sym_fixed);
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
        if (PORTAL_ID_GUARD && id >= 2 * cells) {
            return;
        }
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
            int const exit = portal_exit(position, direction);
            return exit >= 0 ? exit : -1;
        }
        return index_of(position.add_dir(direction));
    }

    int torus_gap(int a, int b, int size) const {
        int const raw = std::abs(a - b);
        return std::min(raw, size - raw);
    }

    void observe() {
        turn_cells = 0;
        if (TARGET_REACHABLE) {
            target_state().ready = false;
        }
        round = gm.get_round_num();
        length = ct.get_length();
        if (length > growth_length) {
            last_growth_round = round;
        }
        growth_length = length;
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
        ally_heads.clear();
        ally_head_ids.clear();
        ally_head_dirs.clear();
        seen_ids.clear();
        seen_parts.clear();
        edge_ids.clear();
        foe_now.clear();
        enemy_heads.clear();
        enemy_head_ids.clear();
        enemy_head_dirs.clear();
        own_parts.clear();
        expire_leader();
        if (QUEEN_MODE && ct.get_id() <= 1) {
            queen_id = ct.get_id();
            enemy_queen_id = 1 - queen_id;
        }
        qh_in_view = false;

        hear_exact(ct.get_id(), length, round, head, ct.get_dir());
        mouths.erase(std::remove_if(mouths.begin(), mouths.end(),
                                    [this](std::pair<int, int> const& entry) { return round - entry.second > 1; }),
                     mouths.end());
        hear_sonar();

        for (auto const& tile : ct.get_tiles()) {
            Position const position = tile.get_position();
            int const index = index_of(position);

            if (CORPSE_SLACK > 0 && tile.has_pearl() && !pearl_here[index] && occupied_round[index] >= round - 1) {
                corpse_round[index] = round;
            }
            pearl_here[index] = tile.has_pearl() ? 1 : 0;
            pearl_timer[index] = tile.get_pearl_time();
            seen_round[index] = round;
            timer_max[index] = std::max(timer_max[index], pearl_timer[index]);
            note_hot(index);

            for (Direction const direction : Direction::get_direction_list()) {
                remember_edge(position, direction, tile.get_edge(direction));
            }

            auto const* part = tile.get_dragon();
            if (!part) {
                continue;
            }
            if (CORPSE_SLACK > 0) {
                occupied_round[index] = round;
            }
            if (part->get_id() != ct.get_id()) {
                mark_blocked(index);
                count_part(part->get_id());
                if ((QUEEN_SAFETY || (CUT_BODY_LEN > 0 && real_queen())) && on_view_edge(position)) {
                    edge_ids.push_back(part->get_id());
                }
                if (LONG_SAFETY && part->get_team() != ct.get_team()) {
                    foe_now.push_back(part->get_id());
                }
                if (QUEEN_WAIT && part->get_team() == ct.get_team()) {
                    ally_part_stamp[index] = round;
                }
            } else {
                own_parts.push_back(index);
            }
            if (QUEEN_MODE && part->get_id() <= 1) {
                if (part->get_team() == ct.get_team()) {
                    queen_id = part->get_id();
                    enemy_queen_id = 1 - queen_id;
                } else {
                    enemy_queen_id = part->get_id();
                    queen_id = 1 - enemy_queen_id;
                }
            }
            if (QUEEN_MODE && part->is_head() && part->get_team() != ct.get_team() && part->get_id() == enemy_queen_id) {
                enemy_queen_pos = position;
                enemy_queen_round = round;
            }
            if ((QH_SCOUT || QUEEN_AVENGE > 0 || QUEEN_WAR > 0) && part->get_id() <= 1) {
                if (part->get_team() == ct.get_team()) {
                    qh_queen_id = part->get_id();
                } else {
                    qh_foe_id = part->get_id();
                    if (part->is_head()) {
                        qh_pos = position;
                        qh_round = round;
                        qh_in_view = true;
                    }
                }
            }
            if (part->is_head() && part->get_id() != ct.get_id()) {
                if (part->get_team() == ct.get_team()) {
                    ally_heads.push_back(position);
                    ally_head_ids.push_back(part->get_id());
                    ally_head_dirs.push_back(part->get_dir());
                } else {
                    enemy_heads.push_back(position);
                    enemy_head_ids.push_back(part->get_id());
                    enemy_head_dirs.push_back(part->get_dir());
                }
            }
        }

        if (SYM_INFER) {
            update_symmetry();
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
        if (TR_STALL_RELEASE) {
            int const gap = center_distance(head);
            if (stall_best < 0 || gap < stall_best) {
                stall_best = gap;
                stall_round = round;
            }
        }
        for (std::size_t k = 0; k < ally_head_ids.size(); k++) {
            hear_sighting(ally_head_ids[k], visible_parts(ally_head_ids[k]), ally_heads[k], ally_head_dirs[k]);
        }
        if (QH_SCOUT || QUEEN_AVENGE > 0 || QUEEN_WAR > 0) {
            qh_watch();
        }
        update_lifecycle();
        compute_drop_cells();
        pick_feed_target();
        refresh_leader_zone();
        map_rivals();
        if (QUEEN_FAR_HEADS > 0) {
            expire_far_heads();
        }
        map_threats();
        if (LONG_SAFETY) {
            note_foes();
        }
        if ((QUEEN_SAFETY && real_queen()) || long_wary()) {
            map_hits();
        }
        mark_trade_targets();
        mark_hunt_targets();
        if (SHORT_EVADE) {
            ShortEvade& state = *evade_state();
            for (std::size_t k = 0; k < seen_ids.size(); k++) {
                state.lengths[seen_ids[k]] = std::max(state.lengths[seen_ids[k]], seen_parts[k]);
            }
            for (Ghost const& ghost : ghosts) {
                if (ghost.id >= 0) {
                    state.lengths[ghost.id] = std::max(state.lengths[ghost.id], ghost.parts);
                }
            }
            for (Foe const& foe : foes) {
                state.lengths[foe.id] = std::max(state.lengths[foe.id], foe.most);
            }
        }
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

    void note_hot(int index) {
        int const timer = pearl_timer[index];
        if (HOT_FAST && timer >= 0 && timer <= 1 && !pearl_here[index]) {
            int const fast_gap = round - fast_seen[index];
            if (fast_gap >= 2 && fast_gap <= 4) {
                hot[index] = 1;
            }
            if (fast_gap >= 2) {
                fast_seen[index] = round;
            }
        }
        if (timer >= 0 && timer <= HOT_TIMER) {
            int const gap = round - low_seen[index];
            if (gap >= HOT_MIN_GAP && gap <= HOT_MAX_GAP) {
                hot[index] = 1;
            }
            if (gap >= HOT_MIN_GAP) {
                low_seen[index] = round;
            }
        } else if (timer > HOT_FALSE_TIMER) {
            hot[index] = 0;
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

    static int parts_bucket(int parts) {
        return parts >= 16 ? 3 : parts >= 8 ? 2 : parts >= 4 ? 1 : 0;
    }

    static int bucket_parts(int bucket) {
        return bucket == 3 ? 16 : bucket == 2 ? 8 : bucket == 1 ? 4 : 2;
    }

    struct FarSight {
        Position queen{-1, -1};
        int when = -1;
        int sent = -1;
        std::vector<Ghost> heads;
    };

    FarSight& far_sight() const {
        static FarSight state;
        return state;
    }

    void far_queen(int id, int when, Position pos) {
        if (QUEEN_FAR_HEADS > 0 && id == queen_id && when >= far_sight().when) {
            far_sight().queen = pos;
            far_sight().when = when;
        }
    }

    // A: one direct sighting, with a distinct 14-bit-cell message and no sentinel.
    bool pack_far_head(std::uint64_t& message) const {
        if (QUEEN_FAR_HEADS <= 0 || real_queen() || !sonar_enabled || (qh_state & 1) != 0 ||
            qh_foe_dead() || enemy_queen_dead) {
            return false;
        }
        FarSight const& state = far_sight();
        if (state.when < 0 || round - state.when > SONAR_STALE) {
            return false;
        }
        int best = -1;
        int gap = 9;
        for (std::size_t k = 0; k < enemy_heads.size(); k++) {
            int const distance = manhattan(state.queen, enemy_heads[k]);
            if (enemy_head_ids[k] != enemy_queen_id && distance < gap) {
                best = static_cast<int>(k);
                gap = distance;
            }
        }
        if (best < 0) {
            return false;
        }
        int const parts = std::clamp(visible_parts(enemy_head_ids[best]), 1, 16384);
        std::uint64_t const body = static_cast<std::uint64_t>(index_of(enemy_heads[best])) |
                                   (static_cast<std::uint64_t>(parts - 1) << 14) |
                                   (static_cast<std::uint64_t>(round) << 28) |
                                   (0x5BULL << 38) | (sonar_tag << 53) | (1ULL << 63);
        message = sonar_codec::seal(sonar_key, body);
        return true;
    }

    bool send_far_head(std::size_t direction) {
        if (QUEEN_FAR_HEADS <= 0 || far_sight().sent == round) {
            return false;
        }
        std::uint64_t message = 0;
        if (!pack_far_head(message)) {
            return false;
        }
        ct.send_sonar(Direction::get_direction_list()[direction], message);
        far_sight().sent = round;
        return true;
    }

    bool learn_far_head(std::uint64_t message) {
        if (QUEEN_FAR_HEADS <= 0 || !sonar_enabled || ((message >> 53) & 3) != sonar_tag ||
            ((message >> 38) & 0x7FFF) != 0x5B) {
            return false;
        }
        int const cell = static_cast<int>(message & 0x3FFF);
        int const parts = static_cast<int>((message >> 14) & 0x3FFF) + 1;
        int const when = static_cast<int>((message >> 28) & 0x1FF);
        if (!real_queen() || cell >= cells || parts > cells || when > round || round - when > QUEEN_FAR_HEADS) {
            return true;
        }
        auto& reports = far_sight().heads;
        auto found = std::find_if(reports.begin(), reports.end(), [cell, this](Ghost const& g) { return index_of(g.pos) == cell; });
        Ghost const report{-2, position_of(cell), when, std::max(parts, CUT_BODY_LEN), true};
        if (found != reports.end()) {
            if (when >= found->round) {
                *found = report;
            }
        } else {
            if (reports.size() >= 8) {
                reports.erase(std::min_element(reports.begin(), reports.end(), [](Ghost const& a, Ghost const& b) { return a.round < b.round; }));
            }
            reports.push_back(report);
        }
        return true;
    }

    void expire_far_heads() {
        if (QUEEN_FAR_HEADS > 0 && real_queen()) {
            auto& reports = far_sight().heads;
            reports.erase(std::remove_if(reports.begin(), reports.end(), [this](Ghost const& g) {
                return round - g.round > QUEEN_FAR_HEADS ||
                       (seen_round[index_of(g.pos)] == round && !is_enemy_head(g.pos));
            }), reports.end());
        }
    }

    bool pack_sight(std::uint64_t& message) const {
        if (enemy_heads.empty() || cells > 4096) {
            return false;
        }
        std::vector<std::size_t> order(enemy_heads.size());
        for (std::size_t k = 0; k < order.size(); k++) {
            order[k] = k;
        }
        std::sort(order.begin(), order.end(), [this](std::size_t a, std::size_t b) {
            bool const qa = enemy_head_ids[a] == enemy_queen_id;
            bool const qb = enemy_head_ids[b] == enemy_queen_id;
            if (qa != qb) {
                return qa;
            }
            return manhattan(head, enemy_heads[a]) < manhattan(head, enemy_heads[b]);
        });
        std::size_t const first = order[0];
        std::uint64_t body = (static_cast<std::uint64_t>(index_of(enemy_heads[first])) & 0xFFF) |
                             (static_cast<std::uint64_t>(parts_bucket(visible_parts(enemy_head_ids[first]))) << 12) |
                             ((static_cast<std::uint64_t>(round) & 0x1FF) << 14);
        if (order.size() > 1) {
            std::size_t const second = order[1];
            body |= (static_cast<std::uint64_t>(index_of(enemy_heads[second])) & 0xFFF) << 23;
            body |= static_cast<std::uint64_t>(parts_bucket(visible_parts(enemy_head_ids[second]))) << 35;
        } else {
            body |= static_cast<std::uint64_t>(0xFFF) << 23;
        }
        if (enemy_head_ids[first] == enemy_queen_id) {
            body |= 1ULL << 37;
        }
        body |= (static_cast<std::uint64_t>(0x5A) << 38) | ((sonar_tag & 0x3) << 53);
        message = sonar_codec::seal(sonar_key, body | (1ULL << 63));
        return true;
    }

    bool learn_sight(std::uint64_t message) {
        std::uint64_t const body = message & ((1ULL << 55) - 1);
        if (((body >> 53) & 0x3) != sonar_tag || ((body >> 38) & 0x7FFF) != 0x5A) {
            return false;
        }
        int const when = static_cast<int>((body >> 14) & 0x1FF);
        if (when > round || round - when > GHOST_ROUNDS) {
            return true;
        }
        int const first = static_cast<int>(body & 0xFFF);
        int const second = static_cast<int>((body >> 23) & 0xFFF);
        for (int k = 0; k < 2; k++) {
            int const cell = k == 0 ? first : second;
            if (cell >= cells) {
                continue;
            }
            int const bucket = static_cast<int>((body >> (k == 0 ? 12 : 35)) & 0x3);
            ghosts.push_back(Ghost{-1, position_of(cell), when, bucket_parts(bucket), true});
            if (k == 0 && ((body >> 37) & 1ULL) != 0 && when >= enemy_queen_round) {
                enemy_queen_pos = position_of(cell);
                enemy_queen_round = when;
            }
        }
        return true;
    }

    std::uint64_t pack_leader(int id, int len, int when, Position pos, Direction facing) const {
        int const tagged = QUEEN_QUIET_ROUND > 0 && queen_game && id == queen_id ? (id | 0x8000) : id;
        // QH_SCOUT: the top two length bits carry the "our queen is dead" state.
        int const sized = QH_SCOUT || QUEEN_AVENGE > 0 || QUEEN_WAR > 0 ? std::min(len, 0x3FF) | ((qh_state & 0x3) << 10) : len;
        std::uint64_t const body = (static_cast<std::uint64_t>(tagged) & 0xFFFF) |
                                   ((static_cast<std::uint64_t>(sized) & 0xFFF) << 16) |
                                   ((static_cast<std::uint64_t>(when) & 0x1FF) << 28) |
                                   ((static_cast<std::uint64_t>(pos.x) & 0x7F) << 37) |
                                   ((static_cast<std::uint64_t>(pos.y) & 0x7F) << 44) |
                                   ((static_cast<std::uint64_t>(face_code(facing)) & 0x3) << 51) |
                                   ((sonar_tag & 0x3) << 53);
        return sonar_codec::seal(sonar_key, body);
    }

    bool unpack_leader(std::uint64_t message, int& id, int& len, int& when, Position& pos,
                       Direction& facing) const {
        std::uint64_t const body = message & ((1ULL << 55) - 1);
        if ((message >> 63) != 0 || ((body >> 53) & 0x3) != sonar_tag) {
            return false;
        }
        id = static_cast<int>(body & 0xFFFF);
        len = static_cast<int>((body >> 16) & (QH_SCOUT || QUEEN_AVENGE > 0 || QUEEN_WAR > 0 ? 0x3FF : 0xFFF));
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
        if (QUEEN_MODE && id <= 1) {
            queen_id = id;
            enemy_queen_id = 1 - id;
        }
        if (QUEEN_FAR_HEADS > 0) {
            far_queen(id, when, pos);
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
        int const mine = leader_priority(known_leader_id, known_leader_len);
        int const theirs = leader_priority(id, len);
        if (theirs > mine || (theirs == mine && when > known_leader_round)) {
            known_leader_id = id;
            known_leader_len = len;
            known_leader_round = when;
            known_leader_pos = pos;
            known_leader_dir = facing;
        }
    }

    
    int leader_priority(int id, int len) const {
        return len + (QUEEN_MODE && id >= 0 && id == queen_id && (!QUEEN_LEAD_LATE || feeding_phase()) && round >= QUEEN_LEAD_ROUND &&
                               (QUEEN_QUIET_ROUND <= 0 || queen_game)
                           ? QUEEN_LEAD_BONUS
                           : 0);
    }

    void hear_sighting(int id, int visible, Position pos, Direction facing) {
        if (QUEEN_FAR_HEADS > 0) {
            far_queen(id, round, pos);
        }
        if (id == known_leader_id) {
            known_leader_len = std::max(known_leader_len, visible);
            known_leader_pos = pos;
            known_leader_dir = facing;
            return;
        }
        if (leader_priority(id, visible) > leader_priority(known_leader_id, known_leader_len)) {
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
        for (std::uint64_t const wire : ct.get_sonar_messages()) {
            std::uint64_t message = 0;
            if (!sonar_codec::open(sonar_key, wire, message)) {
                continue;
            }
            int id = -1;
            int len = 0;
            int when = -1;
            Position pos{};
            Direction facing = dir_of(Direction::NORTH);
            
            if (unpack_leader(message, id, len, when, pos, facing)) {
                if (QH_SCOUT || QUEEN_AVENGE > 0 || QUEEN_WAR > 0) {
                    qh_state = std::max(qh_state, static_cast<int>((message >> 26) & 0x3));
                }
                if ((id & 0x8000) != 0) {
                    id &= 0x7FFF;
                    queen_game = true;
                }
                if (id != ct.get_id()) {
                    hear_exact(id, len, when, pos, facing);
                }
            } else if ((message >> 63) != 0 && learn_mouth(message)) {
                continue;
            } else if (QUEEN_FAR_HEADS > 0 && (message >> 63) != 0 && learn_far_head(message)) {
                continue;
            } else if (SHARE_SIGHT && (message >> 63) != 0 && learn_sight(message)) {
                continue;
            } else if (QG_SAFEZONE && (message >> 63) != 0 && learn_zone(message)) {
                continue;
            } else if ((QH_SCOUT || QUEEN_AVENGE > 0 || QUEEN_WAR > 0) && (message >> 63) != 0 && learn_queen_ping(message)) {
                continue;
            }
        }
    }

    void broadcast_leader() {
        std::uint64_t const message =
            sonar_enabled && known_leader_id >= 0
                ? pack_leader(known_leader_id, known_leader_len, known_leader_round, known_leader_pos, known_leader_dir)
                : 0;
        if (!sonar_enabled) {
            return;
        }
        auto const directions = Direction::get_direction_list();
        int mouth_dir = -1;
        Position post = head;
        Position neck = trail.size() > 1 ? trail[1] : head;
        bool ok = true;
        for (Direction const direction : act_dirs) {
            int const next = step_index(post, direction);
            if (next < 0) {
                ok = false;
                break;
            }
            neck = post;
            post = position_of(next);
        }
        for (std::size_t k = 0; ok && k < directions.size() && mouth_dir < 0; k++) {
            if (edge_at(post, directions[k]) == EDGE_PORTAL) {
                mouth_dir = static_cast<int>(k);
            }
        }
        int const tail_cell = ok ? tail_mouth() : -1;
        // The head's ping gives way only where it would land on our own neck.
        if (tail_cell >= 0 && mouth_dir >= 0 &&
            step_index(post, directions[static_cast<std::size_t>(mouth_dir)]) == index_of(neck)) {
            mouth_dir = -1;
        }
        std::uint64_t sight = 0;
        bool const has_sight = SHARE_SIGHT && pack_sight(sight);
        for (std::size_t k = 0; k < directions.size(); k++) {
            bool const war_active = QUEEN_WAR > 0 && qh_queen_dead() && !qh_foe_dead() && !enemy_queen_dead;
            bool const war_news = QUEEN_WAR > 0 && (qh_state != 0 || qh_round >= 0 || qh_foe_dead() || enemy_queen_dead) &&
                                  (war_active || (round + static_cast<int>(k)) % 4 == 0);
            if (!war_news && QG_SAFEZONE && zone_check_dir >= 0 && static_cast<int>(k) != zone_check_dir) {
                continue;
            }
            if (war_news) {
                ct.send_sonar(directions[k], war_ping(k));
            } else if (static_cast<int>(k) == mouth_dir) {
                ct.send_sonar(directions[k], pack_mouth(index_of(post)));
            } else if (tail_cell >= 0) {
                ct.send_sonar(directions[k], pack_mouth(tail_cell));
            } else if (QG_SAFEZONE && zone_relay(k)) {
                ct.send_sonar(directions[k], pack_zone());
            } else if ((QH_SCOUT && (qh_on || (qh_notice && (round + static_cast<int>(k)) % 4 == 1))) ||
                       (QUEEN_AVENGE > 0 && (qh_round >= 0 || qh_foe_dead()) &&
                        (round + static_cast<int>(k)) % 2 == 0)) {
                ct.send_sonar(directions[k], pack_queen_ping());
            } else if (QUEEN_FAR_HEADS > 0 &&
                       (known_leader_id < 0 || (round + static_cast<int>(k)) % 4 == 2) && send_far_head(k)) {
            } else if (has_sight && (known_leader_id < 0 || (round + static_cast<int>(k)) % 2 == 0)) {
                ct.send_sonar(directions[k], sight);
            } else if (known_leader_id >= 0) {
                ct.send_sonar(directions[k], message);
            }
        }
    }

    // SN_TAIL_MOUTH: our tail cell once this turn's action is done, when a teammate could land on it
    // through a portal (a portal whose far tile is our own next segment does not count); else -1.
    int tail_mouth() const {
        if (!SN_TAIL_MOUTH || tail_index < 0 || (act_dirs.empty() && turn_split == 0)) {
            return -1;
        }
        std::vector<int> walked;
        Position cell = head;
        int eaten = 0;
        for (Direction const direction : act_dirs) {
            int const next = step_index(cell, direction);
            if (next < 0) {
                return -1;
            }
            cell = position_of(next);
            walked.push_back(next);
            eaten += pearl_here[next] ? 1 : 0;
        }
        int const moved = static_cast<int>(walked.size());
        int const last = length - turn_split - std::max(0, moved - sprint_free()) + eaten - 1;
        if (last < 0 || last - moved >= static_cast<int>(trail.size())) {
            return -1;
        }
        auto part = [&](int k) {
            return k < moved ? walked[static_cast<std::size_t>(moved - 1 - k)]
                             : index_of(trail[static_cast<std::size_t>(k - moved)]);
        };
        int const tail = part(last);
        int const before = last > 0 ? part(last - 1) : -1;
        for (Direction const direction : Direction::get_direction_list()) {
            if (edge_at(position_of(tail), direction) != EDGE_PORTAL) {
                continue;
            }
            int const far = portal_exit(position_of(tail), direction);
            if (far < 0 || far != before) {
                return tail;
            }
        }
        return -1;
    }

    // Bits 0-3: the neighbour in direction k, bit 4: the cell itself. With pearl=false a bit means
    // "in view, no pearl, none due to spawn"; with pearl=true it means "in view with a pearl".
    int qh_ring(Position cell, bool pearl) const {
        int mask = 0;
        auto const directions = Direction::get_direction_list();
        for (std::size_t k = 0; k <= directions.size(); k++) {
            int const at = k < directions.size() ? step_index(cell, directions[k]) : index_of(cell);
            if (at < 0 || seen_round[at] != round || (pearl_here[at] != 0) != pearl) {
                continue;
            }
            if (pearl || pearl_timer[at] < 0 || pearl_timer[at] > QH_SPAWN_SLACK) {
                mask |= 1 << k;
            }
        }
        return mask;
    }

    // A corpse leaves a pearl on its head cell: a new pearl there that no spawn explains.
    bool qh_corpse(Position cell, int quiet) const {
        if (QUEEN_AVENGE > 0 || QUEEN_WAR > 0) {
            quiet &= 0x10;
        }
        return seen_round[index_of(cell)] == round && (qh_ring(cell, true) & quiet) != 0;
    }

    bool qh_queen_dead() const {
        return ct.get_id() > 1 && qh_alive_round != round && (qh_state & 1) != 0;
    }

    bool qh_foe_dead() const {
        return qh_foe_dead_round >= 0 && qh_foe_dead_round >= qh_round && !((QUEEN_AVENGE > 0 || QUEEN_WAR > 0) && qh_in_view);
    }

    struct War {
        std::vector<int> seen;
        std::vector<int> windows;
        int relay = 0;
    };

    War& war_state() const {
        static War state;
        return state;
    }

    bool war_hunt() const {
        return QUEEN_WAR > 0 && ct.get_id() > 1 && length <= QUEEN_WAR &&
               qh_queen_dead() && !qh_foe_dead() && !enemy_queen_dead;
    }

    void war_seen(int cell, int when) {
        War& state = war_state();
        if (state.seen.empty()) {
            state.seen = seen_round;
            state.windows.assign(cells, -1);
        }
        state.windows[cell] = std::max(state.windows[cell], when);
        Position const at = position_of(cell);
        for (int y = -3; y <= 3; y++) {
            for (int x = -3; x <= 3; x++) {
                int const next = index_of(Position{(at.x + x + width) % width, (at.y + y + height) % height});
                state.seen[next] = std::max(state.seen[next], when);
            }
        }
    }

    std::uint64_t war_ping(std::size_t direction) {
        if (enemy_queen_dead && (qh_foe_dead_round < 0 || qh_foe_dead_round < qh_round)) {
            qh_foe_dead_round = round;
        }
        bool const active = qh_queen_dead() && !qh_foe_dead() && !enemy_queen_dead;
        int const phase = (round + static_cast<int>(direction)) % 4;
        if (active && phase == 2 && known_leader_id >= 0) {
            return pack_leader(known_leader_id, known_leader_len, known_leader_round, known_leader_pos, known_leader_dir);
        }
        if (!active || phase != 3) {
            return pack_queen_ping();
        }
        war_seen(index_of(head), round);
        War& state = war_state();
        int cell = index_of(head);
        if (round % 2 == 0) {
            for (int n = 0; n < cells; n++) {
                int const next = (state.relay + n) % cells;
                if (state.windows[next] >= 0) {
                    cell = next;
                    state.relay = (next + 1) % cells;
                    break;
                }
            }
        }
        std::uint64_t const body = (static_cast<std::uint64_t>(cell) & 0x3FFF) |
                                   (static_cast<std::uint64_t>(state.windows[cell]) << 14) |
                                   (static_cast<std::uint64_t>(qh_state & 3) << 24) |
                                   (0x8000ULL << 26) | (QH_PING_KIND << 42) | (sonar_tag << 53);
        return sonar_codec::seal(sonar_key, body | (1ULL << 63));
    }

    // War paths pay only after the free steps and keep harvesting out of target selection.
    bool war_path(Position from, int target, int reach, std::vector<Direction>& path, bool mine) {
        visit_mark++;
        int const start = index_of(from);
        int front = 0;
        int tail = 0;
        visit_stamp[start] = visit_mark;
        step_count[start] = 0;
        eaten_count[start] = 0;
        bfs_queue[tail++] = from;
        auto valid = [&](int at, Direction direction, int next, int& remaining, int& eaten) {
            if (!mine) {
                remaining = reach - step_count[at];
                eaten = 0;
                return enter_time[next] == 0 || next == target;
            }
            std::vector<Direction> prefix{direction};
            for (int cell = at; cell != start; cell = bfs_parent[cell]) {
                prefix.insert(prefix.begin(), Direction(bfs_via[cell]));
            }
            std::deque<int> body;
            for (Position const& part : trail) {
                body.push_back(index_of(part));
            }
            if (body.empty()) {
                body.push_back(start);
            }
            std::vector<int> pearls;
            remaining = length;
            eaten = 0;
            Position position = from;
            for (std::size_t n = 0; n < prefix.size(); n++) {
                if (static_cast<int>(n) >= sprint_free() && remaining <= unswbc::Constants::MIN_SIZE) {
                    return false;
                }
                int const cell = step_index(position, prefix[n]);
                if (cell < 0 || std::find(body.begin(), body.end(), cell) != body.end()) {
                    return false;
                }
                auto const* tile = ct.get_tile(position_of(cell));
                auto const* part = tile ? tile->get_dragon() : nullptr;
                if (part && part->get_id() == ct.get_id() &&
                    std::find(trail.begin(), trail.end(), position_of(cell)) == trail.end()) {
                    return false;
                }
                bool const ram = cell == target && qh_in_view && cell == index_of(qh_pos);
                if (!ram && ((part && part->get_id() != ct.get_id()) ||
                    (!part && enter_time[cell] >= BLOCKED_FOREVER))) {
                    return false;
                }
                if (ram) {
                    return n + 1 == prefix.size();
                }
                bool const eat = seen_round[cell] == round && pearl_here[cell] &&
                                 std::find(pearls.begin(), pearls.end(), cell) == pearls.end();
                body.push_front(cell);
                if (eat) {
                    pearls.push_back(cell);
                    remaining++;
                    eaten++;
                } else if (body.size() > 1) {
                    body.pop_back();
                }
                if (static_cast<int>(n) >= sprint_free()) {
                    remaining--;
                    if (body.size() > 1) {
                        body.pop_back();
                    }
                }
                position = position_of(cell);
            }
            return true;
        };
        while (front < tail) {
            Position const position = bfs_queue[front++];
            int const at = index_of(position);
            if (step_count[at] >= reach) {
                continue;
            }
            for (Direction const direction : Direction::get_direction_list()) {
                int const next = step_index(position, direction);
                int remaining = 0;
                int eaten = 0;
                if (next < 0 || visit_stamp[next] == visit_mark ||
                    !valid(at, direction, next, remaining, eaten)) {
                    continue;
                }
                bfs_parent[next] = at;
                bfs_via[next] = static_cast<char>(direction.value);
                step_count[next] = step_count[at] + 1;
                eaten_count[next] = eaten;
                visit_stamp[next] = visit_mark;
                if (next == target) {
                    path.clear();
                    for (int cell = next; cell != start; cell = bfs_parent[cell]) {
                        path.insert(path.begin(), Direction(bfs_via[cell]));
                    }
                    return true;
                }
                bfs_queue[tail++] = position_of(next);
            }
        }
        return false;
    }

    bool war_act() {
        std::vector<Direction> path;
        auto move = [&](char const* kind, std::vector<Direction> const& route) {
            ct.output_log("QWAR", round, ct.get_id(), length, kind, qh_round, qh_pos.x, qh_pos.y);
            ct.make_moves(route);
            act_dirs = route;
            remember_path(route);
            if (POCKET_KEEP_OUT) {
                pocket_choice()->attack = true;
            }
            if (SHORT_EVADE) {
                evade_state()->attack = true;
            }
        };
        war_seen(index_of(head), round);
        int const pearls = qh_in_view ? static_cast<int>(std::count_if(ct.get_tiles().begin(), ct.get_tiles().end(),
                                                        [](auto const& tile) { return tile.has_pearl(); })) : 0;
        if (qh_in_view && war_path(head, index_of(qh_pos), std::min(cells, sprint_reach() + pearls), path, true)) {
            move("ram", path);
            return true;
        }
        qh_gate = -1;
        qh_closed = false;
        Position target = qh_pos;
        int scout_gate = -1;
        int scout_dir = -1;
        bool const fresh = qh_round >= 0 && round - qh_round <= 30;
        bool peer = false;
        if (qh_in_view) {
            for (std::size_t k = 0; k < ally_heads.size(); k++) {
                int const parts = visible_parts(ally_head_ids[k]);
                int const reach = (parts + 3) / 4 + std::max(0, parts - unswbc::Constants::MIN_SIZE);
                if (war_path(ally_heads[k], index_of(qh_pos), reach, path, false)) {
                    peer = true;
                    break;
                }
            }
        }
        if (peer) {
            std::vector<Direction> cut;
            int cut_gap = BLOCKED_FOREVER;
            for (Direction const direction : Direction::get_direction_list()) {
                int const next = step_index(qh_pos, direction);
                if (next < 0 || enter_time[next] != 0 || seen_round[next] != round) {
                    continue;
                }
                int const distance = manhattan(head, position_of(next));
                if (distance < cut_gap) {
                    cut_gap = distance;
                    target = position_of(next);
                }
                if (war_path(head, next, sprint_free(), path, true) && (cut.empty() || path.size() < cut.size())) {
                    cut = path;
                }
            }
            if (!cut.empty()) {
                move("cut", cut);
                return true;
            }
        }
        if (qh_queue.empty()) {
            qh_queue.resize(cells);
        }
        if (!fresh) {
            qh_flood(qh_walk, index_of(head), false);
            int oldest = round + 1;
            int far = BLOCKED_FOREVER;
            int chosen = index_of(head);
            War const& state = war_state();
            for (int n = 0; n < cells; n++) {
                int const cell = (n + ct.get_id()) % cells;
                int const seen = std::max(seen_round[cell], state.seen[cell]);
                if (qh_walk[cell] > 0 && (seen < oldest || (seen == oldest && qh_walk[cell] < far))) {
                    oldest = seen;
                    far = qh_walk[cell];
                    chosen = cell;
                }
            }
            target = position_of(chosen);
            for (int cell = 0; cell < cells; cell++) {
                if (qh_walk[cell] < 0) {
                    continue;
                }
                auto const directions = Direction::get_direction_list();
                for (std::size_t k = 0; k < directions.size(); k++) {
                    if (edge_at(position_of(cell), directions[k]) != EDGE_PORTAL) {
                        continue;
                    }
                    int const exit = portal_exit(position_of(cell), directions[k]);
                    int const seen = exit < 0 ? -1 : std::max(seen_round[exit], state.seen[exit]);
                    if (seen < oldest) {
                        oldest = seen;
                        target = position_of(exit < 0 ? cell : exit);
                        scout_gate = exit < 0 ? cell : -1;
                        scout_dir = exit < 0 ? static_cast<int>(k) : -1;
                    }
                }
            }
        }
        qh_reach(target);
        if (scout_gate >= 0) {
            qh_gate = scout_gate;
            qh_gate_dir = scout_dir;
        }
        route_target = qh_gate >= 0 ? qh_gate : index_of(target);
        escape_through = qh_gate == index_of(head) ? qh_gate_dir : -1;
        if (war_path(head, route_target, cells, path, false)) {
            std::vector<Direction> free_path;
            Position at = head;
            for (Direction const direction : path) {
                int const next = step_index(at, direction);
                if (next < 0 || enter_time[next] != 0 || static_cast<int>(free_path.size()) >= sprint_free()) {
                    break;
                }
                free_path.push_back(direction);
                at = position_of(next);
            }
            if (!free_path.empty()) {
                move(peer ? "cut" : fresh ? "chase" : "explore", free_path);
                return true;
            }
        }
        auto const directions = Direction::get_direction_list();
        int best = -1;
        int gap = BLOCKED_FOREVER;
        for (std::size_t k = 0; k < directions.size(); k++) {
            int const next = step_index(head, directions[k]);
            if (next < 0 || enter_time[next] != 0) {
                continue;
            }
            int const distance = qh_gate >= 0 ? manhattan(position_of(next), position_of(qh_gate)) : qh_walk[next];
            if (distance >= 0 && distance < gap) {
                best = static_cast<int>(k);
                gap = distance;
            }
        }
        if (escape_through >= 0 &&
            (step_index(head, directions[static_cast<std::size_t>(escape_through)]) < 0 ||
             enter_time[step_index(head, directions[static_cast<std::size_t>(escape_through)])] == 0)) {
            best = escape_through;
        }
        if (best < 0) {
            for (std::size_t k = 0; k < directions.size(); k++) {
                if (edge_at(head, directions[k]) == EDGE_PORTAL && portal_exit(head, directions[k]) < 0) {
                    best = static_cast<int>(k);
                    break;
                }
            }
        }
        if (best < 0) {
            for (std::size_t k = 0; k < directions.size(); k++) {
                int const next = step_index(head, directions[k]);
                if (next >= 0 && enter_time[next] == 0) {
                    best = static_cast<int>(k);
                    break;
                }
            }
        }
        if (best < 0) {
            best = face_code(ct.get_dir());
        }
        path.assign(1, directions[static_cast<std::size_t>(best)]);
        move(peer ? "cut" : fresh ? "chase" : "explore", path);
        return true;
    }

    bool avenge_hunt() const {
        return QUEEN_AVENGE > 0 && QUEEN_MODE && qh_queen_dead() && !qh_foe_dead() && !enemy_queen_dead &&
               !is_leader() && known_leader_id != ct.get_id() && length <= 4;
    }

    void qh_watch() {
        bool queen_head = false;
        Position queen_at{};
        for (std::size_t k = 0; k < ally_head_ids.size(); k++) {
            if (ally_head_ids[k] == qh_queen_id) {
                queen_head = true;
                queen_at = ally_heads[k];
            }
        }
        // qh_state: 0 no claim, 1 dead, 2 seen alive after that, 3 dead again; sonar keeps the highest.
        if (ct.get_id() <= 1 || (qh_queen_id >= 0 && visible_parts(qh_queen_id) > 0)) {
            qh_alive_round = round;
            if (qh_state == 1) {
                qh_state = 2;
            }
        } else if (qh_seen_round == round - 1 && (qh_state & 1) == 0 && qh_corpse(qh_seen_pos, qh_seen_clear)) {
            qh_state++;
        }
        if (QUEEN_WAR > 0 && ct.get_id() > 1 && qh_alive_round != round &&
            static_cast<int>(ally_heads.size()) + 1 == ct.get_unit_count() &&
            std::none_of(ally_head_ids.begin(), ally_head_ids.end(), [](int id) { return id <= 1; })) {
            if ((qh_state & 1) == 0) {
                qh_state++;
                ct.output_log("QWAR", round, ct.get_id(), length, "count-dead");
            }
        }
        qh_seen_round = queen_head ? round : -1;
        qh_seen_pos = queen_at;
        qh_seen_clear = queen_head ? qh_ring(queen_at, false) : 0;
        if (!qh_in_view && qh_foe_seen_round == round - 1 && visible_parts(qh_foe_id) == 0 &&
            qh_corpse(qh_foe_seen_pos, qh_foe_seen_clear)) {
            qh_foe_dead_round = round;
        }
        qh_foe_seen_round = qh_in_view ? round : -1;
        if (qh_in_view) {
            qh_foe_seen_pos = qh_pos;
            qh_foe_seen_clear = qh_ring(qh_pos, false);
        }
        if (QUEEN_AVENGE > 0 || QUEEN_WAR > 0) {
            qh_on = false;
            qh_hunter = false;
            qh_notice = false;
            if (qh_in_view) {
                enemy_queen_dead = false;
                if (QUEEN_WAR > 0) {
                    qh_foe_dead_round = -1;
                }
            }
            return;
        }
        bool const foe_dead = qh_foe_dead();
        bool const small = ct.get_id() > 1 && !is_leader() && length <= QH_MAX_LEN;
        bool const fresh = qh_round >= 0 && round - qh_round <= QH_FRESH;
        // Reached her last cell and she is not in view: wait for a newer sighting.
        if (fresh && !qh_in_view && manhattan(head, qh_pos) <= 1) {
            qh_miss_round = std::max(qh_miss_round, qh_round);
        }
        bool const revenge = qh_queen_dead() && round >= QH_REVENGE_ROUND;
        bool const target = small && fresh && !foe_dead && qh_round > qh_miss_round;
        // First finder: sees her and has heard no other hunter for QH_QUIET rounds.
        if (target && qh_in_view && round > QH_QUIET && round - qh_heard_round > QH_QUIET) {
            qh_hunter = true;
        }
        qh_gate = -1;
        qh_closed = false;
        qh_on = target && (qh_hunter || revenge) && qh_reach(qh_pos);
        qh_hunter = qh_hunter && qh_on;
        qh_notice = small && revenge && foe_dead && round - qh_foe_dead_round <= QH_FRESH;
        // No walk to her: head for the portal first.
        qh_route = !qh_on ? -1 : qh_gate >= 0 ? qh_gate : index_of(qh_pos);
    }

    // Steps to her last cell without portals. qh_walk takes unknown edges as open, qh_sure only seen-open ones.
    int qh_flood(std::vector<int>& dist, int from, bool sure) {
        dist.assign(static_cast<std::size_t>(cells), -1);
        int tail = 0;
        dist[from] = 0;
        qh_queue[tail++] = from;
        for (int at = 0; at < tail; at++) {
            Position const cell = position_of(qh_queue[at]);
            for (Direction const direction : Direction::get_direction_list()) {
                std::uint8_t const edge = edge_at(cell, direction);
                if (edge != EDGE_OPEN && (sure || edge != EDGE_UNKNOWN)) {
                    continue;
                }
                int const next = index_of(cell.add_dir(direction));
                if (dist[next] < 0) {
                    dist[next] = dist[qh_queue[at]] + 1;
                    qh_queue[tail++] = next;
                }
            }
        }
        return tail;
    }

    // A hunter takes a portal when the far tile surely walks to her cell on a shorter way than from here,
    // or as the way out of its own closed space (qh_closed).
    bool qh_portal_ok(Position cell, Direction direction) const {
        int const exit = portal_exit(cell, direction);
        int const at = index_of(cell);
        if (exit >= 0 && qh_sure[exit] >= 0 && (qh_walk[at] < 0 || qh_sure[exit] < qh_walk[at])) {
            return true;
        }
        return qh_closed && qh_stamp[at] == qh_mark && (exit < 0 || qh_walk[exit] >= 0);
    }

    bool qh_shut(Position cell, Direction direction) const {
        return QH_SCOUT && qh_on && edge_at(cell, direction) == EDGE_PORTAL && !qh_portal_ok(cell, direction);
    }

    // True when her cell can be walked to. With no walk, qh_gate is the portal to take: one that surely leads
    // to her, or, when our own space is closed and the smaller side, a way out (a seen far tile before an unseen one).
    bool qh_reach(Position foe) {
        if (qh_stamp.empty()) {
            qh_stamp.assign(static_cast<std::size_t>(cells), 0);
            qh_queue.resize(static_cast<std::size_t>(cells));
        }
        int const outside = qh_flood(qh_walk, index_of(foe), false);
        qh_flood(qh_sure, index_of(foe), true);
        if (qh_walk[index_of(head)] >= 0) {
            return true;
        }
        qh_mark++;
        bool closed = true;
        int seen = -1;
        int seen_dir = -1;
        int blind = -1;
        int blind_dir = -1;
        int tail = 0;
        qh_stamp[index_of(head)] = qh_mark;
        qh_queue[tail++] = index_of(head);
        auto const directions = Direction::get_direction_list();
        for (int at = 0; at < tail; at++) {
            Position const cell = position_of(qh_queue[at]);
            for (std::size_t k = 0; k < directions.size(); k++) {
                std::uint8_t const edge = edge_at(cell, directions[k]);
                if (edge == EDGE_PORTAL) {
                    if (QG_SAFEZONE && zone_blocked(cell, directions[k])) {
                        continue;
                    }
                    int const exit = portal_exit(cell, directions[k]);
                    if (exit >= 0 && qh_sure[exit] >= 0) {
                        qh_gate = qh_queue[at];
                        qh_gate_dir = static_cast<int>(k);
                        return true;
                    }
                    if (exit >= 0 && qh_walk[exit] >= 0 && seen < 0) {
                        seen = qh_queue[at];
                        seen_dir = static_cast<int>(k);
                    } else if (exit < 0 && blind < 0) {
                        blind = qh_queue[at];
                        blind_dir = static_cast<int>(k);
                    }
                }
                closed = closed && edge != EDGE_UNKNOWN;
                if (edge != EDGE_OPEN && edge != EDGE_UNKNOWN) {
                    continue;
                }
                int const next = index_of(cell.add_dir(directions[k]));
                if (qh_stamp[next] != qh_mark) {
                    qh_stamp[next] = qh_mark;
                    qh_queue[tail++] = next;
                }
            }
        }
        qh_closed = closed && tail <= outside && (seen >= 0 || blind >= 0);
        if (qh_closed) {
            qh_gate = seen >= 0 ? seen : blind;
            qh_gate_dir = seen >= 0 ? seen_dir : blind_dir;
        }
        return qh_closed;
    }

    // Hunter id with her cell and the round she was seen, or the round she died.
    std::uint64_t pack_queen_ping() const {
        bool const foe_dead = qh_foe_dead();
        int const when = foe_dead ? qh_foe_dead_round : QUEEN_WAR > 0 && qh_round < 0 ? 511 : qh_round;
        int const cell = foe_dead ? 0 : index_of(qh_pos);
        std::uint64_t const body = (static_cast<std::uint64_t>(cell) & 0x3FFF) |
                                   ((static_cast<std::uint64_t>(when) & 0x1FF) << 14) |
                                   (static_cast<std::uint64_t>(foe_dead ? 1 : 0) << 23) |
                                   (static_cast<std::uint64_t>(qh_state & 0x3) << 24) |
                                   ((static_cast<std::uint64_t>(ct.get_id()) & 0xFFFF) << 26) |
                                   (QH_PING_KIND << 42) | ((sonar_tag & 0x3) << 53);
        return sonar_codec::seal(sonar_key, body | (1ULL << 63));
    }

    bool learn_queen_ping(std::uint64_t message) {
        std::uint64_t const body = message & ((1ULL << 55) - 1);
        if (((body >> 53) & 0x3) != sonar_tag || ((body >> 42) & 0x7FF) != QH_PING_KIND) {
            return false;
        }
        int const cell = static_cast<int>(body & 0x3FFF);
        int const when = static_cast<int>((body >> 14) & 0x1FF);
        int const id = static_cast<int>((body >> 26) & 0xFFFF);
        if (QUEEN_WAR > 0) {
            if (cell >= cells || (when > round && when != 511)) {
                return true;
            }
            qh_state = std::max(qh_state, static_cast<int>((body >> 24) & 0x3));
            if (when == 511) {
                return true;
            }
            if ((id & 0x8000) != 0) {
                if ((qh_state & 1) != 0 && !qh_foe_dead() && !enemy_queen_dead) {
                    war_seen(cell, when);
                }
                return true;
            }
        }
        if (cell >= cells || when > round) {
            return true;
        }
        qh_state = std::max(qh_state, static_cast<int>((body >> 24) & 0x3));
        if (((body >> 23) & 1ULL) != 0) {
            qh_foe_dead_round = std::max(qh_foe_dead_round, when);
            return true;
        }
        if (id != (ct.get_id() & 0xFFFF)) {
            qh_heard_round = round;
        }
        if (when > qh_round) {
            qh_round = when;
            qh_pos = position_of(cell);
            if (QUEEN_WAR > 0 && when > qh_foe_dead_round) {
                enemy_queen_dead = false;
            }
        }
        if ((QUEEN_AVENGE > 0 || QUEEN_WAR > 0) && when > enemy_queen_round) {
            enemy_queen_round = when;
            enemy_queen_pos = position_of(cell);
        }
        return true;
    }

    std::uint64_t pack_mouth(int cell) const {
        std::uint64_t const body = (static_cast<std::uint64_t>(cell) & 0x3FFF) |
                                   ((static_cast<std::uint64_t>(round) & 0x1FF) << 14) |
                                   (static_cast<std::uint64_t>(0xA5) << 38) | ((sonar_tag & 0x3) << 53);
        return sonar_codec::seal(sonar_key, body | (1ULL << 63));
    }

    bool learn_mouth(std::uint64_t message) {
        std::uint64_t const body = message & ((1ULL << 55) - 1);
        if (((body >> 53) & 0x3) != sonar_tag || ((body >> 38) & 0x7FFF) != 0xA5 || ((body >> 23) & 0x7FFF) != 0) {
            return false;
        }
        int const cell = static_cast<int>(body & 0x3FFF);
        int const when = static_cast<int>((body >> 14) & 0x1FF);
        if (cell >= cells || when > round || round - when > 1) {
            return false;
        }
        mouths.emplace_back(cell, when);
        return true;
    }

    bool mouth_fresh(int cell) const {
        for (auto const& entry : mouths) {
            if (round - entry.second <= 1 && (cell < 0 || entry.first == cell)) {
                return true;
            }
        }
        return false;
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
        feed_index = -1;
        feed_id = -1;
        if (is_assassin() || (QH_SCOUT && qh_on)) {
            return;
        }
        bool const early = FEED_EARLY_ROUND > 0 && round > FEED_EARLY_ROUND && length <= FEED_EARLY_MAX;
        if ((!feeding_phase() && !early) || is_queen() || queen_aloof() || known_leader_id < 0 ||
            known_leader_id == ct.get_id() || known_leader_len < 2 ||
            !feed_len_ok() || ct.get_unit_count() <= FEEDER_KEEP_UNITS) {
            return;
        }
        if (manhattan(head, live_leader_head()) > feeder_approach) {
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
        if (round <= grow_round || board_short() || known_leader_id < 0 ||
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
        int const to_leader = torus_gap(cell.x, zone_head.x, width) + torus_gap(cell.y, zone_head.y, height);
        if (ZONE_NEARER && (FEEDER_EAT || !is_feeder()) &&
            torus_gap(cell.x, head.x, width) + torus_gap(cell.y, head.y, height) < to_leader) {
            return false;
        }
        return to_leader <= LEADER_PEARL_RADIUS;
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
        rival_mark++;
        flood_heads(enemy_heads, rival_dist, rival_stamp, rival_mark);
        ally_mark++;
        flood_heads(ally_heads, ally_dist, ally_stamp, ally_mark);
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

    
    
    
    
    void update_ghosts() {
        for (std::size_t k = 0; k < enemy_heads.size(); k++) {
            int const id = enemy_head_ids[k];
            auto found = std::find_if(ghosts.begin(), ghosts.end(), [id](Ghost const& g) { return g.id == id; });
            if (found == ghosts.end()) {
                ghosts.push_back(Ghost{id, enemy_heads[k], round, visible_parts(id), false, static_cast<char>(enemy_head_dirs[k].value)});
            } else {
                found->pos = enemy_heads[k];
                found->round = round;
                found->parts = std::max(found->parts, visible_parts(id));
                found->face = static_cast<char>(enemy_head_dirs[k].value);
            }
        }
        ghosts.erase(std::remove_if(ghosts.begin(), ghosts.end(),
                                    [this](Ghost const& g) {
                                        if (round - g.round > GHOST_ROUNDS) {
                                            return true;
                                        }
                                        if (!g.shared) {
                                            return false;
                                        }
                                        for (Position const& seen : enemy_heads) {
                                            if (manhattan(seen, g.pos) <= round - g.round + 1) {
                                                return true;
                                            }
                                        }
                                        return seen_round[index_of(g.pos)] == round;
                                    }),
                     ghosts.end());
    }

    void map_threats() {
        threat_mark++;
        update_ghosts();
        if (CUT_BODY_LEN > 0 && real_queen()) {
            note_cut_lengths();
        }
        bool const wary = queen_wary();
        bool const spare = QUEEN_SAFETY && wary;
        if (spare && peer_depth.empty()) {
            peer_depth.assign(cells, 0);
        }
        std::size_t const local_sources = enemy_heads.size() + (is_big() || wary ? ghosts.size() : 0);
        std::size_t const sources = local_sources + (QUEEN_FAR_HEADS > 0 && real_queen() ? far_sight().heads.size() : 0);
        for (std::size_t k = 0; k < sources; k++) {
            bool const ghost = k >= enemy_heads.size();
            bool const far = QUEEN_FAR_HEADS > 0 && k >= local_sources;
            Ghost const* g = far ? &far_sight().heads[k - local_sources] : ghost ? &ghosts[k - enemy_heads.size()] : nullptr;
            if (ghost && g->round == round && !g->shared) {
                continue;
            }
            // Our queen sizes up the enemy queen as a plain dragon would.
            bool const peer = spare && (ghost ? g->id : enemy_head_ids[k]) == enemy_queen_id;
            if (peer && ghost && !is_big()) {
                continue;
            }
            bool const queen_rules = wary && !peer;
            int parts = ghost ? g->parts : visible_parts(enemy_head_ids[k]);
            if (CUT_BODY_LEN > 0 && real_queen()) {
                int const id = ghost ? g->id : enemy_head_ids[k];
                if (visible_parts(id) > 0) {
                    parts = queen_enemy_parts(id);
                }
            }
            bool const small = !ghost && parts < TRADE_TARGET_MIN_PARTS;
            int const small_reach = SMALL_SPRINT_THREAT ? std::max(SMALL_UNIT_THREAT_REACH, parts - 1) : SMALL_UNIT_THREAT_REACH;
            int const queen_reach = SPRINT_FREE_DIV > 0 ? (parts + SPRINT_FREE_DIV - 1) / SPRINT_FREE_DIV + parts - 1 : parts + 1;
            int const true_reach = std::clamp((parts + 3) / 4 + parts - 2 + BIG_TRUE_MARGIN, 1, std::max(1, BIG_TRUE_REACH));
            bool const eats = REACH_EATS && (!ghost || (QUEEN_FAR_HEADS > 0 && far)) && ((queen_rules && real_queen()) || (SMALL_SPRINT_THREAT && small));
            int const free = (parts + 3) / 4;
            int const reach = eats ? (queen_rules ? QUEEN_REACH_MAX : BIG_TRUE_REACH > 0 && is_big() ? BIG_TRUE_REACH : THREAT_REACH_MAX) : (queen_rules ? std::clamp(queen_reach, THREAT_REACH_MIN, QUEEN_REACH_MAX)
                               : BIG_TRUE_REACH > 0 && is_big() && !ghost ? true_reach
                                          : std::clamp(parts + (is_big() ? BIG_REACH_BONUS : 0), THREAT_REACH_MIN, THREAT_REACH_MAX)) +
                              (ghost && !(QUEEN_FAR_HEADS > 0 && far) ? round - g->round : 0);
            Position const from = ghost ? g->pos : enemy_heads[k];
            visit_mark++;
            int queue_head = 0;
            int queue_tail = 0;
            int const origin = index_of(from);
            visit_stamp[origin] = visit_mark;
            step_count[origin] = 0;
            bfs_queue[queue_tail++] = from;
            if (eats) {
                eaten_count[origin] = 0;
            }
            while (queue_head < queue_tail) {
                Position const position = bfs_queue[queue_head++];
                int const steps = step_count[index_of(position)];
                if (steps >= reach || (eats && !reach_can_step(parts, free, steps, eaten_count[index_of(position)]))) {
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
                    if (eats) {
                        eaten_count[next] = eaten_count[index_of(position)] + reach_pearl(next);
                    }
                    int const remaining = eats ? std::min(reach, free + parts - unswbc::Constants::MIN_SIZE + eaten_count[index_of(position)]) : reach;
                    int const depth = std::min(remaining - steps, queen_rules ? QUEEN_REACH_MAX : std::max(THREAT_REACH_MAX, BIG_TRUE_REACH));
                    if (threat_stamp[next] != threat_mark) {
                        threat_stamp[next] = threat_mark;
                        threat_depth[next] = 0;
                        threat_depth_small[next] = 0;
                        if (spare) {
                            peer_depth[next] = 0;
                        }
                    }
                    if (peer) {
                        peer_depth[next] = std::max(peer_depth[next], depth);
                    } else {
                        threat_depth[next] = std::max(threat_depth[next], depth);
                    }
                    if (small && (eats || steps + 1 <= small_reach) && (peer || !spare)) {
                        threat_depth_small[next] = std::max(threat_depth_small[next], 1);
                    }
                    bfs_queue[queue_tail++] = position_of(next);
                }
            }
        }
    }

    bool is_big() const { return length >= BIG_GUARD_MIN_LENGTH; }

    int exposure_at(int index) const {
        if (threat_stamp[index] != threat_mark) {
            return 0;
        }
        return QUEEN_SAFETY && queen_wary() && !peer_depth.empty() ? std::max(threat_depth[index], peer_depth[index])
                                                                   : threat_depth[index];
    }

    int threat_at(int index) const {
        if (threat_stamp[index] != threat_mark) {
            return 0;
        }
        if (QUEEN_SAFETY && queen_wary()) {
            return std::max(threat_depth[index], peer_at(index));
        }
        return length <= TRADE_MAX_LENGTH && !queen_wary() ? threat_depth_small[index] : threat_depth[index];
    }

    // Danger from the enemy queen to our queen, by plain-dragon rules.
    int peer_at(int index) const {
        if (!QUEEN_SAFETY || !queen_wary() || peer_depth.empty() || threat_stamp[index] != threat_mark) {
            return 0;
        }
        return length <= TRADE_MAX_LENGTH ? threat_depth_small[index] : peer_depth[index];
    }

    void mark_hunt_targets() {
        hunt_targets = 0;
        sure_queen = false;
        bool const spare = QUEEN_SAFETY && queen_wary();
        if (queen_wary() && !spare) {
            hunt_queen = false;
            return;
        }
        if (QH_SCOUT && qh_on && !spare) {
            for (std::size_t k = 0; k < enemy_heads.size(); k++) {
                if (enemy_head_ids[k] == qh_foe_id) {
                    hunt_stamp[index_of(enemy_heads[k])] = round;
                    hunt_targets++;
                }
            }
            if (hunt_targets > 0) {
                hunt_queen = true;
                return;
            }
        }
        if (QUEEN_MODE && QUEEN_SURE_LEN > 0 && !real_queen() && !is_leader() && length <= QUEEN_SURE_LEN) {
            for (std::size_t k = 0; k < enemy_heads.size(); k++) {
                if (enemy_head_ids[k] == enemy_queen_id && manhattan(head, enemy_heads[k]) <= QUEEN_SURE_STEPS) {
                    hunt_stamp[index_of(enemy_heads[k])] = round;
                    hunt_targets++;
                }
            }
            if (hunt_targets > 0) {
                hunt_queen = sure_queen = true;
                return;
            }
        }
        if (QUEEN_MODE && (QUEEN_AVENGE > 0 ? avenge_hunt()
                                         : QUEEN_HUNT && !is_queen() && (QUEEN_HUNT_MAX_LEN <= 0 || length <= QUEEN_HUNT_MAX_LEN))) {
            for (std::size_t k = 0; k < enemy_heads.size(); k++) {
                if (enemy_head_ids[k] == enemy_queen_id) {
                    hunt_stamp[index_of(enemy_heads[k])] = round;
                    hunt_targets++;
                }
            }
            if (hunt_targets > 0) {
                hunt_queen = true;
                return;
            }
        }
        hunt_queen = false;
        if (END_HUNT_MIN_PARTS > 0 && feeding_phase() && !is_leader() && !queen_aloof() && known_leader_id >= 0 &&
            known_leader_id != ct.get_id() && length < known_leader_len) {
            for (std::size_t k = 0; k < enemy_heads.size(); k++) {
                int const parts = visible_parts(enemy_head_ids[k]);
                if (spare && enemy_head_ids[k] != enemy_queen_id) {
                    continue;
                }
                if (parts >= END_HUNT_MIN_PARTS && parts * END_HUNT_RATIO >= length) {
                    hunt_stamp[index_of(enemy_heads[k])] = round;
                    hunt_targets++;
                }
            }
            if (hunt_targets > 0) {
                return;
            }
        }
        if (HUNT_MIN_PARTS <= 0 || is_leader() || length > HUNT_MAX_LENGTH) {
            return;
        }
        for (std::size_t k = 0; k < enemy_heads.size(); k++) {
            int const parts = visible_parts(enemy_head_ids[k]);
            if (spare && enemy_head_ids[k] != enemy_queen_id) {
                continue;
            }
            bool const big = (parts >= HUNT_MIN_PARTS && parts >= length + HUNT_MARGIN) ||
                             (HUNT_SMALL_RATIO > 0 && length <= TRADE_MAX_LENGTH && !real_queen() &&
                              parts >= HUNT_SMALL_RATIO * length);
            if (big || (HUNT_GUARD && !spare && guards_big_ally(enemy_heads[k]))) {
                hunt_stamp[index_of(enemy_heads[k])] = round;
                hunt_targets++;
            }
        }
    }

    bool hunt_path(std::vector<Direction>& path) {
        if (hunt_targets == 0) {
            return false;
        }
        int const reach = std::min(sprint_reach(), sure_queen ? QUEEN_SURE_STEPS : hunt_queen ? QUEEN_HUNT_STEPS : HUNT_MAX_STEPS);
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
                if (next < 0 || visit_stamp[next] == visit_mark || qh_shut(position, direction) ||
                    (sure_queen && edge_at(position, direction) == EDGE_PORTAL)) {
                    continue;
                }
                if (hunt_stamp[next] == round) {
                    if (POCKET_KEEP_OUT) {
                        pocket_choice()->attack = true;
                    }
                    if (SHORT_EVADE) {
                        evade_state()->attack = true;
                    }
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
                step_count[next] = steps + (LUNGE_PEARL && !real_queen() && attack_units_ok() && pearl_here[next] && seen_round[next] == round ? 0 : 1);
                bfs_parent[next] = index;
                bfs_via[next] = static_cast<char>(direction.value);
                bfs_queue[queue_tail++] = position_of(next);
            }
        }
        return false;
    }

    void mark_trade_targets() {
        trade_targets = 0;
        bool const at_cap = ct.get_unit_count() >= std::min(gm.get_unit_limit(), SPLIT_SOFT_LIMIT) - 1;
        bool const normal_ok = round <= feed_round &&
                               ct.get_unit_count() >= (aggressive ? AGGRESSIVE_TRADE_MIN_UNITS : TRADE_MIN_UNITS) &&
                               static_cast<int>(ally_heads.size()) + 1 - static_cast<int>(enemy_heads.size()) >= TRADE_LOCAL_EDGE;
        for (std::size_t k = 0; k < enemy_heads.size(); k++) {
            int const parts = visible_parts(enemy_head_ids[k]);
            bool const spare = QUEEN_SAFETY && queen_wary();
            if (spare && enemy_head_ids[k] != enemy_queen_id) {
                continue;
            }
            bool const worth = at_cap || aggressive || TRADE_EVEN ? parts >= length - (real_queen() || !attack_units_ok() ? 0 : TRADE_SHORT_BY) : parts >= std::max(TRADE_TARGET_MIN_PARTS, length + 2);
            if ((normal_ok && worth) || (!spare && guards_big_ally(enemy_heads[k])) ||
                (QUEEN_DEFEND_STEPS > 0 && !spare && enemy_head_ids[k] != enemy_queen_id && guards_queen(enemy_heads[k]))) {
                trade_target_stamp[index_of(enemy_heads[k])] = round;
                trade_targets++;
            }
        }
    }

    bool guards_queen(Position enemy) const {
        if (!QUEEN_MODE || length > TRADE_MAX_LENGTH || is_leader()) {
            return false;
        }
        int const target = index_of(enemy);
        for (std::size_t k = 0; k < ally_heads.size(); k++) {
            if (ally_head_ids[k] != queen_id) {
                continue;
            }
            std::vector<int> reached{index_of(ally_heads[k])};
            std::size_t from = 0;
            for (int steps = 0; steps < QUEEN_DEFEND_STEPS; steps++) {
                std::size_t const upto = reached.size();
                for (; from < upto; from++) {
                    for (Direction const direction : Direction::get_direction_list()) {
                        int const next = step_index(position_of(reached[from]), direction);
                        if (next == target) {
                            return true;
                        }
                        if (next >= 0 && std::find(reached.begin(), reached.end(), next) == reached.end()) {
                            reached.push_back(next);
                        }
                    }
                }
            }
        }
        return false;
    }

    bool guards_big_ally(Position enemy) const {
        for (std::size_t k = 0; k < ally_heads.size(); k++) {
            if (QUEEN_MODE && ally_head_ids[k] == queen_id && manhattan(ally_heads[k], enemy) <= QUEEN_DEFEND_RADIUS &&
                (!QUEEN_DEFEND_LATE || feeding_phase())) {
                return true;
            }
            if (visible_parts(ally_head_ids[k]) >= DEFEND_MIN_PARTS && manhattan(ally_heads[k], enemy) <= DEFEND_RADIUS) {
                return true;
            }
        }
        return false;
    }

    
    bool ram_path(std::vector<Direction>& path) {
        if (!is_trader()) {
            return false;
        }
        int const reach = std::min(sprint_reach(), aggressive ? AGGRESSIVE_RAM_MAX_STEPS : RAM_MAX_STEPS);
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
                if (next < 0 || visit_stamp[next] == visit_mark || qh_shut(position, direction)) {
                    continue;
                }
                if (is_trade_target_cell(next)) {
                    if (POCKET_KEEP_OUT) {
                        pocket_choice()->attack = true;
                    }
                    if (SHORT_EVADE) {
                        evade_state()->attack = true;
                    }
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
                step_count[next] = steps + (LUNGE_PEARL && !real_queen() && attack_units_ok() && pearl_here[next] && seen_round[next] == round ? 0 : 1);
                bfs_parent[next] = index;
                bfs_via[next] = static_cast<char>(direction.value);
                bfs_queue[queue_tail++] = position_of(next);
            }
        }
        return false;
    }

    
    bool long_escape(std::vector<Direction>& path) {
        if (CUT_BODY_STRIDE && CUT_BODY_LEN > 0 && real_queen()) {
            stride_reach_map();
        }
        if (BIG_ESCAPE_STEPS <= 0 || is_queen() || length < BIG_ESCAPE_MIN_LENGTH || (BIG_ESCAPE_LATE && !feeding_phase()) ||
            !chosen_scored || chosen_index < 0 ||
            threat_at(chosen_index) == 0 || sprint_free() < 2) {
            return false;
        }
        int const limit = std::min(sprint_free(), BIG_ESCAPE_STEPS);
        struct Node {
            int cell;
            int parent;
            int depth;
            Direction dir;
        };
        std::vector<Node> nodes;
        visit_mark++;
        int const start = index_of(head);
        visit_stamp[start] = visit_mark;
        nodes.push_back({start, -1, 0, dir_of(Direction::NORTH)});
        std::vector<int> safe;
        for (std::size_t q = 0; q < nodes.size(); q++) {
            Node const node = nodes[q];
            if (node.depth >= limit) {
                continue;
            }
            Position const position = position_of(node.cell);
            for (Direction const direction : Direction::get_direction_list()) {
                std::uint8_t const edge = edge_at(position, direction);
                if (edge == EDGE_KELP || edge == EDGE_PORTAL || edge == EDGE_UNKNOWN) {
                    continue;
                }
                int const next = index_of(position.add_dir(direction));
                if (visit_stamp[next] == visit_mark || seen_round[next] != round) {
                    continue;
                }
                if (enter_time[next] > (node.depth == 0 ? 1 : 0) || is_enemy_head(position_of(next)) ||
                    is_ally_head(position_of(next))) {
                    continue;
                }
                visit_stamp[next] = visit_mark;
                nodes.push_back({next, static_cast<int>(q), node.depth + 1, direction});
                if (node.depth + 1 >= 2 && threat_at(next) == 0 && !enemy_can_step_to(position_of(next)) &&
                    !(long_wary() && risk_at(next) > 0) &&
                    !(CUT_BODY_STRIDE && CUT_BODY_LEN > 0 && real_queen() && queen_margin(next) <= 0)) {
                    safe.push_back(static_cast<int>(nodes.size()) - 1);
                }
            }
        }
        double best = SCORE_REJECT * 0.5;
        int best_node = -1;
        int evals = 0;
        for (int const k : safe) {
            if (evals++ >= BIG_ESCAPE_EVALS || (CELL_BUDGET > 0 && turn_cells > CELL_BUDGET)) {
                break;
            }
            double const score = score_step(position_of(nodes[k].cell));
            if (score > best) {
                best = score;
                best_node = k;
            }
        }
        if (best_node < 0) {
            return false;
        }
        path.clear();
        for (int k = best_node; nodes[k].parent >= 0; k = nodes[k].parent) {
            path.push_back(nodes[k].dir);
        }
        std::reverse(path.begin(), path.end());
        return true;
    }

    bool sprint_escape(std::vector<Direction>& path, bool force) {
        if (CUT_BODY_STRIDE && CUT_BODY_LEN > 0 && real_queen()) {
            stride_reach_map();
        }
        if ((length < SPRINT_ESCAPE_MIN_LENGTH && !(queen_wary() && sprint_reach() >= 2)) || !chosen_scored || chosen_index < 0 || threat_at(chosen_index) == 0) {
            return false;
        }
        double best = force ? SCORE_REJECT * 0.5 : chosen_score;
        bool found = false;
        int evals = 0;
        int const max_evals = force ? BIG_SPRINT_EVALS : SPRINT_ESCAPE_MAX_EVALS;
        int const start = index_of(head);
        for (int const steps : {2, 3}) {
            if (found || (steps == 3 && (!force || sprint_reach() < 3))) {
                break;
            }
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
                    if (c2 < 0 || c2 == start) {
                        continue;
                    }
                    int const free2 = enter_time[c2];
                    if (!(free2 == 0 || (free2 == 2 && !pearl_here[c1]))) {
                        continue;
                    }
                    if (steps == 2) {
                        if (threat_at(c2) > 0 || (long_wary() && risk_at(c2) > 0) ||
                            (CUT_BODY_STRIDE && CUT_BODY_LEN > 0 && real_queen() && queen_margin(c2) <= 0)) {
                            continue;
                        }
                        if (evals++ >= max_evals || (CELL_BUDGET > 0 && turn_cells > CELL_BUDGET)) {
                            return found;
                        }
                        double const score = score_step(position_of(c2)) - (sprint_free() >= 2 ? 0.0 : SPRINT_ESCAPE_COST);
                        if (score > best) {
                            best = score;
                            path = {first, second};
                            found = true;
                        }
                        continue;
                    }
                    if (free2 != 0) {
                        continue;
                    }
                    Position const p2 = position_of(c2);
                    for (Direction const third : Direction::get_direction_list()) {
                        if (third == second.get_opposite() || edge_at(p2, third) == EDGE_PORTAL) {
                            continue;
                        }
                        int const c3 = step_index(p2, third);
                        if (c3 < 0 || c3 == start || c3 == c1 || threat_at(c3) > 0 || (long_wary() && risk_at(c3) > 0) ||
                            (CUT_BODY_STRIDE && CUT_BODY_LEN > 0 && real_queen() && queen_margin(c3) <= 0)) {
                            continue;
                        }
                        int const free3 = enter_time[c3];
                        if (!(free3 == 0 || (free3 <= 3 && free3 >= 2 && !pearl_here[c1] && !pearl_here[c2]))) {
                            continue;
                        }
                        if (evals++ >= max_evals || (CELL_BUDGET > 0 && turn_cells > CELL_BUDGET)) {
                            return found;
                        }
                        double const score = score_step(position_of(c3)) - std::max(0, 3 - sprint_free()) * SPRINT_ESCAPE_COST;
                        if (score > best) {
                            best = score;
                            path = {first, second, third};
                            found = true;
                        }
                    }
                }
            }
        }
        return found;
    }

    bool entry_dead_end(double room, bool reaches_tail) const {
        return (tail_index >= 0 || (QUEEN_DEAD_END && dead_queen())) && !reaches_tail && room < 3.0 * length + 8.0;
    }

    bool entry_pocket_full(int cell, int pocket) const {
        int const grown = length + (pearl_here[cell] ? 1 : 0);
        return POCKET_CAP > 0 && pocket < POCKET_CAP && grown > pocket / POCKET_DIV;
    }

    bool entry_portal_dead(bool usable, bool dead) const {
        return HARVEST_PORTAL && usable && dead && !real_queen();
    }

    struct TargetRoom {
        int pocket = 0;
        bool dead = false;
        bool harvest = false;
    };

    struct TargetState {
        bool ready = false;
        bool building = false;
        int pocket_count = 0;
        std::vector<int> room;
        std::vector<TargetRoom> rooms;
    };

    static TargetState& target_state() {
        static TargetState state;
        return state;
    }

    // Cache closed pocket facts once; target lookups inspect only their four edges.
    void target_prepare() {
        if (!TARGET_REACHABLE) {
            return;
        }
        TargetState& state = target_state();
        if (state.ready || state.building) {
            return;
        }
        state.building = true;
        state.room.assign(cells, -1);
        state.rooms.clear();
        bool inside = true;
        int const saved_back = survey_back;
        bool const saved_pessimist = survey_pessimist;
        bool const saved_no_portal = survey_no_portal;
        bool const saved_ally_block = survey_ally_block;
        survey_back = NO_REVERSE ? index_of(head) : -1;
        survey_pessimist = (QUEEN_PESSIMIST || (QG_PESSIMIST && queen_guard())) && is_queen();
        survey_no_portal = queen_portal_ban();
        survey_ally_block = (QUEEN_ALLY_BLOCK && is_queen()) || (ALLY_BLOCK_MAX_LEN > 0 && length <= ALLY_BLOCK_MAX_LEN);
        if (survey_ally_block) {
            mark_ally_block();
        }
        for (Direction const direction : Direction::get_direction_list()) {
            std::uint8_t const edge = edge_at(head, direction);
            if (edge == EDGE_KELP || edge == EDGE_PORTAL) {
                continue;
            }
            Position const destination = head.add_dir(direction);
            if (enter_time[index_of(destination)] > 1 ||
                (is_feeder() && !is_ally_head(destination) &&
                 (in_leader_keep_off(destination) || on_leader_ray(destination)))) {
                continue;
            }
            Survey const survey = survey_from(destination);
            if (!entry_dead_end(survey.area_seen + UNSEEN_DISCOUNT * survey.area_unseen, survey.reaches_tail)) {
                inside = false;
                break;
            }
        }
        survey_back = saved_back;
        survey_pessimist = saved_pessimist;
        survey_no_portal = saved_no_portal;
        survey_ally_block = saved_ally_block;
        if (POCKET_CAP > 0) {
            for (int cell = 0; cell < cells; cell++) {
                if (seen_round[cell] < 0 || state.room[cell] >= 0) {
                    continue;
                }
                int const pocket = pocket_size(cell);
                int const count = state.pocket_count;
                TargetRoom info;
                info.pocket = pocket;
                int pearls = 0;
                bool tail = false;
                bool confined = pocket < POCKET_CAP;
                bool portal_entry = false;
                for (int k = 0; k < count; k++) {
                    int const at = pocket_queue[k];
                    pearls += pearl_here[at] ? 1 : 0;
                    tail = tail || at == tail_index;
                    for (Direction const direction : Direction::get_direction_list()) {
                        if (edge_at(position_of(at), direction) != EDGE_PORTAL) {
                            continue;
                        }
                        int const exit = portal_exit(position_of(at), direction);
                        portal_entry = portal_entry || exit >= 0;
                        if (exit < 0 || (pocket_stamp[exit] != pocket_mark && enter_time[exit] <= pocket + 1)) {
                            confined = false;
                        }
                    }
                }
                info.dead = confined && entry_dead_end(pocket, tail);
                info.harvest = pocket < POCKET_CAP &&
                               (pocket_stamp[index_of(head)] == pocket_mark ||
                                entry_portal_dead(portal_entry, true)) &&
                               harvestable(pearls, 0.0, inside);
                int const id = static_cast<int>(state.rooms.size());
                state.rooms.push_back(info);
                for (int k = 0; k < count; k++) {
                    state.room[pocket_queue[k]] = id;
                }
            }
        }
        state.building = false;
        state.ready = true;
    }

    bool target_reachable(int cell) const {
        if (!TARGET_REACHABLE) {
            return true;
        }
        TargetState const& state = target_state();
        if (!state.ready || state.building || state.room[cell] < 0) {
            return true;
        }
        TargetRoom const& room = state.rooms[state.room[cell]];
        if (room.harvest || (!room.dead && !entry_pocket_full(cell, room.pocket))) {
            return true;
        }
        Position const position = position_of(cell);
        for (Direction const direction : Direction::get_direction_list()) {
            std::uint8_t const edge = edge_at(position, direction);
            if (edge == EDGE_UNKNOWN) {
                return true;
            }
            if (edge == EDGE_PORTAL && portal_exit(position, direction) < 0) {
                return true;
            }
        }
        return false;
    }

    Survey survey_from(Position start, bool strict_bodies = false, bool expand_unseen = true) {
        if (TARGET_REACHABLE) {
            target_prepare();
        }
        Survey result;
        visit_mark++;

        int queue_head = 0;
        int queue_tail = 0;

        int const start_index = index_of(start);
        visit_stamp[start_index] = visit_mark;
        beyond_portal[start_index] = 0;
        step_count[start_index] = 1;
        eaten_count[start_index] = pearl_here[start_index];
        bfs_beyond[queue_tail] = 0;
        bfs_queue[queue_tail++] = start;

        bool const scouting = can_scout_portals();
        bool const guard = portal_guarded();
        while (queue_head < queue_tail) {
            if ((SURVEY_CAP > 0 && queue_head >= SURVEY_CAP) || (survey_cap_now > 0 && queue_head >= survey_cap_now)) {
                break;
            }
            bool const beyond = bfs_beyond[queue_head] != 0;
            Position const position = bfs_queue[queue_head++];
            int const index = index_of(position);
            if (beyond && !beyond_portal[index]) {
                continue;
            }
            int const steps = step_count[index];
            int const eaten = eaten_count[index];
            if (beyond) {
                if (index == tail_index) {
                    result.reaches_tail = true;
                }
            } else {
                int const theirs = rival_steps(index);
                double share = steps < theirs ? 1.0 : steps == theirs ? CONTESTED_SHARE : 0.0;
                if (ally_race_steps(index) < steps) {
                    share = 0.0;
                }
                if (seen_round[index] < 0) {
                    result.area_unseen++;
                    result.own_unseen += share * reach_discount(steps);
                } else {
                    result.area_seen++;
                    result.own_seen += share * territory_weight(index) * reach_discount(steps);
                }
                if (index == tail_index) {
                    result.reaches_tail = true;
                }
                if (result.dist_feed < 0 && index == feed_index) {
                    result.dist_feed = steps;
                }
                if (result.dist_route < 0 && index == route_target) {
                    result.dist_route = steps;
                }
                bool const contest = (length <= CONTEST_MAX_LENGTH && steps <= theirs + CONTEST_SLACK &&
                                      ally_race_steps(index) >= steps) ||
                                     (CORPSE_SLACK > 0 && corpse_round[index] >= 0 &&
                                      round - corpse_round[index] <= CORPSE_FRESH && steps <= theirs + CORPSE_SLACK &&
                                      ally_race_steps(index) >= steps);
                if ((share >= 1.0 || contest) && result.dist_pearl < 0 && pearl_here[index] &&
                    !in_leader_pearl_zone(index) && (!TARGET_REACHABLE || target_reachable(index))) {
                    result.dist_pearl = steps;
                }
                if (share > 0.0 && pearl_here[index] && !in_leader_pearl_zone(index)) {
                    result.pearls++;
                }
                if (share >= 1.0 && result.dist_soon < 0 && seen_round[index] >= 0 && pearl_timer[index] >= 0 &&
                    !in_leader_pearl_zone(index) && (!TARGET_REACHABLE || target_reachable(index))) {
                    int const spawns_in = pearl_timer[index] - (round - seen_round[index]);
                    if (spawns_in <= steps + SOON_SLACK) {
                    
                        result.dist_soon = steps + std::max(0, spawns_in - steps);
                    }
                }
                if (hot[index] && result.dist_hot < 0 && ally_race_steps(index) >= steps &&
                    steps <= theirs + HOT_ENEMY_SLACK && !in_leader_pearl_zone(index) && (!TARGET_REACHABLE || target_reachable(index))) {
                    int const spawns_in = pearl_here[index] ? 0 : pearl_timer[index] - (round - seen_round[index]);
                    result.dist_hot = steps + std::max(0, spawns_in - steps);
                }
                if (result.dist_unseen < 0 && seen_round[index] < 0 &&
                    (!UNSEEN_CLAIM || feeding_phase() || ally_race_steps(index) >= steps)) {
                    result.dist_unseen = steps;
                }
            }
            if (!expand_unseen && seen_round[index] < 0) {
                continue;
            }

            for (Direction const direction : Direction::get_direction_list()) {
                if (survey_pessimist && edge_at(position, direction) == EDGE_UNKNOWN) {
                    continue;
                }
                if (survey_no_portal && edge_at(position, direction) == EDGE_PORTAL) {
                    continue;
                }
                if (qh_shut(position, direction)) {
                    continue;
                }
                int const next_index = step_index(position, direction);
                if (survey_back >= 0 && index == start_index && next_index == survey_back) {
                    continue;
                }
                if (survey_ally_block && next_index >= 0 && ally_block_stamp[next_index] == round) {
                    continue;
                }
                if (next_index < 0) {
                    if (scouting && result.dist_portal < 0 && leads_to_unknown(position, direction) &&
                        !(QG_SAFEZONE && zone_blocked(position, direction))) {
                        result.dist_portal = steps + 1;
                    }
                    continue;
                }
                bool const next_beyond = beyond || (guard && edge_at(position, direction) == EDGE_PORTAL &&
                                                    !portal_exit_safe(next_index));
                if (visit_stamp[next_index] == visit_mark && (next_beyond || !beyond_portal[next_index])) {
                    continue;
                }
                int const free_at = enter_time[next_index];
                if (free_at >= BLOCKED_FOREVER || steps + 1 - eaten < free_at) {
                    if (!next_beyond && result.dist_feed < 0 && next_index == feed_index) {
                        result.dist_feed = steps + 1;
                    }
                    if (!next_beyond && result.dist_trade < 0 && is_trade_target_cell(next_index)) {
                        result.dist_trade = steps + 1;
                    }
                    if (QH_SCOUT && !next_beyond && result.dist_route < 0 && qh_gate < 0 && next_index == qh_route) {
                        result.dist_route = steps + 1;
                    }
                    continue;
                }
                if (strict_bodies && free_at != 0) {
                    continue;
                }
                visit_stamp[next_index] = visit_mark;
                beyond_portal[next_index] = next_beyond ? 1 : 0;
                step_count[next_index] = steps + 1;
                eaten_count[next_index] = eaten + pearl_here[next_index];
                bfs_beyond[queue_tail] = next_beyond ? 1 : 0;
                bfs_queue[queue_tail++] = position_of(next_index);
            }
        }
        turn_cells += queue_tail;
        if (CROWD_MARGIN > 0.0) {
            for (std::size_t k = 0; k < ally_heads.size(); k++) {
                for (Direction const direction : Direction::get_direction_list()) {
                    int const near = step_index(ally_heads[k], direction);
                    if (near >= 0 && visit_stamp[near] == visit_mark) {
                        result.ally_load += visible_parts(ally_head_ids[k]) + CROWD_MARGIN;
                        break;
                    }
                }
            }
        }
        return result;
    }

    int center_distance(Position destination) {
        Position const center{width / 2, height / 2};
        if (!CENTER_PATH) {
            return manhattan(destination, center);
        }
        if (center_dist_round != round) {
            center_dist_round = round;
            center_dist.assign(cells, -1);
            std::vector<int> queue;
            queue.reserve(cells);
            center_dist[index_of(center)] = 0;
            queue.push_back(index_of(center));
            for (std::size_t head = 0; head < queue.size(); head++) {
                Position const position = position_of(queue[head]);
                for (Direction const direction : Direction::get_direction_list()) {
                    std::uint8_t const edge = edge_at(position, direction);
                    if (edge != EDGE_OPEN && edge != EDGE_UNKNOWN) {
                        continue;
                    }
                    int const next = index_of(position.add_dir(direction));
                    if (center_dist[next] >= 0) {
                        continue;
                    }
                    center_dist[next] = center_dist[queue[head]] + 1;
                    queue.push_back(next);
                }
            }
        }
        int const dist = center_dist[index_of(destination)];
        return dist >= 0 ? dist : manhattan(destination, center);
    }

    // Card #51: the centre rule is on for this dragon, but it has set no new nearest-to-centre mark for a while.
    bool stall_released() const {
        return TR_STALL_RELEASE && CENTER_PULL > 0.0 && center_map && round < center_rounds &&
               length <= CENTER_MAX_LENGTH && round - stall_round >= TR_STALL_ROUNDS;
    }

    // Card #51: a released dragon is pulled along real paths to the nearest unseen tile instead of to the centre.
    int stall_seek(int dist_unseen) const {
        return dist_unseen >= 0 ? std::min(dist_unseen, TR_STALL_SEEK) : TR_STALL_SEEK;
    }

    // Card #55: on for this turn; off on a turn she is trapped and moves as a plain dragon.
    bool fallback_on() const {
        return QUEEN_FALLBACK && fb_on && !qs_plain;
    }

    // Walking distance to `from` over open and unseen sides, bodies ignored, no portals.
    void fallback_walk(int from, std::vector<int>& dist) {
        dist.assign(cells, -1);
        fb_queue.clear();
        dist[from] = 0;
        fb_queue.push_back(from);
        for (std::size_t at = 0; at < fb_queue.size(); at++) {
            Position const position = position_of(fb_queue[at]);
            for (Direction const direction : Direction::get_direction_list()) {
                std::uint8_t const edge = edge_at(position, direction);
                if (edge != EDGE_OPEN && edge != EDGE_UNKNOWN) {
                    continue;
                }
                int const next = index_of(position.add_dir(direction));
                if (dist[next] >= 0) {
                    continue;
                }
                dist[next] = dist[fb_queue[at]] + 1;
                fb_queue.push_back(next);
            }
        }
    }

    // A free first step toward the target that no enemy head can reach this turn.
    bool fallback_way(std::vector<int> const& dist) const {
        int const here = dist[index_of(head)];
        for (Direction const direction : Direction::get_direction_list()) {
            if (edge_at(head, direction) != EDGE_OPEN) {
                continue;
            }
            Position const next = head.add_dir(direction);
            int const index = index_of(next);
            if (enter_time[index] <= 1 && dist[index] >= 0 && dist[index] < here && risk_at(index) == 0 &&
                !enemy_can_step_to(next)) {
                return true;
            }
        }
        return false;
    }

    // Card #55: counts the heads and, when outnumbered, picks the fall-back target for this turn.
    void fallback_update() {
        fb_on = false;
        fb_pull = false;
        fb_lead = false;
        if (!real_queen()) {
            return;
        }
        int const ours = 1 + static_cast<int>(ally_heads.size());
        // Enemy heads in view, and those she saw in the last GHOST_ROUNDS rounds.
        int const theirs =
            static_cast<int>(std::count_if(ghosts.begin(), ghosts.end(), [](Ghost const& g) { return !g.shared; }));
        fb_spots.erase(std::remove_if(fb_spots.begin(), fb_spots.end(),
                                      [this](Spot const& spot) { return round - spot.round > QF_MEMORY; }),
                       fb_spots.end());
        if (theirs < ours) {
            // More of ours than theirs: the tile of the nearest teammate head in view is remembered, with the margin.
            int nearest = -1;
            for (Position const& ally : ally_heads) {
                int const key = manhattan(head, ally) * cells + index_of(ally);
                if (nearest < 0 || key < nearest) {
                    nearest = key;
                }
            }
            if (nearest >= 0) {
                Position const seen = position_of(nearest % cells);
                // A sighting within QF_MERGE tiles of a remembered spot replaces it.
                fb_spots.erase(std::remove_if(fb_spots.begin(), fb_spots.end(),
                                              [&](Spot const& spot) {
                                                  return manhattan(position_of(spot.cell), seen) <= QF_MERGE;
                                              }),
                               fb_spots.end());
                if (static_cast<int>(fb_spots.size()) >= QF_SPOTS) {
                    fb_spots.erase(fb_spots.begin());
                }
                fb_spots.push_back(Spot{nearest % cells, ours - theirs, round});
            }
            return;
        }
        fb_on = true;
        int const here = index_of(head);
        fallback_walk(here, fb_other);
        // Outnumbered within QF_HOLD steps on foot of a spot: it is no longer a place with company.
        fb_spots.erase(std::remove_if(fb_spots.begin(), fb_spots.end(),
                                      [this](Spot const& spot) {
                                          return fb_other[spot.cell] >= 0 && fb_other[spot.cell] <= QF_HOLD;
                                      }),
                       fb_spots.end());
        // Spots by steps on foot, each extra head of margin worth QF_CROWD steps; the newer one on a tie.
        std::vector<std::array<int, 3>> order;
        for (std::size_t k = 0; k < fb_spots.size(); k++) {
            int const steps = fb_other[fb_spots[k].cell];
            if (steps >= 0) {
                order.push_back({steps - QF_CROWD * (fb_spots[k].margin - 1), steps, -static_cast<int>(k)});
            }
        }
        std::sort(order.begin(), order.end());
        // The first spot with an open way leads; all ways shut, keep-away leads and the first spot breaks ties.
        for (std::size_t k = 0; k < order.size() && !fb_lead; k++) {
            if (k == 1) {
                fb_dist.swap(fb_other);
            }
            fallback_walk(fb_spots[static_cast<std::size_t>(-order[k][2])].cell, fb_dist);
            fb_lead = fallback_way(fb_dist);
        }
        if (!order.empty()) {
            if (!fb_lead && order.size() > 1) {
                fb_dist.swap(fb_other);
            }
            fb_floor = 0;
            fb_pull = true;
            return;
        }
        // No spot left: her start tile is the last resort, and within QF_HOLD steps of it she holds.
        if (queen_home.x < 0) {
            return;
        }
        fallback_walk(index_of(queen_home), fb_dist);
        if (fb_dist[here] < 0) {
            return;
        }
        fb_lead = fb_dist[here] <= QF_HOLD || fallback_way(fb_dist);
        fb_floor = QF_HOLD;
        fb_pull = true;
    }

    // Steps gained on the fall-back target by ending on `cell`.
    int fallback_gain(int cell) const {
        return std::max(fb_dist[index_of(head)], fb_floor) - std::max(fb_dist[cell], fb_floor);
    }

    Herd& herd_state() const {
        static Herd herd;
        return herd;
    }

    void herd_update() {
        Herd& herd = herd_state();
        herd.on = false;
        herd.foes.clear();
        herd.ahead = 0;
        if (!real_queen() || is_leader() || ct.get_unit_count() < HERD_MIN_UNITS) {
            return;
        }
        for (std::size_t k = 0; k < ally_heads.size(); k++) {
            int const id = ally_head_ids[k];
            auto found = std::find_if(herd.mates.begin(), herd.mates.end(), [id](Mate const& m) { return m.id == id; });
            if (found == herd.mates.end()) {
                herd.mates.push_back(Mate{id, index_of(ally_heads[k]), round});
            } else {
                found->cell = index_of(ally_heads[k]);
                found->round = round;
            }
        }
        herd.mates.erase(std::remove_if(herd.mates.begin(), herd.mates.end(),
                                        [this](Mate const& m) { return round - m.round > INC_ALLY_MEMORY; }),
                         herd.mates.end());
        if (herd.mates.empty() || (POCKET_CAP > 0 && pocket_size(index_of(head)) < POCKET_CAP)) {
            return;
        }
        if (HERD_BEHIND > 0.0) {
            for (Ghost const& ghost : ghosts) {
                if (ghost.id == enemy_queen_id) {
                    continue;
                }
                int nearest = -1;
                for (Mate const& mate : herd.mates) {
                    int const gap = manhattan(position_of(mate.cell), ghost.pos);
                    if (round - mate.round <= GHOST_ROUNDS && (nearest < 0 || gap < nearest)) {
                        nearest = gap;
                    }
                }
                if (nearest >= 0) {
                    herd.foes.emplace_back(index_of(ghost.pos), nearest);
                }
            }
            herd.ahead = herd_ahead(index_of(head));
        }
        if (ally_heads.size() >= 2) {
            return;
        }
        herd.dist.assign(cells, -1);
        herd.queue.clear();
        for (Mate const& mate : herd.mates) {
            if (herd.dist[mate.cell] < 0) {
                herd.dist[mate.cell] = 0;
                herd.queue.push_back(mate.cell);
            }
        }
        for (std::size_t at = 0; at < herd.queue.size(); at++) {
            Position const position = position_of(herd.queue[at]);
            for (Direction const direction : Direction::get_direction_list()) {
                std::uint8_t const edge = edge_at(position, direction);
                if (edge != EDGE_OPEN && edge != EDGE_UNKNOWN) {
                    continue;
                }
                int const next = index_of(position.add_dir(direction));
                if (herd.dist[next] >= 0) {
                    continue;
                }
                herd.dist[next] = herd.dist[herd.queue[at]] + 1;
                herd.queue.push_back(next);
            }
        }
        herd.on = herd.dist[index_of(head)] >= 0;
    }

    int herd_ahead(int cell) const {
        int ahead = 0;
        for (auto const& foe : herd_state().foes) {
            ahead = std::max(ahead, foe.second - manhattan(position_of(cell), position_of(foe.first)));
        }
        return ahead;
    }

    int herd_gain(int cell) const {
        Herd const& herd = herd_state();
        if (!herd.on || herd.dist[cell] < 0) {
            return 0;
        }
        int const gap = unswbc::Constants::VISION_RADIUS;
        return std::max(herd.dist[index_of(head)], gap) - std::max(herd.dist[cell], gap);
    }

    bool portal_into_pocket(Position position, Direction direction) {
        if (!POCKET_PORTAL_BAN || POCKET_CAP <= 0) {
            return false;
        }
        int const exit = portal_exit(position, direction);
        return exit >= 0 && pocket_size(exit) < POCKET_CAP;
    }

    // Tiles reachable from `start` over seen tiles and known open edges only, counted up to `limit`.
    // Reaching the known tail counts as enough room.
    int known_room(int start, int limit) {
        if (known_stamp.size() != static_cast<std::size_t>(cells)) {
            known_stamp.assign(cells, 0);
            known_steps.assign(cells, 0);
            known_eaten.assign(cells, 0);
            known_queue.assign(cells, 0);
        }
        known_mark++;
        int queue_head = 0;
        int queue_tail = 0;
        known_stamp[start] = known_mark;
        known_steps[start] = 1;
        known_eaten[start] = pearl_here[start];
        known_queue[queue_tail++] = start;
        while (queue_head < queue_tail && queue_tail < limit) {
            int const index = known_queue[queue_head++];
            Position const position = position_of(index);
            for (Direction const direction : Direction::get_direction_list()) {
                if (edge_at(position, direction) != EDGE_OPEN) {
                    continue;
                }
                int const next = index_of(position.add_dir(direction));
                if (known_stamp[next] == known_mark || seen_round[next] < 0) {
                    continue;
                }
                int const free_at = enter_time[next];
                if (free_at >= BLOCKED_FOREVER || known_steps[index] + 1 - known_eaten[index] < free_at) {
                    continue;
                }
                if (next == tail_index) {
                    return limit;
                }
                known_stamp[next] = known_mark;
                known_steps[next] = known_steps[index] + 1;
                known_eaten[next] = known_eaten[index] + pearl_here[next];
                known_queue[queue_tail++] = next;
            }
        }
        return std::min(queue_tail, limit);
    }

    int pocket_size(int start) {
        if (pocket_stamp.size() != static_cast<std::size_t>(cells)) {
            pocket_stamp.assign(cells, 0);
            pocket_queue.assign(static_cast<std::size_t>(POCKET_CAP) + 4, 0);
        }
        pocket_mark++;
        pocket_doors.clear();
        int queue_head = 0;
        int queue_tail = 0;
        pocket_stamp[start] = pocket_mark;
        pocket_queue[queue_tail++] = start;
        if (TARGET_REACHABLE) {
            target_state().pocket_count = queue_tail;
        }
        while (queue_head < queue_tail) {
            Position const position = position_of(pocket_queue[queue_head++]);
            for (Direction const direction : Direction::get_direction_list()) {
                std::uint8_t const edge = edge_at(position, direction);
                if (edge == EDGE_UNKNOWN) {
                    return POCKET_CAP;
                }
                if (edge != EDGE_OPEN) {
                    if (POCKET_LOOP && edge == EDGE_PORTAL) {
                        Position const across = position.add_dir(direction);
                        int const exit = portal_exit(position, direction);
                        if (exit >= 0 && across.x >= 0 && across.x < width && across.y >= 0 && across.y < height) {
                            pocket_doors.push_back(index_of(across));
                            pocket_doors.push_back(exit);
                        }
                    }
                    continue;
                }
                int const next = index_of(position.add_dir(direction));
                if (pocket_stamp[next] == pocket_mark) {
                    continue;
                }
                if (queue_tail >= POCKET_CAP) {
                    return POCKET_CAP;
                }
                pocket_stamp[next] = pocket_mark;
                pocket_queue[queue_tail++] = next;
                if (TARGET_REACHABLE) {
                    target_state().pocket_count = queue_tail;
                }
            }
        }
        for (std::size_t k = 0; k + 1 < pocket_doors.size(); k += 2) {
            if (pocket_stamp[pocket_doors[k]] == pocket_mark && pocket_stamp[pocket_doors[k + 1]] != pocket_mark) {
                return POCKET_CAP;
            }
        }
        return queue_tail;
    }

    double reach_discount(int steps) {
        if (TERRITORY_DECAY <= 0.0) {
            return 1.0;
        }
        if (discount_table.empty()) {
            discount_table.resize(static_cast<std::size_t>(cells) + 2);
            for (std::size_t k = 0; k < discount_table.size(); k++) {
                discount_table[k] = std::exp(-static_cast<double>(k) / TERRITORY_DECAY);
            }
        }
        return discount_table[static_cast<std::size_t>(std::clamp(steps - 1, 0, cells + 1))];
    }

    double territory_weight(int index) const {
        if (TARGET_REACHABLE && !target_reachable(index)) {
            return BARREN_TERRITORY;
        }
        if (pearl_here[index]) {
            return 1.0;
        }
        if (pearl_timer[index] < 0) {
            return BARREN_TERRITORY;
        }
        double const rate = RATE_EXP > 0.0 ? rate_factor(index) : 1.0;
        if (TERRITORY_TIME_SCALE <= 0.0) {
            return rate;
        }
        int const spawns_in = std::max(0, pearl_timer[index] - (round - seen_round[index]));
        return rate * TERRITORY_TIME_SCALE / (TERRITORY_TIME_SCALE + spawns_in);
    }

    double rate_factor(int index) const {
        double const gap = std::max(2, timer_max[index] + 1);
        return std::min(RATE_CAP, std::pow(RATE_REF_GAP / gap, RATE_EXP));
    }

    double look_cell_value(int cell, int t) const {
        if (TARGET_REACHABLE && t > 1 && !target_reachable(cell)) {
            return 0.0;
        }
        double found = 0.0;
        if (pearl_here[cell]) {
            found = 1.0;
        } else if (LOOK_SOON > 0.0 && seen_round[cell] >= 0 && pearl_timer[cell] >= 0) {
            int const spawns_in = pearl_timer[cell] - (round - seen_round[cell]);
            if (spawns_in >= 1 && spawns_in <= t) {
                found = LOOK_SOON;
            }
        }
        if (found <= 0.0 || in_leader_pearl_zone(cell)) {
            return 0.0;
        }
        int const theirs = rival_steps(cell);
        double share = t < theirs ? 1.0 : t == theirs ? CONTESTED_SHARE : 0.0;
        if (ally_race_steps(cell) < t) {
            share = 0.0;
        }
        double const turns = TURN_DIST ? static_cast<double>(t - 1) / std::max(1, sprint_free()) : t - 1;
        return LOOK_PEARL * found * share * std::pow(LOOK_DISCOUNT, turns);
    }

    double look_extend(int cell, int t, int eaten) {
        if (t >= LOOK_DEPTH) {
            return 0.0;
        }
        double best = 0.0;
        Position const position = position_of(cell);
        for (Direction const direction : Direction::get_direction_list()) {
            std::uint8_t const edge = edge_at(position, direction);
            if (edge == EDGE_KELP || edge == EDGE_PORTAL) {
                continue;
            }
            int const next = index_of(position.add_dir(direction));
            int free_at = enter_time[next];
            for (std::size_t k = 0; k < look_cells.size(); k++) {
                if (look_cells[k] == next) {
                    free_at = std::max(free_at, static_cast<int>(k) + 2 + length);
                }
            }
            if (t + 1 - eaten < free_at) {
                continue;
            }
            double gain = look_cell_value(next, t + 1);
            look_cells.push_back(next);
            gain += look_extend(next, t + 1, eaten + (pearl_here[next] ? 1 : 0));
            look_cells.pop_back();
            best = std::max(best, gain);
        }
        return best;
    }

    double look_gain(int first) {
        look_cells.assign(1, first);
        double const gain = look_cell_value(first, 1) + look_extend(first, 1, pearl_here[first] ? 1 : 0);
        look_cells.clear();
        return gain;
    }

    double target_bonus(int distance, double weight) const {
        if (distance < 0) {
            return 0.0;
        }
        double const reach = TURN_DIST ? static_cast<double>(distance) / std::max(1, sprint_free()) : distance;
        return std::max(0.0, weight * (TARGET_REWARD - TARGET_DECAY * reach));
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
    void update_lifecycle() {
        if (ASSASSIN_MOD > 0) {
            for (std::size_t k = 0; k < enemy_heads.size(); k++) {
                int const parts = visible_parts(enemy_head_ids[k]);
                if (parts >= ASSASSIN_TARGET && (big_enemy_round != round || parts > big_enemy_parts)) {
                    big_enemy_round = round;
                    big_enemy_parts = parts;
                    big_enemy_pos = enemy_heads[k];
                }
            }
        }
        if (LC_ENEMY_LEAD <= 0 && LC_ENEMY_FEED <= 0) {
            return;
        }
        int biggest = 0;
        for (std::size_t k = 0; k < enemy_heads.size(); k++) {
            biggest = std::max(biggest, visible_parts(enemy_head_ids[k]));
        }
        enemy_big_seen = std::max(enemy_big_seen, biggest);
        if (LC_ENEMY_LEAD > 0 && enemy_big_seen >= LC_ENEMY_LEAD && round < grow_round) {
            grow_round = round;
        }
        if (LC_ENEMY_FEED > 0 && enemy_big_seen >= LC_ENEMY_FEED && round < feed_round) {
            feed_round = round;
        }
    }

    bool attack_units_ok() const {
        return ATTACK_MIN_UNITS <= 0 || ct.get_unit_count() >= ATTACK_MIN_UNITS;
    }

    bool board_short() const {
        return LEADER_FULL_UNITS > 0 && !aggressive && !feeding_phase() && ct.get_unit_count() < LEADER_FULL_UNITS;
    }

    bool is_leader() const {
        return round > grow_round && known_leader_id == ct.get_id() && !(board_short() && length < LEADER_FULL_KEEP);
    }

    bool is_queen() const {
        return QUEEN_MODE && ct.get_id() == queen_id && (cells > QUEEN_MIN_CELLS || home_closed);
    }

    // The queen for the dead-end terms: with QUEEN_DEAD_ALL on every board size.
    bool dead_queen() const {
        return QUEEN_DEAD_ALL ? QUEEN_MODE && real_queen() : is_queen();
    }

    bool queen_guard() const {
        return QUEEN_GUARD_CELLS > 0 && cells > QUEEN_GUARD_CELLS && is_queen();
    }

    void ensure_queen_buffers() {
        std::size_t const cells = static_cast<std::size_t>(width * height);
        if (qk_margin.size() != cells) {
            qk_margin.assign(cells, 0);
            qk_stamp.assign(cells, 0);
            qb_seen.assign(cells, 0);
            qb_dist.assign(cells, 0);
            qb_queue.assign(cells, 0);
        }
    }

    int queen_margin(int cell) const {
        return qk_stamp[cell] == qk_mark ? qk_margin[cell] : QB_MARGIN_CAP + 1;
    }

    int enemy_reach(int parts) const {
        int const size = std::max(parts, static_cast<int>(unswbc::Constants::MIN_SIZE));
        return std::clamp((size + 3) / 4 + size - static_cast<int>(unswbc::Constants::MIN_SIZE), 1, QB_REACH_CAP);
    }

    void spread_kill(Position from, int reach) {
        qb_mark++;
        int queue_head = 0;
        int queue_tail = 0;
        int const origin = index_of(from);
        qb_seen[origin] = qb_mark;
        qb_dist[origin] = 0;
        qb_queue[queue_tail++] = origin;
        int const limit = reach + QB_MARGIN_CAP;
        while (queue_head < queue_tail) {
            int const index = qb_queue[queue_head++];
            int const steps = qb_dist[index];
            if (steps > 0) {
                int const margin = steps - reach;
                if (qk_stamp[index] != qk_mark || margin < qk_margin[index]) {
                    qk_stamp[index] = qk_mark;
                    qk_margin[index] = margin;
                }
            }
            if (steps >= limit) {
                continue;
            }
            Position const position = position_of(index);
            for (Direction const direction : Direction::get_direction_list()) {
                int const next = step_index(position, direction);
                if (next < 0 || qb_seen[next] == qb_mark || enter_time[next] >= BLOCKED_FOREVER) {
                    continue;
                }
                qb_seen[next] = qb_mark;
                qb_dist[next] = steps + 1;
                qb_queue[queue_tail++] = next;
            }
        }
    }

    void queen_kill_map() {
        ensure_queen_buffers();
        qk_mark++;
        if (QB_W_DANGER > 0.0) {
            danger_log.erase(std::remove_if(danger_log.begin(), danger_log.end(),
                                            [this](std::tuple<Position, int, int> const& seen) { return round - std::get<1>(seen) > QB_DANGER_ROUNDS; }),
                             danger_log.end());
            for (std::size_t k = 0; k < enemy_heads.size(); k++) {
                danger_log.emplace_back(enemy_heads[k], round, enemy_head_ids[k]);
            }
            for (Ghost const& ghost : ghosts) {
                if (ghost.shared && ghost.round == round) {
                    danger_log.emplace_back(ghost.pos, round, ghost.id);
                }
            }
        }
        for (std::size_t k = 0; k < enemy_heads.size(); k++) {
            int parts = visible_parts(enemy_head_ids[k]);
            for (Ghost const& ghost : ghosts) {
                if (ghost.id == enemy_head_ids[k]) {
                    parts = std::max(parts, ghost.parts);
                }
            }
            if (CUT_BODY_LEN > 0 && real_queen()) {
                parts = queen_enemy_parts(enemy_head_ids[k]);
            }
            if (CUT_BODY_STRIDE && CUT_BODY_LEN > 0 && real_queen()) {
                spread_kill(enemy_heads[k], std::max(enemy_reach(parts), cut_stride_reach(enemy_head_ids[k])));
            } else {
                spread_kill(enemy_heads[k], enemy_reach(parts));
            }
        }
        if (QUEEN_FAR_HEADS > 0 && real_queen()) {
            for (Ghost const& g : far_sight().heads) {
                spread_kill(g.pos, enemy_reach(g.parts));
            }
        }
        for (Ghost const& ghost : ghosts) {
            if (ghost.round == round && !ghost.shared) {
                continue;
            }
            int const age = round - ghost.round;
            if (age > QB_GHOST_AGE) {
                continue;
            }
            if (CUT_BODY_LEN > 0 && real_queen() && visible_parts(ghost.id) > 0) {
                if (CUT_BODY_STRIDE && CUT_BODY_LEN > 0 && real_queen()) {
                    spread_kill(ghost.pos, std::max(enemy_reach(queen_enemy_parts(ghost.id)), cut_stride_reach(ghost.id)) + age);
                } else {
                    spread_kill(ghost.pos, enemy_reach(queen_enemy_parts(ghost.id)) + age);
                }
            } else {
                spread_kill(ghost.pos, enemy_reach(ghost.parts) + age);
            }
        }
    }

    double queen_eval(std::vector<int> const& body, int len, int eaten, int paid, std::vector<int> const& ate) {
        qb_evals++;
        int const end = body.front();
        int const danger = queen_margin(end);
        int const tail = static_cast<int>(body.size()) == len ? body.back() : -1;
        qb_mark++;
        int queue_head = 0;
        int queue_tail = 0;
        qb_seen[end] = qb_mark;
        qb_dist[end] = 0;
        qb_queue[queue_tail++] = end;
        int count = 0;
        bool reaches_tail = false;
        int dist_pearl = -1;
        int dist_unseen = -1;
        while (queue_head < queue_tail && count < QB_BFS_CAP) {
            int const index = qb_queue[queue_head++];
            int const steps = qb_dist[index];
            count++;
            if (steps > 0 && dist_pearl < 0 && pearl_here[index] && std::find(ate.begin(), ate.end(), index) == ate.end() &&
                (!TARGET_REACHABLE || target_reachable(index))) {
                dist_pearl = steps;
            }
            if (dist_unseen < 0 && seen_round[index] != round) {
                dist_unseen = steps;
            }
            Position const position = position_of(index);
            for (Direction const direction : Direction::get_direction_list()) {
                std::uint8_t const edge = edge_at(position, direction);
                if (edge == EDGE_KELP || edge == EDGE_PORTAL) {
                    continue;
                }
                int const next = index_of(position.add_dir(direction));
                if (qb_seen[next] == qb_mark || enter_time[next] >= BLOCKED_FOREVER) {
                    continue;
                }
                if (next == tail) {
                    if (!QB_ROBUST_EXITS || steps > 0) {
                        reaches_tail = true;
                    }
                    continue;
                }
                auto const found = std::find(body.begin(), body.end(), next);
                if (found != body.end()) {
                    int const segment = static_cast<int>(found - body.begin());
                    if (!QB_TIMED_ROOM || steps + 1 < len - segment + 1) {
                        continue;
                    }
                    if (segment >= len - 2) {
                        reaches_tail = true;
                    }
                }
                qb_seen[next] = qb_mark;
                qb_dist[next] = steps + 1;
                qb_queue[queue_tail++] = next;
            }
        }
        if (danger <= 0) {
            return -1e7 + 1e5 * std::max(-10, danger) + count;
        }
        if (QB_TIMED_ROOM && count < len + QB_ROOM && !reaches_tail) {
            return -1e6 + 1e3 * count + QB_W_MARGIN * std::min(danger, QB_MARGIN_CAP) - QB_W_PAID * paid;
        }
        int options = 0;
        bool score_one_exit = false;
        Position const at = position_of(end);
        for (Direction const direction : Direction::get_direction_list()) {
            if (edge_at(at, direction) != EDGE_OPEN) {
                continue;
            }
            int const next = index_of(at.add_dir(direction));
            if (enter_time[next] >= BLOCKED_FOREVER || std::find(body.begin(), body.end(), next) != body.end()) {
                continue;
            }
            if (queen_margin(next) <= 0) {
                continue;
            }
            if (QB_ROBUST_EXITS) {
                bool crowded = false;
                for (Position const& other : ally_heads) {
                    crowded = crowded || manhattan(other, position_of(next)) <= 1;
                }
                for (Position const& other : enemy_heads) {
                    crowded = crowded || manhattan(other, position_of(next)) <= 1;
                }
                if (crowded) {
                    continue;
                }
            }
            options++;
        }
        if (QB_ROBUST_EXITS && options == 0) {
            return -1e6 + 1e3 * std::min(count, 50) + QB_W_MARGIN * std::min(danger, QB_MARGIN_CAP) - QB_W_PAID * paid;
        }
        if (QB_ROBUST_EXITS && options == 1) {
            options = 0;
            score_one_exit = true;
        }
        int ally_adjacent = 0;
        for (Position const& ally : ally_heads) {
            if (manhattan(ally, at) <= 1) {
                ally_adjacent++;
            }
        }
        double const need = static_cast<double>(len + QB_ROOM);
        double score = QB_W_MARGIN * std::min(danger, QB_MARGIN_CAP) - (score_one_exit ? QB_ONE_EXIT : 0.0);
        score += QB_W_ROOM * std::min(1.0, count / need);
        if (count < need && !reaches_tail) {
            score -= QB_DEAD;
        }
        if (reaches_tail) {
            score += QB_W_TAIL;
        }
        score += QB_W_OPT * std::min(options, 3);
        score += QB_W_UNSEEN * (dist_unseen < 0 ? 4 : std::min(dist_unseen, 4));
        score += QB_W_EAT * eaten - QB_W_PAID * paid;
        if (dist_pearl >= 0) {
            score += QB_W_PEARL * std::max(0, 10 - dist_pearl);
        }
        score -= QB_W_ALLY * ally_adjacent;
        if (QB_W_ESCORT > 0.0) {
            int escorts = 0;
            for (Position const& ally : ally_heads) {
                int const gap = manhattan(ally, at);
                if (gap > 1 && gap <= QB_ESCORT_RADIUS) {
                    escorts++;
                }
            }
            score += QB_W_ESCORT * std::min(escorts, 2);
        }
        if (QB_W_DANGER > 0.0) {
            double heat = 0.0;
            for (auto const& seen : danger_log) {
                int const age = round - std::get<1>(seen);
                int const gap = manhattan(std::get<0>(seen), at);
                if (age <= QB_DANGER_ROUNDS && gap <= QB_DANGER_RADIUS) {
                    heat += static_cast<double>(QB_DANGER_RADIUS + 1 - gap) / (QB_DANGER_RADIUS + 1) * (1.0 - static_cast<double>(age) / (QB_DANGER_ROUNDS + 1));
                }
            }
            score -= QB_W_DANGER * heat;
        }
        return score;
    }

    void queen_search(std::vector<int>& body, int len, int depth, int free_steps, int eaten, int paid, std::vector<int>& ate) {
        if (depth >= QB_MAX_STEPS || qb_evals >= QB_EVAL_MAX) {
            return;
        }
        Position const at = position_of(body.front());
        for (Direction const direction : Direction::get_direction_list()) {
            if (edge_at(at, direction) != EDGE_OPEN) {
                continue;
            }
            int const next = index_of(at.add_dir(direction));
            if (seen_round[next] != round || enter_time[next] >= BLOCKED_FOREVER) {
                continue;
            }
            if (std::find(body.begin(), body.end(), next) != body.end()) {
                continue;
            }
            bool const pay = depth + 1 > free_steps;
            if (pay && (paid >= QB_MAX_PAID || len <= static_cast<int>(unswbc::Constants::MIN_SIZE))) {
                continue;
            }
            bool const eat = pearl_here[next] && std::find(ate.begin(), ate.end(), next) == ate.end();
            std::vector<int> moved = body;
            moved.insert(moved.begin(), next);
            int const moved_len = len + (eat ? 1 : 0) - (pay ? 1 : 0);
            while (static_cast<int>(moved.size()) > moved_len) {
                moved.pop_back();
            }
            if (eat) {
                ate.push_back(next);
            }
            qb_path.push_back(direction);
            double const score = queen_eval(moved, moved_len, eaten + (eat ? 1 : 0), paid + (pay ? 1 : 0), ate);
            if (score > qb_best_score) {
                qb_best_score = score;
                qb_best = qb_path;
            }
            queen_search(moved, moved_len, depth + 1, free_steps, eaten + (eat ? 1 : 0), paid + (pay ? 1 : 0), ate);
            qb_path.pop_back();
            if (eat) {
                ate.pop_back();
            }
        }
    }

    bool queen_act() {
        queen_kill_map();
        int const child = split_child_size();
        if (child > 0 && queen_margin(index_of(head)) >= QB_SPLIT_MARGIN) {
            split_off(child);
            return true;
        }
        std::vector<int> body;
        for (Position const& cell : trail) {
            body.push_back(index_of(cell));
        }
        std::vector<int> ate;
        qb_best.clear();
        qb_path.clear();
        qb_best_score = -1e18;
        qb_evals = 0;
        queen_search(body, length, 0, sprint_free(), 0, 0, ate);
        if (qb_best.empty()) {
            return false;
        }
        if (qb_best.size() == 1) {
            ct.make_move(qb_best.front());
        } else {
            ct.make_moves(qb_best);
        }
        act_dirs = qb_best;
        remember_path(qb_best);
        return true;
    }

    int sprint_reach() const {
        if (SPRINT_FREE_DIV <= 0) {
            return length - 1;
        }
        return (length + SPRINT_FREE_DIV - 1) / SPRINT_FREE_DIV + length - unswbc::Constants::MIN_SIZE;
    }

    int sprint_free() const {
        return SPRINT_FREE_DIV <= 0 ? 1 : (length + SPRINT_FREE_DIV - 1) / SPRINT_FREE_DIV;
    }

    bool enemy_near(Position cell, int radius) const {
        for (Position const& enemy : enemy_heads) {
            if (manhattan(enemy, cell) <= radius) {
                return true;
            }
        }
        for (Ghost const& ghost : ghosts) {
            if ((ghost.round != round || ghost.shared) && manhattan(ghost.pos, cell) <= radius + round - ghost.round) {
                return true;
            }
        }
        return false;
    }

    bool is_assassin() const {
        return ASSASSIN_MOD > 0 && feeding_phase() && !is_leader() && !is_queen() && !queen_aloof() && length >= ASSASSIN_MIN &&
               length <= ASSASSIN_MAX && ct.get_id() % ASSASSIN_MOD == 0 && big_enemy_round >= 0 &&
               round - big_enemy_round <= ASSASSIN_FRESH;
    }

    bool is_trader() const {
        if (QUEEN_SAFETY && real_queen()) {
            return length <= TRADE_MAX_LENGTH && !is_leader() && trade_targets > 0;
        }
        return length <= TRADE_MAX_LENGTH && !is_leader() && (!is_queen() || (QUEEN_TRADE_SMALL && aggressive)) && trade_targets > 0;
    }

    bool can_scout_portals() const {
        
        return length <= PORTAL_SCOUT_MAX_LENGTH && !is_feeder() &&
               !is_leader() && (!is_queen() || round < QUEEN_PORTAL_ROUND) && !(QUEEN_PORTAL_ALL && real_queen()) && tail_index >= 0;
    }

    bool queen_portal_ban() const {
        return QUEEN_NO_PORTAL && (is_queen() || (QUEEN_PORTAL_ALL && real_queen())) && round >= QUEEN_PORTAL_ROUND;
    }

    bool queen_wait() {
        if (!QUEEN_WAIT || !real_queen() || length < QW_MIN_LENGTH || !(ct.can_split(unswbc::Constants::MIN_SIZE) && !(QUEEN_BOOT_LEN > 0 && queen_booting()))) {
            return false;
        }
        bool const cramped = chosen_scored && !chosen_reaches_tail && chosen_room < length + 2.0;
        bool const outlasts = QW_END_ROOM > 0 && chosen_room >= QW_END_ROOM * (unswbc::Constants::MAX_ROUNDS - round);
        bool const stuck = !any_enterable || (cramped && !outlasts);
        if (!stuck) {
            return false;
        }
        bool ally_block = false;
        for (Direction const direction : Direction::get_direction_list()) {
            if (edge_at(head, direction) == EDGE_KELP) {
                continue;
            }
            int const next = step_index(head, direction);
            if (next < 0) {
                continue;
            }
            if ((is_enemy_head(position_of(next)) || threat_at(next) > 1) && !(QW_ANY_BLOCK && !any_enterable)) {
                return false;
            }
            if (ally_part_stamp[next] == round) {
                ally_block = true;
            }
        }
        return ally_block || QW_ANY_BLOCK;
    }

    bool queen_booting() const {
        return feeding_phase() && real_queen() && length < QUEEN_BOOT_LEN;
    }

    bool real_queen() const {
        return QUEEN_MODE && ct.get_id() == queen_id;
    }

    bool queen_aloof() const {
        return QUEEN_NO_FEED && real_queen();
    }

    // Queen threat handling: with QUEEN_SAFETY on every map, except on a turn she is trapped.
    bool queen_wary() const {
        return QUEEN_SAFETY ? real_queen() && !qs_plain : is_queen();
    }

    // Card #54: a long dragon under the ring veto; the queen keeps her own rules.
    bool long_wary() const {
        return LONG_SAFETY && length >= LS_MIN_LENGTH && !real_queen();
    }

    bool ring_wary() const {
        return (QUEEN_SAFETY && queen_wary()) || long_wary();
    }

    // Card #54: no clean step left: a free stride, then a sprint paying at most LS_ESCAPE_COST, then a split, then
    // the least bad tile.
    bool long_stuck(std::vector<Direction>& path) {
        int const keep = unswbc::Constants::MIN_SIZE;
        auto run = [&]() {
            ct.make_moves(path);
            act_dirs = path;
            remember_path(path);
            return true;
        };
        if (hit_escape(path, false, 0) || hit_escape(path, true, 0)) {
            return run();
        }
        // The head keeps 2 where it stands and the rest leaves from the tail end, when that end is clean.
        if (tail_index >= 0 && risk_at(tail_index) == 0 && (ct.can_split(length - keep) && !(QUEEN_BOOT_LEN > 0 && queen_booting())) && tail_room() >= CHILD_MIN_ROOM) {
            split_off(length - keep);
            return true;
        }
        // Its own tile is clean: a 2-child off the tail and it stays.
        if (!hit_head && !pay_head && (ct.can_split(keep) && !(QUEEN_BOOT_LEN > 0 && queen_booting()))) {
            split_off(keep);
            return true;
        }
        int const step = least_bad();
        if (step < 0) {
            return false;
        }
        if (risk_at(step_dest[static_cast<std::size_t>(step)]) == 2 && (hit_escape(path, false, 1) || hit_escape(path, true, 1))) {
            return run();
        }
        Direction const direction = Direction::get_direction_list()[static_cast<std::size_t>(step)];
        ct.make_move(direction);
        act_dirs.assign(1, direction);
        return true;
    }

    // Card #54: the step when every step is in reach: an open tile over a pocket, a pay-ring tile over a hit-ring
    // one, then the tile fewer enemy heads reach.
    int least_bad() const {
        int best = -1;
        std::array<int, 4> best_key{};
        for (int k = 0; k < 4; k++) {
            std::size_t const slot = static_cast<std::size_t>(k);
            int const dest = step_dest[slot];
            if (dest < 0 || step_score[slot] <= SCORE_REJECT * 0.5) {
                continue;
            }
            bool const marked = risk_at(dest) > 0;
            std::array<int, 4> const key{step_closed[slot] ? 1 : 0, risk_at(dest), marked ? hit_count[dest] : 0,
                                         marked ? pay_count[dest] : 0};
            if (best < 0 || key < best_key ||
                (key == best_key && step_score[slot] > step_score[static_cast<std::size_t>(best)])) {
                best = k;
                best_key = key;
            }
        }
        return best;
    }

    Foe const* foe_of(int id) const {
        auto const found = std::find_if(foes.begin(), foes.end(), [id](Foe const& foe) { return foe.id == id; });
        return found == foes.end() ? nullptr : &*found;
    }

    // Card #54: how much of each enemy, the enemy queen aside, has been in view.
    void note_foes() {
        for (int const id : foe_now) {
            if (id == enemy_queen_id) {
                continue;
            }
            auto found = std::find_if(foes.begin(), foes.end(), [id](Foe const& foe) { return foe.id == id; });
            if (found == foes.end()) {
                foes.push_back(Foe{id});
                found = foes.end() - 1;
            }
            if (found->round == round) {
                continue;
            }
            int const seen = visible_parts(id);
            found->round = round;
            found->last = seen;
            found->cut = std::find(edge_ids.begin(), edge_ids.end(), id) != edge_ids.end();
            found->most = std::max(found->most, seen);
            if (!found->cut && std::find(enemy_head_ids.begin(), enemy_head_ids.end(), id) != enemy_head_ids.end()) {
                found->whole = std::max(found->whole, seen);
            }
            foe_longest = std::max(foe_longest, seen);
        }
    }

    // Card #54: an enemy whose body runs out of view: the most we have seen of it if we know its whole length, else
    // the longest enemy we have seen; never the stub in view.
    int foe_size(int id, int seen) const {
        Foe const* const foe = foe_of(id);
        int const known = foe && foe->whole > seen ? foe->most : foe_longest;
        return std::max({known, seen + 1, static_cast<int>(unswbc::Constants::INITIAL_LENGTH)});
    }

    int ghost_size(Ghost const& ghost) const {
        Foe const* const foe = foe_of(ghost.id);
        return foe && foe->cut ? std::max(ghost.parts, foe_size(ghost.id, foe->last)) : ghost.parts;
    }

    // Card #54: how many heads reach the tile, for free and at all. Call before stamping it.
    void count_hit(int index, bool free) {
        if (pay_stamp[index] != hit_mark) {
            hit_count[index] = 0;
            pay_count[index] = 0;
        }
        hit_count[index] += free ? 1 : 0;
        pay_count[index]++;
    }

    static std::unordered_map<int, int>& cut_lengths() {
        static std::unordered_map<int, int> lengths;
        return lengths;
    }

    void note_cut_lengths() {
        auto& lengths = cut_lengths();
        for (auto const& tile : ct.get_tiles()) {
            auto const* part = tile.get_dragon();
            if (part && part->get_team() != ct.get_team()) {
                int const id = part->get_id();
                lengths[id] = std::max(lengths[id], visible_parts(id));
            }
        }
        for (Ghost const& ghost : ghosts) {
            lengths[ghost.id] = std::max(lengths[ghost.id], ghost.parts);
        }
        for (Foe const& foe : foes) {
            lengths[foe.id] = std::max(lengths[foe.id], foe.most);
        }
    }

    // Only a body touching this turn's view edge uses remembered length.
    int queen_enemy_parts(int id) const {
        int const seen = visible_parts(id);
        if (std::find(edge_ids.begin(), edge_ids.end(), id) == edge_ids.end()) {
            return seen;
        }
        auto const& lengths = cut_lengths();
        auto const found = lengths.find(id);
        return std::max({seen, CUT_BODY_LEN, found == lengths.end() ? 0 : found->second});
    }

    bool on_view_edge(Position position) const {
        int const radius = unswbc::Constants::VISION_RADIUS;
        return torus_gap(position.x, head.x, width) == radius || torus_gap(position.y, head.y, height) == radius;
    }

    // Tiles a visible enemy head, the enemy queen aside, can enter this turn: on free steps (hit) or by paying length too (pay).
    void map_hits() {
        if (hit_stamp.empty()) {
            hit_stamp.assign(cells, 0);
            pay_stamp.assign(cells, 0);
            if (LONG_SAFETY) {
                hit_count.assign(cells, 0);
                pay_count.assign(cells, 0);
            }
        }
        hit_mark++;
        hit_round = round;
        hit_head = false;
        pay_head = false;
        int const keep = unswbc::Constants::MIN_SIZE;
        bool const longs = long_wary();
        for (std::size_t k = 0; k < enemy_heads.size(); k++) {
            if (enemy_head_ids[k] == enemy_queen_id) {
                continue;
            }
            int const seen = visible_parts(enemy_head_ids[k]);
            int parts = seen;
            for (Ghost const& ghost : ghosts) {
                if (ghost.id == enemy_head_ids[k]) {
                    parts = std::max(parts, ghost.parts);
                }
            }
            // A body running out of view may be longer than it looks.
            bool const cut = std::find(edge_ids.begin(), edge_ids.end(), enemy_head_ids[k]) != edge_ids.end();
            if (longs && cut) {
                parts = std::max(parts, foe_size(enemy_head_ids[k], seen));
            }
            if (CUT_BODY_LEN > 0 && real_queen()) {
                parts = queen_enemy_parts(enemy_head_ids[k]);
            }
            int const free = SPRINT_FREE_DIV > 0 ? std::max(1, (parts + SPRINT_FREE_DIV - 1) / SPRINT_FREE_DIV) : 1;
            int const size = CUT_BODY_LEN > 0 && real_queen() ? parts
                                 : cut ? std::max({parts, seen + 1, static_cast<int>(unswbc::Constants::INITIAL_LENGTH)}) : parts;
            int const full = (SPRINT_FREE_DIV > 0 ? (size + SPRINT_FREE_DIV - 1) / SPRINT_FREE_DIV : 1) + size - keep;
            bool const eats = REACH_EATS && real_queen();
            int const reach = eats ? std::max(free, QS_PAY_REACH)
                                  : longs ? std::min(full, free + LS_PAY_STEPS) : std::max(free, std::min(full, QS_PAY_REACH));
            visit_mark++;
            int const origin = index_of(enemy_heads[k]);
            visit_stamp[origin] = visit_mark;
            step_count[origin] = 0;
            bfs_queue[0] = enemy_heads[k];
            if (eats) {
                eaten_count[origin] = 0;
            }
            spread_hits(1, free, reach, eats ? size : 0);
        }
        if (QUEEN_FAR_HEADS > 0 && real_queen()) {
            for (Ghost const& g : far_sight().heads) {
                int const free = SPRINT_FREE_DIV > 0 ? std::max(1, (g.parts + SPRINT_FREE_DIV - 1) / SPRINT_FREE_DIV) : 1;
                int const full = free + g.parts - keep;
                int const reach = REACH_EATS ? std::max(free, QS_PAY_REACH) : std::max(free, std::min(full, QS_PAY_REACH));
                visit_mark++;
                int const origin = index_of(g.pos);
                visit_stamp[origin] = visit_mark;
                step_count[origin] = 0;
                if (REACH_EATS) {
                    eaten_count[origin] = 0;
                }
                bfs_queue[0] = g.pos;
                spread_hits(1, free, reach, REACH_EATS ? g.parts : 0);
            }
        }
        if (!longs) {
            return;
        }
        // Card #54: a head seen in the last rounds but not now rings the tiles around where it may stand.
        for (Ghost const& ghost : ghosts) {
            if (ghost.round == round || ghost.id == enemy_queen_id) {
                continue;
            }
            int const free = SPRINT_FREE_DIV > 0 ? std::max(1, (ghost_size(ghost) + SPRINT_FREE_DIV - 1) / SPRINT_FREE_DIV) : 1;
            int const spots = ghost_spots(ghost);
            visit_mark++;
            for (int k = 0; k < spots; k++) {
                int const spot = index_of(bfs_queue[k]);
                visit_stamp[spot] = visit_mark;
                step_count[spot] = 0;
                count_hit(spot, true);
                hit_stamp[spot] = hit_mark;
                pay_stamp[spot] = hit_mark;
            }
            spread_hits(spots, free, free + LS_PAY_STEPS);
        }
    }

    // Free steps are fixed at move start; a paid step must be affordable before its pearl.
    bool reach_can_step(int parts, int free, int steps, int eaten) const {
        return steps < free || parts + eaten - std::max(0, steps - free) > unswbc::Constants::MIN_SIZE;
    }

    int reach_pearl(int index) const {
        return seen_round[index] == round && pearl_here[index] ? 1 : 0;
    }

    // Floods the rings from the heads at bfs_queue[0, queue_tail), already stamped at step 0.
    void spread_hits(int queue_tail, int free, int reach, int parts = 0) {
        int queue_head = 0;
        while (queue_head < queue_tail) {
            Position const position = bfs_queue[queue_head++];
            int const steps = step_count[index_of(position)];
            if (steps >= reach || (REACH_EATS && parts > 0 && !reach_can_step(parts, free, steps, eaten_count[index_of(position)]))) {
                continue;
            }
            for (Direction const direction : Direction::get_direction_list()) {
                int const next = step_index(position, direction);
                if (next == index_of(head)) {
                    (steps < free ? hit_head : pay_head) = true;
                }
                if (next < 0 || visit_stamp[next] == visit_mark || (enter_time[next] != 0 && enter_time[next] != 2)) {
                    continue;
                }
                visit_stamp[next] = visit_mark;
                step_count[next] = steps + 1;
                if (REACH_EATS && parts > 0) {
                    eaten_count[next] = eaten_count[index_of(position)] + reach_pearl(next);
                }
                if (LONG_SAFETY) {
                    count_hit(next, steps < free);
                }
                if (steps < free) {
                    hit_stamp[next] = hit_mark;
                }
                pay_stamp[next] = hit_mark;
                bfs_queue[queue_tail++] = position_of(next);
            }
        }
    }

    // Card #54: tiles a remembered head may stand on now, left at the front of bfs_queue: one step per round out of
    // view, not behind where it was heading, not on a tile in sight.
    int ghost_spots(Ghost const& ghost) {
        visit_mark++;
        int queue_head = 0;
        int queue_tail = 0;
        visit_stamp[index_of(ghost.pos)] = visit_mark;
        step_count[index_of(ghost.pos)] = 0;
        bfs_queue[queue_tail++] = ghost.pos;
        int const age = round - ghost.round;
        while (queue_head < queue_tail) {
            Position const position = bfs_queue[queue_head++];
            int const steps = step_count[index_of(position)];
            if (steps >= age) {
                continue;
            }
            for (Direction const direction : Direction::get_direction_list()) {
                int const next = step_index(position, direction);
                if (next < 0 || visit_stamp[next] == visit_mark || (enter_time[next] != 0 && enter_time[next] != 2)) {
                    continue;
                }
                visit_stamp[next] = visit_mark;
                step_count[next] = steps + 1;
                bfs_queue[queue_tail++] = position_of(next);
            }
        }
        auto const [face_x, face_y] = ghost.face != 0 ? Direction(ghost.face).get_offset() : std::pair<int, int>{0, 0};
        auto signed_gap = [](int from, int to, int size) {
            int const gap = ((to - from) % size + size) % size;
            return 2 * gap > size ? gap - size : gap;
        };
        int spots = 0;
        for (int k = 0; k < queue_tail; k++) {
            Position const position = bfs_queue[k];
            int const ahead = signed_gap(ghost.pos.x, position.x, width) * face_x + signed_gap(ghost.pos.y, position.y, height) * face_y;
            if (seen_round[index_of(position)] != round && ahead >= 0) {
                bfs_queue[spots++] = position;
            }
        }
        return spots;
    }

    // 2 = an enemy head hits the tile for free, 1 = only by paying length, 0 = out of reach.
    int risk_at(int index) const {
        if (!QUEEN_SAFETY || qs_plain || hit_round != round) {
            return 0;
        }
        return hit_stamp[index] == hit_mark ? 2 : pay_stamp[index] == hit_mark ? 1 : 0;
    }

    // Sprint to the best seen tile of at most this risk, on free steps or, with paid, on length too.
    bool hit_escape(std::vector<Direction>& path, bool paid, int risk) {
        if (CUT_BODY_STRIDE && CUT_BODY_LEN > 0 && real_queen()) {
            stride_reach_map();
        }
        // Card #54: a long dragon pays at most LS_ESCAPE_COST, and its paid run only adds tiles past the free one.
        bool const far = long_wary() && paid;
        int const limit = far ? std::min(sprint_reach(), sprint_free() + LS_ESCAPE_COST)
                              : std::min(paid ? sprint_reach() : sprint_free(), STRIDE_MAX);
        int const first = far ? std::min(sprint_free(), STRIDE_MAX) + 1 : 2;
        struct Node {
            int cell;
            int parent;
            int depth;
            Direction dir;
        };
        std::vector<Node> nodes;
        visit_mark++;
        int const start = index_of(head);
        visit_stamp[start] = visit_mark;
        nodes.push_back({start, -1, 0, dir_of(Direction::NORTH)});
        std::vector<int> safe;
        for (std::size_t q = 0; q < nodes.size(); q++) {
            Node const node = nodes[q];
            if (node.depth >= limit) {
                continue;
            }
            Position const position = position_of(node.cell);
            for (Direction const direction : Direction::get_direction_list()) {
                std::uint8_t const edge = edge_at(position, direction);
                if (edge == EDGE_KELP || edge == EDGE_PORTAL || edge == EDGE_UNKNOWN) {
                    continue;
                }
                int const next = index_of(position.add_dir(direction));
                if (visit_stamp[next] == visit_mark || seen_round[next] != round) {
                    continue;
                }
                if (enter_time[next] > (node.depth == 0 ? 1 : 0) || is_enemy_head(position_of(next)) ||
                    is_ally_head(position_of(next))) {
                    continue;
                }
                visit_stamp[next] = visit_mark;
                nodes.push_back({next, static_cast<int>(q), node.depth + 1, direction});
                if (node.depth + 1 >= first && risk_at(next) <= risk &&
                    !(CUT_BODY_STRIDE && CUT_BODY_LEN > 0 && real_queen() && queen_margin(next) <= 0)) {
                    safe.push_back(static_cast<int>(nodes.size()) - 1);
                }
            }
        }
        double best = SCORE_REJECT * 0.5;
        int best_node = -1;
        int evals = 0;
        for (int const k : safe) {
            if (evals++ >= QS_ESCAPE_EVALS || (CELL_BUDGET > 0 && turn_cells > CELL_BUDGET)) {
                break;
            }
            double const score = score_step(position_of(nodes[k].cell)) - SPRINT_ESCAPE_COST * std::max(0, nodes[k].depth - sprint_free());
            if (score > best && (last_reaches_tail || last_room >= length + 2.0)) {
                best = score;
                best_node = k;
            }
        }
        if (best_node < 0) {
            return false;
        }
        path.clear();
        for (int k = best_node; nodes[k].parent >= 0; k = nodes[k].parent) {
            path.push_back(nodes[k].dir);
        }
        std::reverse(path.begin(), path.end());
        return true;
    }

    bool portal_guarded() const {
        if (is_queen()) {
            return true;
        }
        return PORTAL_GUARD_LENGTH > 0 &&
               (length >= PORTAL_GUARD_LENGTH || (is_leader() && length > PORTAL_GUARD_LEADER_MIN));
    }

    bool portal_exit_safe(int exit) const {
        if (exit < 0 || seen_round[exit] != round || exposure_at(exit) > 0) {
            return false;
        }
        Position const cell = position_of(exit);
        for (Position const& enemy : enemy_heads) {
            if (manhattan(enemy, cell) <= PORTAL_GUARD_ENEMY_CLEAR) {
                return false;
            }
        }
        return true;
    }

    int home_region_size() {
        int const limit = static_cast<int>(HOME_MAX_FRAC * cells);
        visit_mark++;
        int queue_head = 0;
        int queue_tail = 0;
        visit_stamp[index_of(head)] = visit_mark;
        bfs_queue[queue_tail++] = head;
        while (queue_head < queue_tail) {
            Position const position = bfs_queue[queue_head++];
            for (Direction const direction : Direction::get_direction_list()) {
                std::uint8_t const edge = edge_at(position, direction);
                if (edge == EDGE_UNKNOWN) {
                    return -1;
                }
                if (edge != EDGE_OPEN) {
                    continue;
                }
                int const next = index_of(position.add_dir(direction));
                if (visit_stamp[next] == visit_mark) {
                    continue;
                }
                if (queue_tail >= limit) {
                    return -1;
                }
                visit_stamp[next] = visit_mark;
                bfs_queue[queue_tail++] = position_of(next);
            }
        }
        return queue_tail;
    }

    bool boxed_in() {
        visit_mark++;
        int queue_head = 0;
        int queue_tail = 0;
        visit_stamp[index_of(head)] = visit_mark;
        bfs_queue[queue_tail++] = head;
        while (queue_head < queue_tail) {
            Position const position = bfs_queue[queue_head++];
            int const index = index_of(position);
            if (pearl_here[index] || pearl_timer[index] != -1) {
                return false;
            }
            for (Direction const direction : Direction::get_direction_list()) {
                std::uint8_t const edge = edge_at(position, direction);
                if (edge == EDGE_UNKNOWN) {
                    return false;
                }
                if (edge != EDGE_OPEN) {
                    continue;
                }
                int const next = index_of(position.add_dir(direction));
                if (visit_stamp[next] == visit_mark) {
                    continue;
                }
                if (queue_tail >= BOX_MAX_CELLS) {
                    return false;
                }
                visit_stamp[next] = visit_mark;
                bfs_queue[queue_tail++] = position_of(next);
            }
        }
        return true;
    }

    void mark_ally_block() {
        if (ally_block_stamp.size() != static_cast<std::size_t>(width * height)) {
            ally_block_stamp.assign(static_cast<std::size_t>(width * height), -1);
        }
        for (Position const& ally : ally_heads) {
            for (Direction const direction : Direction::get_direction_list()) {
                if (edge_at(ally, direction) == EDGE_KELP) {
                    continue;
                }
                int const next = step_index(ally, direction);
                if (next >= 0) {
                    ally_block_stamp[next] = round;
                }
            }
        }
    }

    bool leads_to_unknown(Position position, Direction direction) const {
        return edge_at(position, direction) == EDGE_PORTAL && portal_exit(position, direction) < 0;
    }

    int portal_id_at(Position position, Direction direction) const {
        auto const [index, horizontal] = canonical_edge(position, direction);
        return (horizontal ? north_portal : west_portal)[index];
    }

    int zone_scan(int start, int id, int& core, bool strict) {
        if (zs_stamp.size() != static_cast<std::size_t>(cells)) {
            zs_stamp.assign(cells, 0);
            zs_cut.assign(cells, 0);
            zs_degree.assign(cells, 0);
            zs_queue.assign(cells, 0);
        }
        zs_mark++;
        zs_unknown = false;
        int const cap = std::max(1, static_cast<int>(QG_SAFEZONE_FRAC * cells));
        int tail = 0;
        zs_stamp[start] = zs_mark;
        zs_queue[tail++] = start;
        for (int at = 0; at < tail; at++) {
            Position const position = position_of(zs_queue[at]);
            int degree = 0;
            for (Direction const direction : Direction::get_direction_list()) {
                std::uint8_t const edge = edge_at(position, direction);
                if (edge == EDGE_UNKNOWN) {
                    if (strict) {
                        return -1;
                    }
                    zs_unknown = true;
                    degree++;
                    continue;
                }
                if (edge == EDGE_PORTAL) {
                    if (portal_id_at(position, direction) != id) {
                        return -2;
                    }
                    continue;
                }
                if (edge != EDGE_OPEN) {
                    continue;
                }
                degree++;
                int const next = index_of(position.add_dir(direction));
                if (zs_stamp[next] == zs_mark) {
                    continue;
                }
                if (tail >= cap) {
                    return -2;
                }
                zs_stamp[next] = zs_mark;
                zs_queue[tail++] = next;
            }
            zs_degree[zs_queue[at]] = degree;
        }
        std::vector<int> leaves;
        for (int k = 0; k < tail; k++) {
            if (zs_degree[zs_queue[k]] <= 1) {
                leaves.push_back(zs_queue[k]);
            }
        }
        int removed = 0;
        while (!leaves.empty()) {
            int const cell = leaves.back();
            leaves.pop_back();
            if (zs_cut[cell] == zs_mark) {
                continue;
            }
            zs_cut[cell] = zs_mark;
            removed++;
            Position const position = position_of(cell);
            for (Direction const direction : Direction::get_direction_list()) {
                if (edge_at(position, direction) != EDGE_OPEN) {
                    continue;
                }
                int const next = index_of(position.add_dir(direction));
                if (zs_stamp[next] != zs_mark || zs_cut[next] == zs_mark) {
                    continue;
                }
                if (--zs_degree[next] == 1) {
                    leaves.push_back(next);
                }
            }
        }
        core = tail - removed;
        return tail;
    }

    int zone_doors() const {
        int doors = 0;
        for (int k = 0; k < cells; k++) {
            if (zs_stamp[k] != zs_mark) {
                continue;
            }
            for (Direction const direction : Direction::get_direction_list()) {
                doors += edge_at(position_of(k), direction) == EDGE_PORTAL ? 1 : 0;
            }
        }
        return doors;
    }

    bool zone_blocked(Position position, Direction direction) const {
        if (zone_core <= 0 || real_queen()) {
            return false;
        }
        int const at = index_of(position);
        int const code = face_code(direction);
        Position const mouth = position_of(zone_mouth);
        Direction const through = Direction::get_direction_list()[static_cast<std::size_t>(zone_dir)];
        return (at == zone_mouth && code == zone_dir) ||
               (zone_two && at == index_of(mouth.add_dir(through)) && code == face_code(through.get_opposite()));
    }

    void zone_note_crossing() {
        Position cell = head;
        for (Direction const direction : act_dirs) {
            if (edge_at(cell, direction) == EDGE_PORTAL) {
                zp_mouth = index_of(cell);
                zp_dir = face_code(direction);
                zp_id = portal_id_at(cell, direction);
                zp_until = round + QG_SAFEZONE_PROBE;
            }
            int const next = step_index(cell, direction);
            if (next < 0) {
                return;
            }
            cell = position_of(next);
        }
    }

    void zone_probe() {
        if (zp_until < round || zone_mode != 0 || zone_claimed) {
            return;
        }
        int const entry = portal_exit(position_of(zp_mouth), Direction::get_direction_list()[zp_dir]);
        if (entry < 0) {
            return;
        }
        int core = 0;
        int const size = zone_scan(entry, zp_id, core, true);
        if (size == -1) {
            return;
        }
        zp_until = -1;
        if (size < 0 || zs_stamp[zp_mouth] == zs_mark || zs_stamp[index_of(head)] != zs_mark ||
            core < unswbc::Constants::MIN_SIZE + QG_SAFEZONE_ROOM || core <= zone_core) {
            return;
        }
        int const entry_check = portal_exit(position_of(zp_mouth),
                                    Direction::get_direction_list()[static_cast<std::size_t>(zp_dir)]);
        if (entry_check < 0) {
            return;
        }
        bool too_tight = false;
        for (Direction const d : Direction::get_direction_list()) {
            Position cell = position_of(entry_check);
            for (int step = 0; step < 2; step++) {
                std::uint8_t const e = edge_at(cell, d);
                if (e == EDGE_KELP) {
                    too_tight = true;
                    break;
                }
                if (e != EDGE_OPEN) {
                    break;
                }
                cell = cell.add_dir(d);
            }
            if (too_tight) {
                break;
            }
        }
        if (too_tight) {
            return;
        }
        zone_mouth = zp_mouth;
        zone_dir = zp_dir;
        zone_size = size;
        zone_core = core;
        zone_two = zone_doors() > 1;
        if (QG_SAFEZONE_LOG) {
            ct.output_log("ZFOUND", zone_mouth % width, zone_mouth / width, zone_dir, zone_size, zone_core);
        }
        if (real_queen() && zone_mode == 0) {
            zone_mode = 2;
            zone_enter_round = round;
            zone_entry = index_of(head);
            zone_claimed = true;
            if (QG_SAFEZONE_LOG) {
                ct.output_log("ZSTAY", head.x, head.y, zone_core, length);
            }
        }
    }

    std::uint64_t pack_zone() const {
        std::uint64_t const body = (static_cast<std::uint64_t>(zone_mouth >= 0 ? zone_mouth : 0) & 0x3FFF) |
                                   ((static_cast<std::uint64_t>(zone_dir) & 0x3) << 14) |
                                   ((static_cast<std::uint64_t>(std::min(zone_size, 255)) & 0xFF) << 16) |
                                   ((static_cast<std::uint64_t>(std::min(zone_core, 255)) & 0xFF) << 24) |
                                   (static_cast<std::uint64_t>(enemy_queen_dead ? 1 : 0) << 32) |
                                   (static_cast<std::uint64_t>(zone_two ? 1 : 0) << 33) |
                                   (static_cast<std::uint64_t>(zone_claimed ? 1 : 0) << 34) |
                                   (static_cast<std::uint64_t>(0x3C) << 38) | ((sonar_tag & 0x3) << 53);
        return sonar_codec::seal(sonar_key, body | (1ULL << 63));
    }

    bool learn_zone(std::uint64_t message) {
        std::uint64_t const body = message & ((1ULL << 55) - 1);
        if (((body >> 53) & 0x3) != sonar_tag || ((body >> 38) & 0x7FFF) != 0x3C) {
            return false;
        }
        if (((body >> 32) & 1ULL) != 0) {
            enemy_queen_dead = true;
        }
        int const mouth = static_cast<int>(body & 0x3FFF);
        int const core = static_cast<int>((body >> 24) & 0xFF);
        bool const claimed = ((body >> 34) & 1ULL) != 0;
        if (zone_mode == 0 && mouth < cells && core > 0 && !zone_claimed && (claimed || core > zone_core)) {
            zone_mouth = mouth;
            zone_dir = static_cast<int>((body >> 14) & 0x3);
            zone_size = static_cast<int>((body >> 16) & 0xFF);
            zone_core = core;
            zone_two = ((body >> 33) & 1ULL) != 0;
            zone_claimed = claimed;
        }
        return true;
    }

    bool zone_relay(std::size_t k) const {
        if (static_cast<int>(k) == zone_check_dir) {
            return true;
        }
        if (zone_core <= 0 && !enemy_queen_dead) {
            return false;
        }
        if (feeding_phase()) {
            return false;
        }
        int const back_dir = (zone_dir + 2) % 4;
        return static_cast<int>(k) != back_dir;
    }

    void zone_watch() {
        if (QUEEN_MODE && enemy_queen_id >= 0 && eq_round == round - 1 && enemy_queen_round != round) {
            int const at = index_of(eq_pos);
            if (seen_round[at] == round && pearl_here[at] && visible_parts(enemy_queen_id) == 0) {
                enemy_queen_dead = true;
                if (QG_SAFEZONE_LOG) {
                    ct.output_log("ZQDEAD", eq_pos.x, eq_pos.y);
                }
            }
        }
        eq_round = enemy_queen_round == round ? round : -1;
        eq_pos = enemy_queen_pos;
    }

    bool zone_queen() {
        zone_target = -1;
        if (zone_checked) {
            unswbc::SonarEchoes const echo = ct.get_sonar_echoes();
            bool const clear = echo.kelp == 1 && echo.ally == 0 && echo.ally_head == 0 && echo.enemy == 0 && echo.enemy_head == 0;
            zone_clear = clear ? zone_clear + 1 : 0;
            zone_checked = false;
            zone_last_check = round - 1;
            if (QG_SAFEZONE_LOG) {
                ct.output_log("ZCHECK", echo.kelp, echo.ally, echo.ally_head, echo.enemy, echo.enemy_head, zone_clear);
            }
        } else if (round - zone_last_check > QG_SAFEZONE_GAP) {
            zone_clear = 0;
        }
        bool const late = feeding_phase() && !enemy_queen_dead;
        auto const directions = Direction::get_direction_list();
        if (zone_mode <= 1) {
            int const was = zone_mode;
            zone_mode = zone_core > 0 && zone_core >= length + QG_SAFEZONE_ROOM && !late ? 1 : 0;
            zone_claimed = zone_claimed || zone_mode == 1;
            if (QG_SAFEZONE_LOG && zone_mode != was) {
                ct.output_log("ZMODE", zone_mode, zone_mouth % width, zone_mouth / width, zone_dir, zone_core, length);
            }
        }
        if (zone_mode == 1) {
            Position const mouth = position_of(zone_mouth);
            Direction const through = directions[static_cast<std::size_t>(zone_dir)];
            if (head == mouth && zone_clear >= QG_SAFEZONE_CHECKS && edge_at(head, through) == EDGE_PORTAL) {
                zone_id = portal_id_at(head, through);
                ct.make_move(through);
                act_dirs.assign(1, through);
                zone_mode = 2;
                zone_enter_round = round;
                if (QG_SAFEZONE_LOG) {
                    ct.output_log("ZENTER", head.x, head.y, zone_clear, length);
                }
                return true;
            }
            Direction const back = through.get_opposite();
            int const before = edge_at(mouth, back) == EDGE_OPEN ? index_of(mouth.add_dir(back)) : -1;
            zone_target = before >= 0 && index_of(head) != before ? before : zone_mouth;
            return false;
        }
        if (zone_mode == 2) {
            if (zone_entry < 0) {
                zone_entry = index_of(head);
            }
            int core = 0;
            int const size = zone_scan(index_of(head), zone_id, core, false);
            if (size == -2) {
                zone_mode = 4;
                return false;
            }
            bool invaded = false;
            for (Position const& enemy : enemy_heads) {
                invaded = invaded || zs_stamp[index_of(enemy)] == zs_mark;
            }
            if (invaded) {
                zone_mode = 3;
                if (QG_SAFEZONE_LOG) {
                    ct.output_log("ZBAD", size, length);
                }
            }
            if (zone_mode == 2 && (late || (zs_unknown ? zone_core : core) < length + 1)) {
                zone_mode = 3;
                if (QG_SAFEZONE_LOG) {
                    ct.output_log("ZLEAVE", late ? 1 : 0, core, length);
                }
            }
        }
        if (zone_mode == 3) {
            Direction const out = directions[static_cast<std::size_t>(zone_dir)].get_opposite();
            if (index_of(head) == zone_entry && round - zone_enter_round > length && edge_at(head, out) == EDGE_PORTAL) {
                ct.make_move(out);
                act_dirs.assign(1, out);
                zone_mode = 4;
                if (QG_SAFEZONE_LOG) {
                    ct.output_log("ZEXIT", head.x, head.y, length);
                }
                return true;
            }
            zone_target = zone_entry;
        }
        return false;
    }

    void zone_after_move() {
        zone_note_crossing();
        zone_check_dir = -1;
        if (zone_mode != 1 || !sonar_enabled) {
            return;
        }
        Position post = head;
        for (Direction const direction : act_dirs) {
            int const next = step_index(post, direction);
            if (next < 0) {
                return;
            }
            post = position_of(next);
        }
        Position const mouth = position_of(zone_mouth);
        Direction const through = Direction::get_direction_list()[static_cast<std::size_t>(zone_dir)];
        bool const at_mouth = post == mouth;
        bool const behind = edge_at(post, through) == EDGE_OPEN && index_of(post.add_dir(through)) == zone_mouth &&
                            !(head == mouth) && enter_time[zone_mouth] == 0;
        if (at_mouth || behind) {
            zone_check_dir = zone_dir;
            zone_checked = true;
        }
    }

    double zone_cost(int cell) const {
        if (zs_stamp[cell] != zs_mark) {
            return 0.0;
        }
        if (zs_cut[cell] == zs_mark && !zs_unknown) {
            return QG_SAFEZONE_PENALTY;
        }
        Position const position = position_of(cell);
        for (Direction const direction : Direction::get_direction_list()) {
            if (edge_at(position, direction) == EDGE_PORTAL) {
                return QG_SAFEZONE_PENALTY;
            }
        }
        return 0.0;
    }

    bool kelp_within(Position from, Direction direction) const {
        Position cell = from;
        for (int k = 0; k < QG_CORNER_RADIUS; k++) {
            std::uint8_t const edge = edge_at(cell, direction);
            if (edge == EDGE_KELP) {
                return true;
            }
            if (edge != EDGE_OPEN) {
                return false;
            }
            cell = cell.add_dir(direction);
        }
        return false;
    }

    std::vector<int> corner_area(int center) const {
        std::vector<int> area(1, center);
        std::vector<int> depth(1, 0);
        for (std::size_t at = 0; at < area.size(); at++) {
            if (depth[at] >= QG_CORNER_RADIUS) {
                continue;
            }
            Position const position = position_of(area[at]);
            for (Direction const direction : Direction::get_direction_list()) {
                if (edge_at(position, direction) != EDGE_OPEN) {
                    continue;
                }
                int const next = index_of(position.add_dir(direction));
                if (std::find(area.begin(), area.end(), next) == area.end()) {
                    area.push_back(next);
                    depth.push_back(depth[at] + 1);
                }
            }
        }
        return area;
    }

    int corner_room(int center) const {
        std::vector<int> area = corner_area(center);
        bool cut = true;
        while (cut && !area.empty()) {
            cut = false;
            for (std::size_t k = 0; k < area.size(); k++) {
                Position const position = position_of(area[k]);
                int degree = 0;
                for (Direction const direction : Direction::get_direction_list()) {
                    if (edge_at(position, direction) == EDGE_OPEN &&
                        std::find(area.begin(), area.end(), index_of(position.add_dir(direction))) != area.end()) {
                        degree++;
                    }
                }
                if (degree <= 1) {
                    area.erase(area.begin() + static_cast<std::ptrdiff_t>(k));
                    cut = true;
                    break;
                }
            }
        }
        return static_cast<int>(area.size());
    }

    void corner_search() {
        corner_center = -1;
        corner_dir = -1;
        visit_mark++;
        int queue_head = 0;
        int queue_tail = 0;
        int const start = index_of(head);
        visit_stamp[start] = visit_mark;
        step_count[start] = 0;
        bfs_queue[queue_tail++] = head;
        double best = SCORE_REJECT;
        auto const directions = Direction::get_direction_list();
        while (queue_head < queue_tail) {
            Position const position = bfs_queue[queue_head++];
            int const index = index_of(position);
            int const steps = step_count[index];
            int sides = 0;
            for (Direction const direction : directions) {
                sides += kelp_within(position, direction) ? 1 : 0;
            }
            if (sides >= 3 && seen_round[index] >= 0 &&
                std::find(corner_bad.begin(), corner_bad.end(), index) == corner_bad.end()) {
                int mouth = -1;
                int mouth_dir = -1;
                bool known = false;
                for (int const cell : corner_area(index)) {
                    for (std::size_t k = 0; k < directions.size(); k++) {
                        if (edge_at(position_of(cell), directions[k]) != EDGE_PORTAL) {
                            continue;
                        }
                        bool const exit_known = portal_exit(position_of(cell), directions[k]) >= 0;
                        if (mouth < 0 || (exit_known && !known)) {
                            mouth = cell;
                            mouth_dir = static_cast<int>(k);
                            known = exit_known;
                        }
                    }
                }
                int const center = mouth >= 0 ? mouth : index;
                if (std::find(corner_bad.begin(), corner_bad.end(), center) == corner_bad.end() &&
                    corner_room(center) >= length + 1) {
                    double const score = (mouth >= 0 ? 1000.0 : 0.0) + (known ? 500.0 : 0.0) - steps;
                    if (score > best) {
                        best = score;
                        corner_center = center;
                        corner_dir = mouth_dir;
                    }
                }
            }
            if (steps >= QG_CORNER_REACH) {
                continue;
            }
            for (Direction const direction : directions) {
                if (edge_at(position, direction) != EDGE_OPEN) {
                    continue;
                }
                int const next = index_of(position.add_dir(direction));
                if (visit_stamp[next] == visit_mark) {
                    continue;
                }
                visit_stamp[next] = visit_mark;
                step_count[next] = steps + 1;
                bfs_queue[queue_tail++] = position_of(next);
            }
        }
    }

    void corner_update() {
        corner_target = -1;
        corner_escape = false;
        corner_hold = false;
        if (feeding_phase() || (QG_SAFEZONE && zone_mode != 0 && zone_mode != 4)) {
            corner_center = -1;
            return;
        }
        if (corner_center >= 0 && corner_room(corner_center) < length + 1) {
            corner_center = -1;
        }
        if (corner_center < 0 && round - corner_round >= QG_CORNER_EVERY) {
            corner_round = round;
            corner_search();
            if (QG_CORNER_LOG && corner_center >= 0) {
                ct.output_log("CANCHOR", corner_center % width, corner_center / width, corner_dir,
                              corner_dir >= 0 && portal_exit(position_of(corner_center), Direction::get_direction_list()[static_cast<std::size_t>(corner_dir)]) >= 0 ? 1 : 0,
                              length);
            }
        }
        if (corner_center < 0) {
            return;
        }
        corner_escape = enemy_near(head, QG_CORNER_DANGER);
        int const gap = manhattan(head, position_of(corner_center));
        corner_hold = !corner_escape && gap <= QG_CORNER_RADIUS;
        if (gap > QG_CORNER_RADIUS || (corner_escape && corner_dir >= 0 && gap > 0)) {
            corner_target = corner_center;
        }
        if (QG_CORNER_LOG && gap <= QG_CORNER_RADIUS) {
            ct.output_log("CNEAR", gap, corner_escape ? 1 : 0, length);
        }
    }

    bool corner_gate(Direction direction) const {
        return corner_escape && corner_dir >= 0 && index_of(head) == corner_center && face_code(direction) == corner_dir;
    }

    double corner_portal_score(Direction direction, bool& usable) {
        int const exit = portal_exit(head, direction);
        usable = exit >= 0 && enter_time[exit] <= 1;
        if (exit >= 0 && !usable) {
            return SCORE_REJECT;
        }
        return (usable ? score_step(position_of(exit)) : 0.0) - PORTAL_LEAP_PENALTY;
    }

    void corner_after_move() {
        if (corner_center < 0 || act_dirs.size() != 1 || !corner_gate(act_dirs.front())) {
            return;
        }
        if (QG_CORNER_LOG) {
            ct.output_log("CESCAPE", head.x, head.y, length);
        }
        corner_bad.push_back(corner_center);
        corner_center = -1;
        corner_round = round;
    }

    
    
    
    double cell_rate(int index) const {
        if (seen_round[index] < 0) {
            return 0.0;
        }
        if (TARGET_REACHABLE && !target_reachable(index)) {
            return 0.0;
        }
        double rate = 0.0;
        if (hot[index]) {
            rate += INC_HOT_RATE;
        } else if (pearl_timer[index] >= 0) {
            rate += INC_SPAWN_RATE;
        }
        if (pearl_here[index]) {
            rate += INC_PEARL_RATE;
        }
        return rate;
    }

    double area_value(Position center) const {
        double total = 0.0;
        for (int dy = -3; dy <= 3; dy++) {
            for (int dx = -3; dx <= 3; dx++) {
                Position const cell{((center.x + dx) % width + width) % width, ((center.y + dy) % height + height) % height};
                total += cell_rate(index_of(cell));
            }
        }
        int crowd = 0;
        for (auto const& seen : recent_allies) {
            if (manhattan(seen.first, center) <= 4) {
                crowd++;
            }
        }
        return total / (1.0 + crowd);
    }

    void income_update() {
        if (TARGET_REACHABLE && inc_target >= 0 && !target_reachable(inc_target)) {
            inc_target = -1;
        }
        recent_allies.erase(std::remove_if(recent_allies.begin(), recent_allies.end(),
                                           [this](std::pair<Position, int> const& entry) {
                                               return round - entry.second > INC_ALLY_MEMORY;
                                           }),
                            recent_allies.end());
        for (Position const& ally : ally_heads) {
            recent_allies.emplace_back(ally, round);
        }
        if (feeding_phase() || is_leader() || is_feeder() || length > INC_MAX_LENGTH) {
            inc_target = -1;
            return;
        }
        if (inc_target >= 0 && manhattan(head, position_of(inc_target)) <= 2) {
            inc_target = -1;
        }
        if (round - inc_round < INC_PERIOD) {
            return;
        }
        if (escape_stamp.empty()) {
            escape_stamp.assign(cells, 0);
            escape_steps.assign(cells, 0);
            escape_queue.assign(cells, 0);
        }
        escape_mark++;
        int queue_head = 0;
        int queue_tail = 0;
        int const start = index_of(head);
        escape_stamp[start] = escape_mark;
        escape_steps[start] = 0;
        escape_queue[queue_tail++] = start;
        double const here = area_value(head);
        double best = here + INC_MARGIN;
        int best_cell = -1;
        while (queue_head < queue_tail) {
            int const index = escape_queue[queue_head++];
            int const steps = escape_steps[index];
            if (steps >= 3 && (hot[index] || pearl_here[index]) && (!TARGET_REACHABLE || target_reachable(index))) {
                double const score = area_value(position_of(index)) - INC_DIST_W * steps;
                if (score > best) {
                    best = score;
                    best_cell = index;
                }
            }
            if (steps >= INC_RADIUS) {
                continue;
            }
            Position const position = position_of(index);
            for (Direction const direction : Direction::get_direction_list()) {
                int const next = step_index(position, direction);
                if (next < 0 || escape_stamp[next] == escape_mark || seen_round[next] < 0 ||
                    enter_time[next] >= BLOCKED_FOREVER) {
                    continue;
                }
                escape_stamp[next] = escape_mark;
                escape_steps[next] = steps + 1;
                escape_queue[queue_tail++] = next;
            }
        }
        inc_target = best_cell;
        inc_round = round;
    }

    void idle_update() {
        if (is_leader() || is_feeder() || tail_index < 0) {
            return;
        }
        if (escape_stamp.empty()) {
            escape_stamp.assign(cells, 0);
            escape_steps.assign(cells, 0);
            escape_queue.assign(cells, 0);
        }
        escape_mark++;
        int queue_head = 0;
        int queue_tail = 0;
        int const start = index_of(head);
        escape_stamp[start] = escape_mark;
        escape_steps[start] = 0;
        escape_queue[queue_tail++] = start;
        int portal_cell = -1;
        int portal_dir = -1;
        auto const directions = Direction::get_direction_list();
        while (queue_head < queue_tail) {
            int const index = escape_queue[queue_head++];
            if (pearl_here[index]) {
                return;
            }
            Position const position = position_of(index);
            for (std::size_t k = 0; k < directions.size(); k++) {
                std::uint8_t const edge = edge_at(position, directions[k]);
                if (edge == EDGE_PORTAL) {
                    if (portal_into_pocket(position, directions[k]) || (QG_SAFEZONE && zone_blocked(position, directions[k]))) {
                        continue;
                    }
                    if (portal_cell < 0 || escape_steps[index] < escape_steps[portal_cell]) {
                        portal_cell = index;
                        portal_dir = static_cast<int>(k);
                    }
                    continue;
                }
                if (IDLE_STRICT && edge == EDGE_UNKNOWN) {
                    return;
                }
                if (edge != EDGE_OPEN) {
                    continue;
                }
                int const next = index_of(position.add_dir(directions[k]));
                if (escape_stamp[next] == escape_mark) {
                    continue;
                }
                if (IDLE_STRICT && seen_round[next] < 0) {
                    return;
                }
                if (queue_tail >= IDLE_REGION_MAX) {
                    return;
                }
                escape_stamp[next] = escape_mark;
                escape_steps[next] = escape_steps[index] + 1;
                escape_queue[queue_tail++] = next;
            }
        }
        if (portal_cell < 0) {
            return;
        }
        escape_target = portal_cell;
        if (portal_cell == start) {
            escape_through = portal_dir;
        }
    }

    void staff_update() {
        if (feeding_phase() || is_leader() || is_feeder() || is_trader() || tail_index < 0) {
            return;
        }
        if (escape_stamp.empty()) {
            escape_stamp.assign(cells, 0);
            escape_steps.assign(cells, 0);
            escape_queue.assign(cells, 0);
        }
        escape_mark++;
        int queue_head = 0;
        int queue_tail = 0;
        int const start = index_of(head);
        escape_stamp[start] = escape_mark;
        escape_steps[start] = 0;
        escape_queue[queue_tail++] = start;
        int spawn = 0;
        int portal_cell = -1;
        int portal_dir = -1;
        auto const directions = Direction::get_direction_list();
        while (queue_head < queue_tail) {
            int const index = escape_queue[queue_head++];
            if (seen_round[index] >= 0 && pearl_timer[index] >= 0) {
                spawn++;
            }
            Position const position = position_of(index);
            for (std::size_t k = 0; k < directions.size(); k++) {
                std::uint8_t const edge = edge_at(position, directions[k]);
                if (edge == EDGE_PORTAL) {
                    if (portal_into_pocket(position, directions[k]) || (QG_SAFEZONE && zone_blocked(position, directions[k]))) {
                        continue;
                    }
                    if (portal_cell < 0 || escape_steps[index] < escape_steps[portal_cell]) {
                        portal_cell = index;
                        portal_dir = static_cast<int>(k);
                    }
                    continue;
                }
                if (edge != EDGE_OPEN) {
                    continue;
                }
                int const next = index_of(position.add_dir(directions[k]));
                if (escape_stamp[next] == escape_mark) {
                    continue;
                }
                if (queue_tail >= STAFF_REGION_MAX) {
                    return;
                }
                escape_stamp[next] = escape_mark;
                escape_steps[next] = escape_steps[index] + 1;
                escape_queue[queue_tail++] = next;
            }
        }
        if (portal_cell < 0) {
            return;
        }
        int ahead = 0;
        for (std::size_t k = 0; k < ally_heads.size(); k++) {
            if (escape_stamp[index_of(ally_heads[k])] == escape_mark && ally_head_ids[k] < ct.get_id()) {
                ahead++;
            }
        }
        int const capacity = std::max(1, spawn / std::max(1, STAFF_CELLS));
        if (ahead < capacity) {
            return;
        }
        escape_target = portal_cell;
        if (portal_cell == start) {
            escape_through = portal_dir;
        }
    }

    void escape_update() {
        escape_target = -1;
        escape_through = -1;
        bool const barren_on = BARREN_ESCAPE && round <= BARREN_ROUNDS;
        if (!barren_on || !can_scout_portals() || is_trader()) {
            return;
        }
        if (escape_stamp.empty()) {
            escape_stamp.assign(cells, 0);
            escape_steps.assign(cells, 0);
            escape_queue.assign(cells, 0);
        }
        escape_mark++;
        int queue_head = 0;
        int queue_tail = 0;
        int const start = index_of(head);
        escape_stamp[start] = escape_mark;
        escape_steps[start] = 0;
        escape_queue[queue_tail++] = start;
        int seen = 0;
        int spawn = 0;
        int portal_cell = -1;
        int portal_dir = -1;
        bool portal_unknown = false;
        bool productive = false;
        auto const directions = Direction::get_direction_list();
        while (queue_head < queue_tail) {
            int const index = escape_queue[queue_head++];
            if (seen_round[index] >= 0) {
                if (pearl_here[index] || hot[index]) {
                    productive = true;
                }
                seen++;
                spawn += pearl_timer[index] >= 0 ? 1 : 0;
            }
            Position const position = position_of(index);
            for (std::size_t k = 0; k < directions.size(); k++) {
                std::uint8_t const edge = edge_at(position, directions[k]);
                if (edge == EDGE_KELP || (BARREN_KNOWN && edge == EDGE_UNKNOWN)) {
                    continue;
                }
                if (edge == EDGE_PORTAL) {
                    if (portal_into_pocket(position, directions[k]) || (QG_SAFEZONE && zone_blocked(position, directions[k]))) {
                        continue;
                    }
                    bool const unknown = portal_exit(position, directions[k]) < 0;
                    if (portal_cell < 0 || (unknown && !portal_unknown)) {
                        portal_cell = index;
                        portal_dir = static_cast<int>(k);
                        portal_unknown = unknown;
                    }
                    continue;
                }
                int const next = index_of(position.add_dir(directions[k]));
                if (escape_stamp[next] == escape_mark || queue_tail >= BARREN_REGION_CAP) {
                    continue;
                }
                escape_stamp[next] = escape_mark;
                escape_steps[next] = escape_steps[index] + 1;
                escape_queue[queue_tail++] = next;
            }
        }
        int target = -1;
        int through = -1;
        if (barren_on && (BARREN_BY_RATE || !productive) && seen >= BARREN_MIN_SEEN && spawn <= BARREN_MAX_SPAWN * seen && portal_cell >= 0) {
            target = portal_cell;
            through = portal_dir;
        }
        if (target < 0) {
            return;
        }
        escape_target = target;
        if (target == start) {
            escape_through = through;
        }
    }

    
    void apply_route(std::array<double, 4>& scores, std::array<bool, 4> const& scored,
                    std::array<bool, 4> const& closed, std::array<int, 4> const& dests,
                    std::array<int, 4> const& route_dist) const {
        if (route_target < 0 || escape_through >= 0) {
            return;
        }
        double top = SCORE_REJECT;
        for (std::size_t k = 0; k < 4; k++) {
            if (scored[k] && scores[k] > SCORE_REJECT * 0.5) {
                top = std::max(top, scores[k]);
            }
        }
        std::array<bool, 4> safe{};
        int nearest = BLOCKED_FOREVER;
        // With her in view the hunter closes in through threatened cells.
        bool const charge = QH_SCOUT && qh_in_view && qh_gate < 0 && route_target == qh_route;
        for (std::size_t k = 0; k < 4; k++) {
            if (!scored[k] || dests[k] < 0 || scores[k] <= SCORE_REJECT * 0.5 ||
                (closed[k] && !(STAFF_CELLS > 0 && dests[k] == route_target)) ||
                (scores[k] < top - ROUTE_VETO && !(STAFF_CELLS > 0 && dests[k] == route_target) && !charge) ||
                route_dist[k] < 0) {
                continue;
            }
            Position const cell = position_of(dests[k]);
            if (((threat_at(dests[k]) > 0 || enemy_can_step_to(cell)) && !charge) || can_step_to(ally_heads, cell)) {
                continue;
            }
            safe[k] = true;
            nearest = std::min(nearest, route_dist[k]);
        }
        for (std::size_t k = 0; k < 4; k++) {
            if (safe[k] && route_dist[k] == nearest) {
                scores[k] += ROUTE_OVERRIDE;
            }
        }
    }

    bool is_feeder() const {
        return feed_index >= 0;
    }

    bool rally_ready() const {
        int const fresh = RALLY_END_FRESH > 0 && round > feed_round ? RALLY_END_FRESH : rally_fresh;
        if (fresh <= 0 || (QH_SCOUT && qh_on) || !feeding_phase() || is_feeder() || is_leader() || is_trader() || queen_aloof() || known_leader_id < 0 ||
            known_leader_id == ct.get_id() || known_leader_round < 0 || round - known_leader_round > fresh ||
            !feed_len_ok() || ct.get_unit_count() <= FEEDER_KEEP_UNITS) {
            return false;
        }
        return manhattan(head, known_leader_pos) > feeder_approach;
    }

    bool feed_len_ok() const {
        if (QUEEN_BOOT_LEN > 0 && feeding_phase() && QUEEN_MODE && queen_id >= 0 &&
            known_leader_id == queen_id && known_leader_len >= 2 && known_leader_len < QUEEN_BOOT_LEN &&
            !qh_queen_dead() && (length == 2 || length == 3)) {
            return true;
        }
        if (known_leader_len < FEED_BOOT_LEN) {
            return length <= known_leader_len;
        }
        return length * FEED_LEN_RATIO <= known_leader_len;
    }

    bool feeding_phase() const {
        return round > feed_round ||
               (FEED_CAP_UNITS > 0 && round > FEED_CAP_ROUND && ct.get_unit_count() >= FEED_CAP_UNITS);
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
        return (on_drop_cell(head) && leader_info_fresh() && leader_in_vision()) ||
               beside_visible_leader();
    }

    bool local_die() const {
        if (!feeding_phase() || is_leader() || is_queen() || queen_aloof() || is_feeder() || ct.get_unit_count() <= FEEDER_KEEP_UNITS) {
            return false;
        }
        for (Position const& enemy : enemy_heads) {
            if (manhattan(head, enemy) <= FEEDER_ENEMY_CLEAR) {
                return false;
            }
        }
        for (std::size_t k = 0; k < ally_heads.size(); k++) {
            int const parts = visible_parts(ally_head_ids[k]);
            if (manhattan(head, ally_heads[k]) <= FEED_LOCAL && parts >= FEED_LOCAL_MIN &&
                parts >= length * FEED_LEN_RATIO) {
                return true;
            }
        }
        return false;
    }

    double score_step(Position destination) {
        survey_back = NO_REVERSE ? index_of(head) : -1;
        survey_pessimist = (QUEEN_PESSIMIST || (QG_PESSIMIST && queen_guard())) && is_queen();
        survey_no_portal = queen_portal_ban();
        survey_ally_block = (QUEEN_ALLY_BLOCK && is_queen()) || (ALLY_BLOCK_MAX_LEN > 0 && length <= ALLY_BLOCK_MAX_LEN);
        if (survey_ally_block) {
            mark_ally_block();
        }
        Survey const survey = survey_from(destination);
        survey_pessimist = false;
        survey_no_portal = false;
        survey_ally_block = false;
        survey_back = -1;
        last_survey = survey;

        double const room = survey.area_seen + UNSEEN_DISCOUNT * survey.area_unseen;
        double const territory = survey.own_seen + UNSEEN_DISCOUNT * survey.own_unseen;
        last_room = room;
        last_seen_room = survey.area_seen;
        last_reaches_tail = survey.reaches_tail;
        double const space = WEIGHT_SPACE * room + WEIGHT_TERRITORY * territory;

        double const room_wanted = 3.0 * length + 8.0;
        double const avail = room - survey.ally_load;
        double cramped = 0.0;
        bool const eats_cramped = CRAMPED_EAT && avail >= length + 2.0 && pearl_here[index_of(destination)] &&
                                  !real_queen() && !is_leader() && !is_feeder();
        if (avail < room_wanted && !eats_cramped) {
            cramped += PENALTY_TIGHT * (room_wanted - avail);
        }
        if (avail < length + 2.0) {
            cramped += PENALTY_TRAPPED * (length + 2.0 - avail);
        }
        bool const fall = fallback_on();
        bool const released = stall_released() && !fall;
        if (!eats_cramped && tail_index >= 0 && !survey.reaches_tail && (NO_TAIL_ROOM <= 0 || avail < NO_TAIL_ROOM * length + 8.0) &&
            !(released && avail >= TR_STALL_ROOM * length + 8.0)) {
            cramped += PENALTY_NO_TAIL;
        }
        last_space = space;
        last_cramped = cramped;
        last_dist_route = survey.dist_route;
        last_pearls = survey.pearls;
        last_dead_end = TARGET_REACHABLE ? entry_dead_end(room, survey.reaches_tail)
                                      : (tail_index >= 0 || (QUEEN_DEAD_END && dead_queen())) && !survey.reaches_tail && room < room_wanted;
        double score = space - cramped;
        // Card #55: a step short of room, which the fall-back pull must not buy.
        bool boxed = last_dead_end || avail < length + 2.0 || (!survey.reaches_tail && room < length + 2.0);
        if (dead_queen() && QUEEN_ROOM > 0 && (last_dead_end || avail < length + QUEEN_ROOM)) {
            score -= QUEEN_DEAD_PENALTY;
            boxed = true;
        }
        if (QUEEN_DEAD_END && dead_queen()) {
            int const need = length + 2;
            int const known = known_room(index_of(destination), need);
            if (known < need) {
                score -= QUEEN_DEAD_PENALTY + QUEEN_KNOWN_STEP * (need - known);
                boxed = true;
            }
        }
        if (QUEEN_MODE && QUEEN_GIVE_WAY > 0 && !is_queen()) {
            for (std::size_t k = 0; k < ally_heads.size(); k++) {
                if (ally_head_ids[k] != queen_id) {
                    continue;
                }
                int const gap = manhattan(destination, ally_heads[k]);
                if (gap <= QUEEN_GIVE_WAY) {
                    score -= QUEEN_GIVE_WAY_PENALTY * (QUEEN_GIVE_WAY + 1 - gap);
                }
            }
        }

        double const pearl_weight = is_leader() && feeding_phase() ? WEIGHT_PEARL * LEADER_ENDGAME_PEARL_MULT
                                    : is_leader()                   ? WEIGHT_PEARL * LC_LEAD_MULT
                                                                    : WEIGHT_PEARL;
        last_bonus = std::max({PEARL_FAR_DECAY > 0.0 && survey.dist_pearl >= 0
                                   ? pearl_weight * std::max(0.0, TARGET_REWARD - std::min(TARGET_DECAY, PEARL_FAR_DECAY) * survey.dist_pearl)
                                   : target_bonus(survey.dist_pearl, pearl_weight),
                               target_bonus(survey.dist_soon, WEIGHT_SOON),
                               HOT_FAR_DECAY > 0.0 && survey.dist_hot >= 0
                                   ? WEIGHT_HOT * std::max(0.0, TARGET_REWARD - std::min(TARGET_DECAY, HOT_FAR_DECAY) * survey.dist_hot)
                                   : target_bonus(survey.dist_hot, WEIGHT_HOT),
                               target_bonus(survey.dist_unseen, WEIGHT_UNSEEN),
                               PORTAL_FAR_DECAY > 0.0 && survey.dist_portal >= 0 &&
                                       (PORTAL_FAR_ROUNDS <= 0 || round <= PORTAL_FAR_ROUNDS)
                                   ? WEIGHT_PORTAL_SCOUT * std::max(0.0, TARGET_REWARD - PORTAL_FAR_DECAY * survey.dist_portal)
                                   : target_bonus(survey.dist_portal, WEIGHT_PORTAL_SCOUT)});
        score += last_bonus;
        if (EXPLORE_GAIN > 0.0 && round < EXPLORE_ROUNDS && survey.dist_unseen >= 0) {
            score += EXPLORE_GAIN * std::max(0, EXPLORE_RANGE - survey.dist_unseen);
        }
        if (FAR_GAIN > 0.0 && (FAR_IDLE <= 0 || round - last_growth_round >= FAR_IDLE)) {
            int far = -1;
            for (int const dist : {survey.dist_pearl, survey.dist_soon, survey.dist_hot, survey.dist_unseen}) {
                if (dist >= 0 && (far < 0 || dist < far)) {
                    far = dist;
                }
            }
            if (far >= 0) {
                score += FAR_GAIN * std::max(0, FAR_RANGE - far);
            }
        }

        int const grown = length + (pearl_here[index_of(destination)] ? 1 : 0);
        int const pocket = POCKET_CAP > 0 ? pocket_size(index_of(destination)) : POCKET_CAP;
        bool const pocket_full = TARGET_REACHABLE ? entry_pocket_full(index_of(destination), pocket)
                                                : POCKET_CAP > 0 && pocket < POCKET_CAP && grown > pocket / POCKET_DIV;
        last_pocket = 0.0;
        if (pocket_full) {
            score -= POCKET_PENALTY * (grown - pocket / POCKET_DIV);
            last_pocket = POCKET_PENALTY * (grown - pocket / POCKET_DIV);
        }
        if (pearl_here[index_of(destination)] && (FEEDER_EAT || !is_feeder()) && !in_leader_pearl_zone(index_of(destination)) && !pocket_full) {
            score += EAT_BONUS;
        } else if (pocket_full && pearl_here[index_of(destination)] && !is_feeder() && !in_leader_pearl_zone(index_of(destination))) {
            last_pocket += EAT_BONUS;
        }
        if (SPAWN_CLEAR && !pearl_here[index_of(destination)] && (SPAWN_CLEAR_ALL || (!is_feeder() && !is_leader()))) {
            int const spot = index_of(destination);
            if (pearl_timer[spot] >= 0 && seen_round[spot] >= 0) {
                int const spawns_in = pearl_timer[spot] - (round - seen_round[spot]);
                if (spawns_in >= 0 && spawns_in <= std::min(length, SPAWN_CLEAR_MAX)) {
                    score -= SPAWN_CLEAR_PENALTY;
                }
            }
        }
        if (!is_leader() && pearl_here[index_of(destination)] && in_leader_pearl_zone(index_of(destination))) {
            score -= ZONE_PEARL_PENALTY;
        }
        if (CENTER_PULL > 0.0 && center_map && round < center_rounds && length <= CENTER_MAX_LENGTH && !fall &&
            static_cast<int>(enemy_heads.size()) - static_cast<int>(ally_heads.size()) <= center_margin &&
            std::max(target_bonus(survey.dist_pearl, pearl_weight), target_bonus(survey.dist_hot, WEIGHT_HOT)) <= 0.0) {
            score -= CENTER_PULL * (released ? stall_seek(survey.dist_unseen) : center_distance(destination));
        }
        if (can_step_to(ally_heads, destination)) {
            score -= PENALTY_ENEMY_HEAD;
        }
        if (QUEEN_SAFETY && queen_wary()) {
            int const cell = index_of(destination);
            int const depth = threat_stamp[cell] == threat_mark ? threat_depth[cell] : 0;
            int const peer = is_trader() ? 0 : peer_at(cell);
            double const race = PENALTY_HEAD_RACE * std::max(0.5, length / THREAT_LENGTH_SCALE);
            double const wary = depth > 0 ? race * (0.5 + 0.5 * depth) * (queen_guard() ? QG_THREAT_MULT : QS_THREAT_MULT) : 0.0;
            double const plain = peer > 0 ? race * (0.5 + 0.5 * peer) * (is_leader() ? LEADER_HEAD_MULT : 1.0) : 0.0;
            score -= std::max(wary, plain);
        } else if (!is_trader()) {
            int const depth = threat_at(index_of(destination));
            if (depth > 0) {
                double penalty = PENALTY_HEAD_RACE * std::max(0.5, length / THREAT_LENGTH_SCALE) * (0.5 + 0.5 * depth);
                if (queen_wary()) {
                    penalty *= queen_guard() ? QG_THREAT_MULT : QUEEN_THREAT_MULT;
                } else if (is_leader()) {
                    penalty *= LEADER_HEAD_MULT;
                }
                if (SMALL_THREAT_MULT != 1.0 && length <= TRADE_MAX_LENGTH &&
                    (!SMALL_THREAT_OUTNUMBERED || enemy_heads.size() > ally_heads.size())) {
                    penalty *= SMALL_THREAT_MULT;
                }
                score -= penalty;
            }
        }

        int const guard_radius = fall ? QF_GUARD_RADIUS : queen_guard() ? QG_GUARD_RADIUS : QUEEN_GUARD_RADIUS;
        if ((is_queen() || fall) && guard_radius > 0) {
            for (Position const& enemy : enemy_heads) {
                int const gap = manhattan(destination, enemy);
                if (gap <= guard_radius) {
                    score -= QUEEN_GUARD_PENALTY * (guard_radius + 1 - gap);
                }
            }
            for (Ghost const& ghost : ghosts) {
                if (ghost.round == round && !ghost.shared) {
                    continue;
                }
                int const gap = manhattan(destination, ghost.pos) - (round - ghost.round);
                if (gap <= guard_radius) {
                    score -= QUEEN_GUARD_PENALTY * (guard_radius + 1 - std::max(0, gap));
                }
            }
            if (last_dead_end || (!last_reaches_tail && last_room < length + 2.0)) {
                score -= (queen_guard() ? QG_DEAD_PENALTY : QUEEN_DEAD_PENALTY);
            }
        }
        if (QUEEN_HOME_LEASH > 0 && real_queen() && queen_home.x >= 0) {
            int const leash = std::min(QUEEN_HOME_LEASH, (width + height) / 8);
            score -= QUEEN_HOME_SLOPE * std::max(0, manhattan(destination, queen_home) - leash);
        }
        if (QG_HOME_RADIUS > 0 && queen_guard() && queen_home.x >= 0) {
            score -= QG_HOME_PENALTY * std::max(0, manhattan(destination, queen_home) - QG_HOME_RADIUS);
        }
        if (QUEEN_HERD && real_queen() && !qs_plain) {
            int const cell = index_of(destination);
            int gain = std::clamp(herd_gain(cell), -STRIDE_MAX, STRIDE_MAX);
            if (boxed || !survey.reaches_tail || pocket < POCKET_CAP || threat_at(cell) > 0 || risk_at(cell) > 0) {
                gain = std::min(gain, 0);
            }
            if (pearl_here[cell]) {
                gain = std::max(gain, 0);
            }
            score += HERD_PULL * gain;
            if (HERD_BEHIND > 0.0) {
                int back = std::clamp(herd_state().ahead - herd_ahead(cell), -STRIDE_MAX, STRIDE_MAX);
                if (boxed || !survey.reaches_tail || pocket < POCKET_CAP || threat_at(cell) > 0 || risk_at(cell) > 0) {
                    back = std::min(back, 0);
                }
                if (pearl_here[cell]) {
                    back = std::max(back, 0);
                }
                score += HERD_BEHIND * back;
            }
        }
        if (fall && fb_pull && fb_dist[index_of(destination)] >= 0) {
            int const gain = fallback_gain(index_of(destination));
            // Leading, the pull outweighs keep-away, and a boxed step ranks below any other step.
            score += fb_lead ? QF_PULL * (std::clamp(gain, -STRIDE_MAX, STRIDE_MAX) - (boxed ? 2 : 0))
                             : QF_TIE_PULL * std::clamp(gain, -QF_TIE_SPAN, QF_TIE_SPAN);
        }
        if (QG_SAFEZONE && zone_mode == 2) {
            score -= zone_cost(index_of(destination));
        }
        if (QG_CORNER && corner_hold) {
            score -= QG_CORNER_PENALTY * std::max(0, manhattan(destination, position_of(corner_center)) - QG_CORNER_RADIUS);
        }
        if (LEADER_GUARD_ROUNDS > 0 && is_leader() && round >= unswbc::Constants::MAX_ROUNDS - LEADER_GUARD_ROUNDS) {
            for (Position const& enemy : enemy_heads) {
                int const gap = manhattan(destination, enemy);
                if (gap <= LEADER_GUARD_RADIUS) {
                    score -= LEADER_GUARD_PENALTY * (LEADER_GUARD_RADIUS + 1 - gap);
                }
            }
            for (Ghost const& ghost : ghosts) {
                if (ghost.round == round && !ghost.shared) {
                    continue;
                }
                int const gap = manhattan(destination, ghost.pos) - (round - ghost.round);
                if (gap <= LEADER_GUARD_RADIUS) {
                    score -= LEADER_GUARD_PENALTY * (LEADER_GUARD_RADIUS + 1 - std::max(0, gap));
                }
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
        if (QG_CORNER && corner_gate(direction)) {
            return corner_portal_score(direction, usable);
        }
        if (QG_SAFEZONE && zone_blocked(head, direction)) {
            return SCORE_REJECT;
        }
        if (queen_portal_ban() || (QG_SAFEZONE && (zone_mode == 2 || zone_mode == 3)) || qh_shut(head, direction)) {
            return SCORE_PORTAL;
        }
        int const exit = portal_exit(head, direction);
        if (exit >= 0 && enter_time[exit] > 1) {
            return SCORE_REJECT;
        }
        if (portal_into_pocket(head, direction)) {
            return SCORE_PORTAL;
        }
        if (exit >= 0 ? mouth_fresh(exit) : mouth_fresh(-1)) {
            return SCORE_REJECT;
        }
        if (exit < 0 || (portal_guarded() && !portal_exit_safe(exit))) {
            return SCORE_PORTAL;
        }
        double const leap = length <= PORTAL_SCOUT_MAX_LENGTH && boxed_in() ? PORTAL_LEAP_SMALL : PORTAL_LEAP_PENALTY;
        double const score = score_step(position_of(exit)) - leap;
        if (length > PORTAL_SCOUT_MAX_LENGTH && last_seen_room < length + PORTAL_SAFETY_MARGIN) {
            return SCORE_PORTAL;
        }
        usable = true;
        return score;
    }

    bool edge_head_known() const {
        for (Position const& pos : enemy_heads) {
            if (manhattan(head, pos) <= 8) {
                return true;
            }
        }
        for (Ghost const& g : ghosts) {
            if (round - g.round <= GHOST_ROUNDS && manhattan(head, g.pos) <= 8) {
                return true;
            }
        }
        if (QUEEN_FAR_HEADS > 0) {
            for (Ghost const& g : far_sight().heads) {
                if (round - g.round <= QUEEN_FAR_HEADS && manhattan(head, g.pos) <= 8) {
                    return true;
                }
            }
        }
        return false;
    }

    // B: reverse simple paths to just outside the view; L3 pays before eating.
    bool edge_reach_path(std::vector<int>& path) const {
        int const steps = static_cast<int>(path.size()) - 1;
        Position const pos = position_of(path.back());
        bool const visible = torus_gap(pos.x, head.x, width) <= unswbc::Constants::VISION_RADIUS &&
                             torus_gap(pos.y, head.y, height) <= unswbc::Constants::VISION_RADIUS;
        if (!visible) {
            int parts = 3;
            int pearls = 0;
            for (int k = steps - 1, moved = 0; k >= 0; k--, moved++) {
                if (moved >= 1 && parts <= unswbc::Constants::MIN_SIZE) {
                    return false;
                }
                int const eat = reach_pearl(path[k]);
                parts += eat - (moved >= 1 ? 1 : 0);
                pearls += eat;
            }
            return pearls > 0;
        }
        if (steps >= QUEEN_EDGE_REACH) {
            return false;
        }
        for (Direction const direction : Direction::get_direction_list()) {
            if (edge_at(pos, direction) != EDGE_OPEN) {
                continue;
            }
            int const next = index_of(pos.add_dir(direction));
            if ((enter_time[next] != 0 && enter_time[next] != 2) ||
                std::find(path.begin(), path.end(), next) != path.end()) {
                continue;
            }
            path.push_back(next);
            bool const reached = edge_reach_path(path);
            path.pop_back();
            if (reached) {
                return true;
            }
        }
        return false;
    }

    bool edge_reach(int cell) const {
        if (QUEEN_EDGE_REACH <= 0 || !real_queen() || cell < 0 || edge_head_known()) {
            return false;
        }
        Position const pos = position_of(cell);
        if (seen_round[cell] != round || torus_gap(pos.x, head.x, width) > unswbc::Constants::VISION_RADIUS ||
            torus_gap(pos.y, head.y, height) > unswbc::Constants::VISION_RADIUS) {
            return false;
        }
        std::vector<int> path{cell};
        return edge_reach_path(path);
    }

    void veto_edge_moves(std::array<double, 4>& scores, std::array<bool, 4> const& scored,
                         std::array<int, 4> const& dests, std::array<bool, 4>& blind) const {
        if (QUEEN_EDGE_REACH <= 0 || !real_queen() || edge_head_known()) {
            return;
        }
        std::array<bool, 4> risk{};
        bool open = false;
        for (std::size_t k = 0; k < scores.size(); k++) {
            if (scored[k] && dests[k] >= 0 && scores[k] > SCORE_REJECT * 0.5) {
                risk[k] = edge_reach(dests[k]);
                open = open || !risk[k];
            }
        }
        if (open) {
            for (std::size_t k = 0; k < scores.size(); k++) {
                if (risk[k]) {
                    scores[k] = SCORE_REJECT;
                    blind[k] = false;
                }
            }
        }
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
        std::array<int, 4> route_dist{};
        route_dist.fill(-1);
        std::array<double, 4> spaces{};
        std::array<double, 4> others{};
        std::array<int, 4> pearls{};
        std::array<bool, 4> dead{};
        std::array<bool, 4> harvest{};
        std::array<bool, 4> portal_dead{};
        std::array<int, 4> portal_pearls{};
        std::array<double, 4> portal_space{};
        std::array<double, 4> portal_other{};
        std::array<Survey, 4> surveys{};
        double best_open_space = SCORE_REJECT;
        std::array<bool, 4> closed{};
        std::array<bool, 4> imminent{};
        std::array<bool, 4> eats{};
        std::array<bool, 4> plain{};
        double best_base = SCORE_REJECT;
        bool const scouting = can_scout_portals();

        for (std::size_t k = 0; k < directions.size(); k++) {
            Direction const direction = directions[k];
            std::uint8_t const edge = edge_at(head, direction);
            double score = SCORE_REJECT;

            last_room = 0.0;
            last_reaches_tail = false;
            last_dist_route = -1;
            if (edge == EDGE_PORTAL) {
                bool usable = false;
                if (HARVEST_PORTAL) {
                    last_dead_end = false;
                    last_pearls = 0;
                    last_pocket = 0.0;
                }
                score = score_portal_step(direction, usable);
                if (TARGET_REACHABLE ? entry_portal_dead(usable, last_dead_end)
                                     : HARVEST_PORTAL && usable && last_dead_end && !real_queen()) {
                    portal_dead[k] = true;
                    portal_pearls[k] = last_pearls;
                    portal_space[k] = last_space;
                    portal_other[k] = score - last_space + last_cramped - last_bonus + last_pocket;
                }
                dests[k] = usable ? portal_exit(head, direction) : -1;
                scored[k] = usable;
                any_enterable = any_enterable || usable;
                // A hunter scouts an unseen portal only as its way out.
                bool const scout = QH_SCOUT && qh_on ? static_cast<int>(k) == escape_through : scouting;
                blind[k] = scout && !usable && leads_to_unknown(head, direction) && !mouth_fresh(-1) &&
                           !(QG_SAFEZONE && zone_blocked(head, direction));
            } else if (edge != EDGE_KELP) {
                Position const destination = head.add_dir(direction);
                dests[k] = index_of(destination);
                bool const enterable = enter_time[index_of(destination)] <= 1;
                any_enterable = any_enterable || enterable;
                if (is_feeder() && !is_ally_head(destination) &&
                    (in_leader_keep_off(destination) || on_leader_ray(destination))) {
                    score = SCORE_REJECT;
                } else if (enterable) {
                    score = score_step(destination);
                    if (LOOK_DEPTH > 0 && !is_feeder()) {
                        score += look_gain(index_of(destination));
                    }
                    scored[k] = true;
                    surveys[k] = last_survey;
                    best_base = std::max(best_base, score - last_bonus);
                    spaces[k] = last_space;
                    others[k] = score - last_space + last_cramped - last_bonus;
                    pearls[k] = last_pearls;
                    dead[k] = last_dead_end;
                    closed[k] = !last_reaches_tail && last_room < length + 2.0;
                    if (!last_dead_end) {
                        best_open_space = std::max(best_open_space, last_space);
                    }
                    if (EAT_FIRST) {
                        plain[k] = true;
                        eats[k] = pearl_here[dests[k]] && (FEEDER_EAT || !is_feeder()) && !in_leader_pearl_zone(dests[k]) &&
                                  last_pocket <= 0.0 && !dead[k] && !closed[k] && threat_at(dests[k]) == 0 &&
                                  risk_at(dests[k]) == 0 && !enemy_can_step_to(destination);
                    }
                } else if (is_enemy_head(destination)) {
                    score = is_trader() && is_trade_target_cell(index_of(destination)) ? TRADE_REWARD
                                                                                      : SCORE_REJECT * 0.5;
                } else if (is_ally_head(destination)) {
                    
                    score = SCORE_REJECT * 1.5;
                }
            }
            if (SHORT_EVADE) {
                evade_state()->open[k] = scored[k] && dests[k] >= 0 && !last_dead_end &&
                                        (last_reaches_tail || last_room >= length + 2.0);
            }
            scores[k] = score;
            rooms[k] = last_room;
            reaches[k] = last_reaches_tail;
            route_dist[k] = scored[k] ? last_dist_route : -1;
        }

        if (EAT_FIRST) {
            std::array<double, 4> ground{};
            for (std::size_t k = 0; k < directions.size(); k++) {
                ground[k] = plain[k] ? surveys[k].own_seen + UNSEEN_DISCOUNT * surveys[k].own_unseen : 0.0;
            }
            for (std::size_t k = 0; k < directions.size(); k++) {
                if (!eats[k]) {
                    continue;
                }
                double rest = 0.0;
                for (std::size_t j = 0; j < directions.size(); j++) {
                    if (j != k && plain[j]) {
                        rest = std::max(rest, ground[j]);
                    }
                }
                if (rest > ground[k]) {
                    scores[k] += WEIGHT_TERRITORY * (rest - ground[k]);
                }
            }
        }

        
        
        for (std::size_t k = 0; k < directions.size(); k++) {
            if (portal_dead[k] && scores[k] > SCORE_REJECT * 0.5 &&
                harvestable(portal_pearls[k], rooms[k], best_open_space <= SCORE_REJECT * 0.5)) {
                spaces[k] = portal_space[k];
                others[k] = portal_other[k];
                pearls[k] = portal_pearls[k];
                dead[k] = true;
            }
            if (dead[k] && scores[k] > SCORE_REJECT * 0.5 &&
                harvestable(pearls[k], rooms[k], best_open_space <= SCORE_REJECT * 0.5)) {
                double const space = best_open_space > SCORE_REJECT * 0.5 ? best_open_space : spaces[k];
                scores[k] = space + others[k] +
                            HARVEST_SEGMENT_VALUE * (pearls[k] - unswbc::Constants::MIN_SIZE);
                harvest[k] = true;
            }
        }

        hit_blocked = false;
        pay_open = false;
        if (ring_wary()) {
            bool risky = false;
            std::array<bool, 2> open{};
            for (std::size_t k = 0; k < directions.size(); k++) {
                if (!scored[k] || dests[k] < 0) {
                    continue;
                }
                int const risk = risk_at(dests[k]);
                risky = risky || risk > 0;
                if (risk < 2 && !closed[k]) {
                    open[static_cast<std::size_t>(risk)] = true;
                }
            }
            for (std::size_t k = 0; k < directions.size(); k++) {
                if (!scored[k] || dests[k] < 0) {
                    continue;
                }
                int const risk = risk_at(dests[k]);
                if (risk == 2 && (open[0] || open[1])) {
                    scores[k] -= QS_HIT_PENALTY;
                } else if (risk == 1 && open[0]) {
                    scores[k] -= QS_PAY_PENALTY;
                }
            }
            hit_blocked = risky && !open[0];
            pay_open = open[1];
        }

        apply_route(scores, scored, closed, dests, route_dist);

        cornered = false;
        if (length >= LONG_SAFE_MIN_LENGTH) {
            std::array<int, 4> level{};
            level.fill(-2);
            int best_level = -2;
            bool any_scored = false;
            bool all_imminent = true;
            bool all_exposed = true;
            for (std::size_t k = 0; k < directions.size(); k++) {
                if (!scored[k] || dests[k] < 0 || scores[k] <= SCORE_REJECT * 0.5) {
                    continue;
                }
                any_scored = true;
                imminent[k] = enemy_can_step_to(position_of(dests[k]));
                all_imminent = all_imminent && imminent[k];
                all_exposed = all_exposed && exposure_at(dests[k]) > 0;
                level[k] = closed[k] || (dead[k] && !is_big()) ? -1 : std::max(THREAT_REACH_MAX, BIG_TRUE_REACH) + 1 - exposure_at(dests[k]);
                if (dead[k] && !closed[k] && is_big()) {
                    level[k] = std::min(level[k], BIG_DEAD_LEVEL);
                }
                if (imminent[k] && !closed[k] && is_big()) {
                    level[k] = 0;
                }
                best_level = std::max(best_level, level[k]);
            }
            for (std::size_t k = 0; k < directions.size(); k++) {
                if (level[k] > -2 && level[k] < best_level) {
                    scores[k] -= LONG_THREAT_VETO * (best_level - level[k]);
                }
            }
            cornered = any_scored && ((all_imminent && length >= DODGE_MIN_LENGTH) || (is_big() && all_exposed));
        }

        if (QUEEN_EDGE_REACH > 0 && real_queen()) {
            veto_edge_moves(scores, scored, dests, blind);
        }
        for (std::size_t k = 0; k < directions.size(); k++) {
            Direction const direction = directions[k];
            double score = scores[k];
            if (blind[k] && best_base > SCORE_REJECT * 0.5) {
                score = best_base + target_bonus(1, WEIGHT_PORTAL_SCOUT);
            }
            if (static_cast<int>(k) == escape_through && score > SCORE_REJECT * 0.5) {
                score += ROUTE_OVERRIDE * 10.0;
            }

            score += 0.25 * ((TIE_SEED * 101 + ct.get_id() * 31 + round * 17 + static_cast<int>(k) * 7) % 5);
            if (HEADING_TIE > 0.0 && (HEADING_TIE_ROUNDS <= 0 || round < HEADING_TIE_ROUNDS) &&
                length <= CENTER_MAX_LENGTH && !real_queen() && !is_leader() && !is_feeder() && scored[k] &&
                score > SCORE_REJECT * 0.5 && directions[k] == ct.get_dir()) {
                score += HEADING_TIE;
            }
            if (PORTAL_SCOUT_MIN_LEN > 0 && !real_queen() && length < PORTAL_SCOUT_MIN_LEN) {
                portal_scout_choice()->scored = true;
                portal_scout_choice()->scores[k] = score;
                portal_scout_choice()->open[k] = scored[k] && score > SCORE_REJECT * 0.5;
            }
            if (POCKET_KEEP_OUT) {
                pocket_choice()->scored = true;
                pocket_choice()->scores[k] = score;
                pocket_choice()->open[k] = (scored[k] || blind[k]) && score > SCORE_REJECT * 0.5;
            }
            if (QUEEN_CORRIDOR_GUARD > 0 && real_queen()) {
                corridor_choice()->scored = true;
                corridor_choice()->scores[k] = score;
                corridor_choice()->open[k] = (scored[k] || blind[k]) && score > SCORE_REJECT * 0.5;
            }
            if (LONG_SAFETY) {
                step_score[k] = score;
                step_dest[k] = scored[k] ? dests[k] : -1;
                step_closed[k] = closed[k];
            }

            if (SHORT_EVADE) {
                evade_state()->scores[k] = score;
                evade_state()->dests[k] = scored[k] ? dests[k] : -1;
                evade_state()->open[k] = evade_state()->open[k] && score > SCORE_REJECT * 0.5;
            }
            if (MATE_UNPIN && unpin_state()->near) {
                Unpin& state = *unpin_state();
                state.scored = true;
                state.scores[k] = score;
                state.open[k] = scored[k] && dests[k] >= 0 && score > SCORE_REJECT * 0.5;
            }
            if (DEBUG_LOG) {
                ct.output_log("r", round, "len", length, "trail", static_cast<int>(trail.size()), "dir",
                              direction, "edge", static_cast<int>(edge_at(head, direction)), "enter",
                              enter_time[index_of(head.add_dir(direction))], "score", score);
            }

            if (score > best_score) {
                best_score = score;
                best = direction;
                chosen_survey = surveys[k];
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
    std::array<bool, 3> sym_alive{true, true, true};
    int sym_fixed = -1;
    std::vector<std::uint8_t> west_edge;
    std::vector<int> north_portal;
    std::vector<int> west_portal;
    std::vector<std::array<int, 2>> portal_edges;
    std::vector<std::uint8_t> pearl_here;
    std::vector<int> pearl_timer;
    std::vector<int> seen_round;
    std::vector<std::uint8_t> hot;
    std::vector<int> low_seen;
    std::vector<int> timer_max;
    std::vector<double> discount_table;
    std::vector<int> pocket_stamp;
    std::vector<int> pocket_queue;
    std::vector<int> pocket_doors;
    int pocket_mark = 0;
    std::vector<int> known_stamp;
    std::vector<int> known_steps;
    std::vector<int> known_eaten;
    std::vector<int> known_queue;
    int known_mark = 0;
    std::vector<int> center_dist;
    int center_dist_round = -1;
    std::vector<int> occupied_round;
    std::vector<int> corpse_round;
    std::vector<int> fast_seen;

    std::vector<int> enter_time;
    std::vector<int> dirty;
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
    sonar_codec::Key sonar_key{};
    bool sonar_enabled = false;
    bool aggressive = false;
    int grow_round = LEADER_GROW_ROUND;
    int feed_round = ENDGAME_ROUND;
    int enemy_big_seen = 0;
    int first_contact = -1;
    int last_contact = -1;
    bool home_closed = false;
    bool queen_game = false;
    int big_enemy_round = -1;
    int big_enemy_parts = 0;
    Position big_enemy_pos{};
    int center_rounds = CENTER_ROUNDS;
    int center_margin = CENTER_OUTNUMBER_MARGIN;
    bool center_map = false;
    int stall_best = -1;
    int stall_round = 0;
    bool fb_on = false;
    bool fb_pull = false;
    bool fb_lead = false;
    int fb_floor = 0;
    std::vector<Spot> fb_spots;
    std::vector<int> fb_dist;
    std::vector<int> fb_other;
    std::vector<int> fb_queue;
    int feeder_approach = FEEDER_APPROACH;
    int rally_fresh = RALLY_FRESH;
    Position known_leader_pos{};
    Direction known_leader_dir = dir_of(Direction::NORTH);
    bool zone_active = false;
    Position zone_head{};
    std::vector<Position> enemy_heads;
    std::vector<int> enemy_head_ids;
    std::vector<int> trade_target_stamp;
    int trade_targets = 0;
    std::vector<int> hunt_stamp;
    int hunt_targets = 0;
    std::vector<Direction> act_dirs;
    int turn_split = 0;
    std::vector<int> threat_stamp;
    std::vector<Ghost> ghosts;
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
    std::vector<std::pair<int, int>> mouths;
    double last_room = 0.0;
    int last_dist_route = -1;
    int route_target = -1;
    int escape_target = -1;
    int escape_through = -1;
    std::vector<int> escape_stamp;
    std::vector<int> escape_steps;
    std::vector<int> escape_queue;
    int escape_mark = 0;
    double last_bonus = 0.0;
    double last_space = 0.0;
    double last_cramped = 0.0;
    int last_pearls = 0;
    bool last_dead_end = false;
    double last_pocket = 0.0;
    int chosen_pearls = 0;
    bool chosen_harvest = false;
    Survey chosen_survey{};
    Survey last_survey{};
    bool harvesting_now = false;
    int survey_back = -1;
    int last_growth_round = 0;
    int inc_target = -1;
    int inc_round = -1000;
    std::vector<std::pair<Position, int>> recent_allies;
    int growth_length = 0;
    bool cornered = false;
    int harvest_round = SPLIT_ROUND0 ? -2 : -1;
    int behind_round = -1;
    double behind_room = 0.0;
    double last_seen_room = 0.0;
    bool last_reaches_tail = false;

    std::vector<int> look_cells;
    int queen_id = -1;
    Position queen_home{-1, -1};
    int enemy_queen_id = -1;
    Position enemy_queen_pos{};
    int enemy_queen_round = -1;
    bool hunt_queen = false;
    bool sure_queen = false;
    bool survey_pessimist = false;
    bool survey_no_portal = false;
    bool survey_ally_block = false;
    std::vector<int> qk_margin;
    std::vector<std::tuple<Position, int, int>> danger_log;
    std::vector<int> qk_stamp;
    int qk_mark = 0;
    std::vector<int> qb_seen;
    std::vector<int> qb_dist;
    std::vector<int> qb_queue;
    int qb_mark = 0;
    std::vector<Direction> qb_path;
    std::vector<Direction> qb_best;
    double qb_best_score = 0.0;
    int qb_evals = 0;
    std::vector<int> ally_block_stamp;
    int zp_mouth = -1;
    int zp_dir = 0;
    int zp_id = -1;
    int zp_until = -1;
    int zone_mouth = -1;
    int zone_dir = 0;
    int zone_size = 0;
    int zone_core = 0;
    int zone_id = -1;
    bool zone_two = false;
    bool zone_claimed = false;
    int zone_mode = 0;
    int zone_enter_round = -1;
    int zone_entry = -1;
    bool zs_unknown = false;
    int zone_clear = 0;
    int zone_last_check = -1000;
    int zone_check_dir = -1;
    bool zone_checked = false;
    int zone_target = -1;
    bool enemy_queen_dead = false;
    int qh_queen_id = -1;
    int qh_foe_id = -1;
    int qh_state = 0;
    int qh_alive_round = -1;
    int qh_seen_round = -1;
    Position qh_seen_pos{};
    int qh_seen_clear = 0;
    Position qh_pos{};
    int qh_round = -1;
    bool qh_in_view = false;
    int qh_foe_seen_round = -1;
    Position qh_foe_seen_pos{};
    int qh_foe_seen_clear = 0;
    int qh_foe_dead_round = -1;
    int qh_miss_round = -1;
    int qh_heard_round = -1000;
    bool qh_hunter = false;
    bool qh_on = false;
    bool qh_notice = false;
    int qh_route = -1;
    int qh_gate = -1;
    int qh_gate_dir = -1;
    bool qh_closed = false;
    std::vector<int> qh_stamp;
    std::vector<int> qh_queue;
    std::vector<int> qh_walk;
    std::vector<int> qh_sure;
    int qh_mark = 0;
    int eq_round = -1;
    Position eq_pos{};
    std::vector<int> zs_stamp;
    std::vector<int> zs_cut;
    std::vector<int> zs_degree;
    std::vector<int> zs_queue;
    int zs_mark = 0;
    int corner_center = -1;
    int corner_dir = -1;
    int corner_round = -1000;
    int corner_target = -1;
    bool corner_escape = false;
    bool corner_hold = false;
    std::vector<int> corner_bad;
    int turn_cells = 0;
    int survey_cap_now = 0;
    std::vector<int> ally_part_stamp;
    std::vector<int> hit_stamp;
    int hit_mark = 0;
    int hit_round = -1;
    std::vector<int> pay_stamp;
    std::vector<int> edge_ids;
    std::vector<Direction> enemy_head_dirs;
    std::vector<int> hit_count;
    std::vector<int> pay_count;
    std::vector<Foe> foes;
    std::vector<int> foe_now;
    int foe_longest = 0;
    std::array<double, 4> step_score{};
    std::array<int, 4> step_dest{};
    std::array<bool, 4> step_closed{};
    bool hit_blocked = false;
    bool pay_open = false;
    bool hit_head = false;
    bool pay_head = false;
    bool qs_plain = false;
    std::vector<int> peer_depth;
    std::vector<int> visit_stamp;
    std::vector<int> step_count;
    std::vector<int> eaten_count;
    std::vector<Position> bfs_queue;
    std::vector<std::uint8_t> bfs_beyond;
    std::vector<std::uint8_t> beyond_portal;
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
            if (QUEEN_EXIT_KEEP || POCKET_KEEP_OUT || QUEEN_EXIT_STRICT) {
                bot.fallback_exit(fallback_direction(controller));
            } else {
                controller.make_move(fallback_direction(controller));
            }
        }
        unswbc::end_turn();
    }
}
