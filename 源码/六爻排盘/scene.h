#ifndef V84_SCENE_H
#define V84_SCENE_H
#include "chart.h"
#include "cast_flow.h"
#define SCENE_FRAME_BYTES (320u*172u)
typedef struct { int16_t x,y,angle,drift; uint16_t impact,energy; uint8_t flips; int8_t direction; } coin_path;
typedef struct { cast_flow_t flow; ly_result_t chart; coin_path path[3]; uint8_t error; } scene_state;
void scene_reset(scene_state*);
int scene_launch(scene_state*,uint8_t,uint32_t,int,uint32_t,uint32_t);
int scene_tick(scene_state*,const ly_table_t*,uint32_t);
int scene_show(scene_state*);
int scene_render(const scene_state*,const ly_table_t*,uint32_t,uint8_t*,uint32_t,chart_stats*,const uint8_t*,const uint16_t*);
#define SCENE_FONT_ROWS 2294
void scene_prepare_fonts(uint16_t*);
void scene_draw_right(const scene_state*,uint32_t,uint8_t*,const uint8_t*);
void scene_prepare_cloth(uint8_t*,int16_t*);
#endif
