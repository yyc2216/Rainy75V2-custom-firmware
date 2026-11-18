#include "scene.h"
__declspec(dllexport) int result_frame(const uint8_t*t,uint32_t epoch,const uint8_t*vals,uint8_t*fb,chart_stats*stats){
 scene_state s={0};ly_table_t table={t,LY_TABLE_SIZE};
 uint16_t fonts[SCENE_FONT_ROWS];
 int rc=ly_calculate(&table,epoch,vals,&s.chart);if(rc)return rc;
 scene_prepare_fonts(fonts);s.flow.phase=CF_RESULT;s.flow.chart_ready=1;
 return scene_render(&s,&table,0,fb,SCENE_FRAME_BYTES,stats,0,fonts);
}
