#pragma once

#include <cstdint>

// Sonar wire format: bits 55..62 keyed check, bits 53..54 team tag (clear), the rest XORed with a keystream.
namespace sonar_codec {

constexpr std::uint64_t SECRET = 0xE1DE70530C48DE42ULL;
constexpr std::uint64_t CHECK_MASK = 0xFFULL << 55;
constexpr std::uint64_t TAG_MASK = 0x3ULL << 53;
constexpr std::uint64_t CIPHER_MASK = ~(CHECK_MASK | TAG_MASK);

struct Key {
    std::uint64_t k0 = 0;
    std::uint64_t k1 = 0;
};

constexpr std::uint64_t rotl(std::uint64_t x, int b) {
    return (x << b) | (x >> (64 - b));
}

// SipHash-2-4 of one 8-byte block.
constexpr std::uint64_t prf(Key key, std::uint64_t m) {
    std::uint64_t v0 = key.k0 ^ 0x736F6D6570736575ULL;
    std::uint64_t v1 = key.k1 ^ 0x646F72616E646F6DULL;
    std::uint64_t v2 = key.k0 ^ 0x6C7967656E657261ULL;
    std::uint64_t v3 = key.k1 ^ 0x7465646279746573ULL;
    auto const rounds = [&](int n) {
        for (int k = 0; k < n; k++) {
            v0 += v1;
            v1 = rotl(v1, 13) ^ v0;
            v0 = rotl(v0, 32);
            v2 += v3;
            v3 = rotl(v3, 16) ^ v2;
            v0 += v3;
            v3 = rotl(v3, 21) ^ v0;
            v2 += v1;
            v1 = rotl(v1, 17) ^ v2;
            v2 = rotl(v2, 32);
        }
    };
    std::uint64_t const tail = 8ULL << 56;
    v3 ^= m;
    rounds(2);
    v0 ^= m;
    v3 ^= tail;
    rounds(2);
    v0 ^= tail;
    v2 ^= 0xFF;
    rounds(4);
    return v0 ^ v1 ^ v2 ^ v3;
}

// Per-game key: secret + map size + team tag.
constexpr Key make_key(int width, int height, std::uint64_t tag, std::uint64_t secret = SECRET) {
    Key const root{secret, rotl(secret, 29) ^ 0xA5A5A5A5A5A5A5A5ULL};
    std::uint64_t const game = (static_cast<std::uint64_t>(width) << 40) | (static_cast<std::uint64_t>(height) << 16) |
                               (tag & 0x3);
    return Key{prf(root, game), prf(root, game | (1ULL << 63))};
}

constexpr std::uint8_t check_of(Key key, std::uint64_t plain) {
    return static_cast<std::uint8_t>(prf(key, plain & ~CHECK_MASK));
}

// Keystream depends on the check byte, so messages do not share one pad.
constexpr std::uint64_t stream_of(Key key, std::uint8_t check) {
    return prf(key, CHECK_MASK | check) & CIPHER_MASK;
}

constexpr std::uint64_t seal(Key key, std::uint64_t plain) {
    plain &= ~CHECK_MASK;
    std::uint8_t const check = check_of(key, plain);
    return (plain ^ stream_of(key, check)) | (static_cast<std::uint64_t>(check) << 55);
}

constexpr bool open(Key key, std::uint64_t wire, std::uint64_t& plain) {
    std::uint8_t const check = static_cast<std::uint8_t>((wire & CHECK_MASK) >> 55);
    plain = (wire & ~CHECK_MASK) ^ stream_of(key, check);
    return check_of(key, plain) == check;
}

// Reference vector from the SipHash paper's test set (8-byte input).
static_assert(prf(Key{0x0706050403020100ULL, 0x0F0E0D0C0B0A0908ULL}, 0x0706050403020100ULL) == 0x93F5F5799A932462ULL);

} // namespace sonar_codec
