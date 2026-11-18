#ifndef V84_CHART_H
#define V84_CHART_H
#include "liuyao_native.h"
#define CHART_W 320
#define CHART_H 172
#define CHART_BYTES (CHART_W*CHART_H/2)
typedef struct { unsigned glyphs,missing,outside; } chart_stats;
int chart_draw(const ly_result_t*,const ly_table_t*,uint8_t*,unsigned,chart_stats*);
int chart_entry(const uint8_t*,uint32_t,const uint8_t*,uint8_t*,chart_stats*);
#endif
