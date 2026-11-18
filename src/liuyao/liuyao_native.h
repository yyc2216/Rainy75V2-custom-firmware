/* Rainy75 V2 native six-line divination engine (offline candidate).
 * Upstream MIT source: songgoldenwind-crypto/liuyao-skills
 * pinned commit d3f4575d449c0872aac23a04fbd80e5f690506e6.
 * Exact user rules: changed Shi/Ying independent, changed LiuQin based on
 * ORIGINAL palace; six FuShen slots, midnight day, first coin locks time.
 *
 * No IO, no heap, no LCD, no flash writes, no libc in the core.
 * Table is firmware portable: V41 verified 1669-byte binary.
 */
#ifndef RAINY75_LIUYAO_NATIVE_H
#define RAINY75_LIUYAO_NATIVE_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
enum { LY_OK=0, LY_ERR_CLOCK=-1, LY_ERR_TABLE=-2,
       LY_ERR_DATE=-3, LY_ERR_INPUT=-4, LY_ERR_STATE=-5 };
enum { LY_TABLE_SIZE=804, LY_TABLE_JIE_OFFSET=391 };
typedef struct {
    const uint8_t *data;
    uint32_t length;
} ly_table_t;
typedef struct {
    uint8_t stem; /* 0..9: 甲乙丙丁戊己庚辛壬癸 */
    uint8_t branch; /* 0..11: 子丑寅卯辰巳午未申酉戌亥 */
    uint8_t xun; /* 0..5: 戌亥/申酉/午未/辰巳/寅卯/子丑 */
} ly_pillar_t;
typedef struct {
    uint8_t original_najia; /* high nibble stem, low nibble branch */
    uint8_t changed_najia;
    uint8_t hidden_najia;
    uint8_t original_relation; /* 0兄弟 1子孙 2妻财 3官鬼 4父母 */
    uint8_t changed_relation;
    uint8_t hidden_relation;
    uint8_t hidden_present; /* only when a missing kinship appears in palace */
    uint8_t spirit; /* 0青龙 1朱雀 2勾陈 3螣蛇 4白虎 5玄武 */
    uint8_t original_marker; /* 0 none 1世 2应 */
    uint8_t changed_marker;
    uint8_t original_yang; /* 1阳,0阴 */
    uint8_t changed_yang;
    uint8_t moving;
} ly_line_t;
typedef struct {
    uint32_t frozen_epoch; /* seconds since 2000-01-01 00:00 Beijing */
    uint16_t year;
    uint8_t month,day,hour,minute,second;
    uint8_t original_mask,changed_mask,moving_mask,has_change;
    uint8_t original_palace,original_role,changed_palace,changed_role;
    uint8_t original_kingwen,changed_kingwen;
    ly_pillar_t pillar[4]; /* year,month,day,hour */
    ly_line_t line[6]; /* bottom (初) to top (上) */
} ly_result_t;
typedef struct {
    uint32_t frozen_epoch;
    uint8_t values[6];
    uint8_t count;
    uint8_t valid_time;
} ly_session_t;

int ly_check_table(const ly_table_t *table);
int ly_calculate(const ly_table_t *table, uint32_t time_seconds,
                 const uint8_t yao_bottom_to_top[6], ly_result_t *result);
void ly_session_reset(ly_session_t *state);
int ly_session_throw(ly_session_t *state, const uint8_t coins[3],
                     uint32_t current_epoch, int clock_valid);
int ly_session_finish(const ly_table_t *table, const ly_session_t *state,
                      ly_result_t *result);
const char *ly_hexagram_name(const ly_table_t *table,uint8_t kingwen);

#ifdef __cplusplus
}
#endif
#endif
