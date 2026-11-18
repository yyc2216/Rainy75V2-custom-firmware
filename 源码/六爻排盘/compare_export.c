#include "scene.h"
__declspec(dllexport) int result_frame(const uint8_t*table,uint32_t epoch,const uint8_t*vals,uint8_t*fb,chart_stats*stats){
 scene_state s={0};ly_table_t t={table,LY_TABLE_SIZE};
 int rc=ly_calculate(&t,epoch,vals,&s.chart);if(rc)return rc;
 s.flow.phase=CF_RESULT;s.flow.chart_ready=1;
 return scene_render(&s,&t,0,fb,SCENE_FRAME_BYTES,stats);
}
