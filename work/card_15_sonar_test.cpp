// Card #15 check: sonar codec round trip and forgery rejection. Prints one JSON object.
#include "../mybot2/sonar_codec.hpp"

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <utility>
#include <vector>

namespace sc = sonar_codec;

static std::uint64_t rng_state = 0x15C0DEC5EEDULL;

static std::uint64_t rnd() {
    std::uint64_t z = (rng_state += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

static std::uint64_t bits(int n) {
    return rnd() & ((1ULL << n) - 1);
}

// Same field layouts as pack_leader / pack_mouth / pack_sight / pack_zone in mybot2/main.cpp.
static std::uint64_t body_of(int kind, std::uint64_t tag) {
    std::uint64_t const tagged = (tag & 0x3) << 53;
    switch (kind) {
    case 0: // leader: id, length, round, x, y, facing
        return bits(16) | (bits(12) << 16) | (bits(9) << 28) | (bits(7) << 37) | (bits(7) << 44) | (bits(2) << 51) |
               tagged;
    case 1: // mouth: cell, round
        return bits(14) | (bits(9) << 14) | (0xA5ULL << 38) | tagged | (1ULL << 63);
    case 2: // sight: two enemy heads with size buckets, round, queen flag
        return bits(12) | (bits(2) << 12) | (bits(9) << 14) | (bits(12) << 23) | (bits(2) << 35) | (bits(1) << 37) |
               (0x5AULL << 38) | tagged | (1ULL << 63);
    case 3: // zone: mouth, direction, size, core, three flags
        return bits(14) | (bits(2) << 14) | (bits(8) << 16) | (bits(8) << 24) | (bits(3) << 32) | (0x3CULL << 38) |
               tagged | (1ULL << 63);
    default: // any body
        return rnd() & ~sc::CHECK_MASK;
    }
}

// The previous version's wire format: plain body with an XOR checksum.
static std::uint64_t old_encode(std::uint64_t plain) {
    std::uint64_t const body = plain & ((1ULL << 55) - 1);
    std::uint8_t sum = 0;
    for (int shift = 0; shift < 56; shift += 8) {
        sum ^= static_cast<std::uint8_t>(body >> shift);
    }
    return body | (static_cast<std::uint64_t>(sum) << 55) | (plain & (1ULL << 63));
}

struct Game {
    int width;
    int height;
    std::uint64_t tag;
    sc::Key key;
};

static Game random_game() {
    Game g{};
    g.width = 1 + static_cast<int>(rnd() % 128);
    g.height = 1 + static_cast<int>(rnd() % 128);
    g.tag = 1 + (rnd() & 1);
    g.key = sc::make_key(g.width, g.height, g.tag);
    return g;
}

static bool accepts(sc::Key key, std::uint64_t wire) {
    std::uint64_t plain = 0;
    return sc::open(key, wire, plain);
}

// stdin lines "S|F width height tag wire old": S = sent by the new bot (old = same message from the previous
// version), F = sent by the previous version's bot on the other team and heard by the new one.
static int replay_mode() {
    long sent = 0;
    long sent_ok = 0;
    long foreign = 0;
    long foreign_same = 0;
    long foreign_check_ok = 0;
    long foreign_taken = 0;
    char type = 0;
    int width = 0;
    int height = 0;
    unsigned long long tag = 0;
    unsigned long long wire = 0;
    unsigned long long old = 0;
    while (std::scanf(" %c %d %d %llu %llu %llu", &type, &width, &height, &tag, &wire, &old) == 6) {
        sc::Key const key = sc::make_key(width, height, tag);
        std::uint64_t plain = 0;
        bool const opened = sc::open(key, wire, plain);
        if (type == 'S') {
            sent++;
            sent_ok += opened && old_encode(plain) == old && wire != old;
        } else {
            foreign++;
            foreign_same += wire == old;
            foreign_check_ok += opened;
            foreign_taken += opened && ((plain >> 53) & 0x3) == tag;
        }
    }
    std::printf("{\"sent\": %ld, \"sent_decode_to_old_message\": %ld, \"foreign\": %ld, \"foreign_unchanged\": %ld, "
                "\"foreign_pass_check\": %ld, \"foreign_pass_check_and_tag\": %ld}\n",
                sent, sent_ok, foreign, foreign_same, foreign_check_ok, foreign_taken);
    return 0;
}

int main(int argc, char** argv) {
    if (argc > 1 && argv[1][0] == 'r') {
        return replay_mode();
    }
    long const trials = argc > 1 ? std::atol(argv[1]) : 200000;
    char const* const kinds[] = {"leader", "mouth", "sight", "zone", "any"};

    std::printf("{\"trials\": %ld", trials);

    // 1. Round trip for every message kind, across random games.
    long differing = 0;
    long cipher_bits = 0;
    long tag_kept = 0;
    std::printf(", \"round_trip\": {");
    for (int kind = 0; kind < 5; kind++) {
        long ok = 0;
        for (long t = 0; t < trials; t++) {
            Game const g = random_game();
            std::uint64_t const plain = body_of(kind, g.tag);
            std::uint64_t const wire = sc::seal(g.key, plain);
            std::uint64_t back = 0;
            ok += sc::open(g.key, wire, back) && back == plain;
            differing += __builtin_popcountll((wire ^ plain) & sc::CIPHER_MASK);
            cipher_bits += __builtin_popcountll(sc::CIPHER_MASK);
            tag_kept += ((wire ^ plain) & sc::TAG_MASK) == 0;
        }
        std::printf("%s\"%s\": %ld", kind ? ", " : "", kinds[kind], ok);
    }
    std::printf("}, \"scrambled_bit_fraction\": %.4f, \"tag_kept\": %ld",
                static_cast<double>(differing) / static_cast<double>(cipher_bits), tag_kept);

    // 2. Forgeries: count how many the receiver accepts.
    long old_scheme = 0;
    long wrong_size = 0;
    long wrong_tag = 0;
    long wrong_secret = 0;
    long size_only_key = 0;
    long one_flip = 0;
    long many_flips = 0;
    long random_wire = 0;
    for (long t = 0; t < trials; t++) {
        Game const g = random_game();
        int const kind = static_cast<int>(t % 5);
        std::uint64_t const plain = body_of(kind, g.tag);
        std::uint64_t const wire = sc::seal(g.key, plain);

        old_scheme += accepts(g.key, old_encode(plain));

        int other_width = g.width;
        int other_height = g.height;
        if (rnd() & 1) {
            other_width = 1 + (g.width + static_cast<int>(rnd() % 127)) % 128;
        } else {
            other_height = 1 + (g.height + static_cast<int>(rnd() % 127)) % 128;
        }
        wrong_size += accepts(g.key, sc::seal(sc::make_key(other_width, other_height, g.tag), plain));
        wrong_tag += accepts(g.key, sc::seal(sc::make_key(g.width, g.height, g.tag ^ 0x3), plain));
        std::uint64_t guess = rnd();
        guess += guess == sc::SECRET;
        wrong_secret += accepts(g.key, sc::seal(sc::make_key(g.width, g.height, g.tag, guess), plain));
        // Key from map size and tag alone (no secret), as in the first suggestion.
        size_only_key += accepts(g.key, sc::seal(sc::make_key(g.width, g.height, g.tag, 0), plain));

        one_flip += accepts(g.key, wire ^ (1ULL << (rnd() % 64)));
        std::uint64_t mask = 0;
        int const flips = 2 + static_cast<int>(rnd() % 7);
        while (__builtin_popcountll(mask) < flips) {
            mask |= 1ULL << (rnd() % 64);
        }
        many_flips += accepts(g.key, wire ^ mask);

        random_wire += accepts(g.key, rnd());
    }
    std::printf(", \"forgery_accepted\": {\"old_scheme\": %ld, \"wrong_size\": %ld, \"wrong_tag\": %ld, "
                "\"wrong_secret\": %ld, \"size_only_key\": %ld, \"one_flip\": %ld, \"many_flips\": %ld, "
                "\"random_wire\": %ld}",
                old_scheme, wrong_size, wrong_tag, wrong_secret, size_only_key, one_flip, many_flips, random_wire);

    // 3. Every single-bit flip of a sample of valid messages.
    long const samples = std::max(1L, trials / 64);
    long every_flip = 0;
    for (long t = 0; t < samples; t++) {
        Game const g = random_game();
        std::uint64_t const wire = sc::seal(g.key, body_of(static_cast<int>(t % 5), g.tag));
        for (int bit = 0; bit < 64; bit++) {
            every_flip += accepts(g.key, wire ^ (1ULL << bit));
        }
    }
    std::printf(", \"every_flip\": {\"accepted\": %ld, \"tried\": %ld}", every_flip, samples * 64);

    // 4. Every map size and team gets its own key.
    std::vector<std::pair<std::uint64_t, std::uint64_t>> keys;
    for (int width = 1; width <= 128; width++) {
        for (int height = 1; height <= 128; height++) {
            for (std::uint64_t tag = 1; tag <= 2; tag++) {
                sc::Key const key = sc::make_key(width, height, tag);
                keys.emplace_back(key.k0, key.k1);
            }
        }
    }
    std::sort(keys.begin(), keys.end());
    long const distinct = std::unique(keys.begin(), keys.end()) - keys.begin();
    std::printf(", \"keys\": {\"made\": %zu, \"distinct\": %ld}}\n", keys.size(), distinct);
    return 0;
}
