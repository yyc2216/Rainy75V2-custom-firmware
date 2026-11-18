#include "ui_api.h"
UI_EXPORT unsigned ui_state_bytes(void){return sizeof(scene_state);}
UI_EXPORT int ui_step(scene_state*s,const uint8_t*table,uint8_t*frame,const ui_input*in,chart_stats*st){
 if(!s||!table||!frame||!in||!st)return LY_ERR_INPUT;
 ly_table_t t={table,LY_TABLE_SIZE};
 int rc=0;
 switch(in->action){
 case UI_RESET:
  for(unsigned i=0;i<sizeof(*s);i++)((uint8_t*)s)[i]=0;
  scene_reset(s);break;
 case UI_UP:
  if(in->mask>7)return LY_ERR_INPUT;
  rc=scene_launch(s,(uint8_t)in->mask,in->epoch,(int)in->valid,in->tick,in->seed);break;
 case UI_DOWN:rc=scene_show(s);break;
 case UI_TICK:rc=scene_tick(s,&t,in->tick);break;
 case UI_DRAW:break;
 default:return LY_ERR_INPUT;
 }
 int dr=scene_render(s,&t,in->tick,frame,SCENE_FRAME_BYTES,st);
 return dr?dr:rc;
}
