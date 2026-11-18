#include "cast_flow.h"
void cf_reset(cast_flow_t *s) {
 ly_session_reset(&s->session);
 s->started=0;s->phase=CF_READY;s->visible=0;s->last_mask=0;s->chart_ready=0;
}
int cf_launch(cast_flow_t *s,uint8_t mask,uint32_t epoch,int valid,uint32_t tick) {
 if((s->phase!=CF_READY && s->phase!=CF_LANDED)||s->session.count>=6) return CF_BLOCK;
 if(mask>7)return LY_ERR_INPUT;
 uint8_t coins[3]={(uint8_t)(mask&1),(uint8_t)((mask>>1)&1),(uint8_t)((mask>>2)&1)};
 int status=ly_session_throw(&s->session,coins,epoch,valid);
 if(status!=LY_OK)return status;
 s->last_mask=mask;s->started=tick;s->phase=CF_FLYING;return CF_OK;
}
int cf_update(cast_flow_t *s,uint32_t tick) {
 if(s->phase!=CF_FLYING)return CF_BLOCK;
 if((uint32_t)(tick-s->started)<CF_ANIMATION_MS)return CF_TOO_EARLY;
 s->visible=s->session.count;
 s->phase=s->visible==6?CF_COMPLETE:CF_LANDED;return CF_OK;
}
int cf_compute(cast_flow_t *s,const ly_table_t *t,ly_result_t *r) {
 if(s->session.count!=6 || (s->phase!=CF_FLYING && s->phase!=CF_COMPLETE))return CF_BLOCK;
 int status=ly_session_finish(t,&s->session,r);
 if(status==LY_OK)s->chart_ready=1;
 return status;
}
int cf_show(cast_flow_t *s) {
 if(s->phase!=CF_COMPLETE || !s->chart_ready)return CF_BLOCK;
 s->phase=CF_RESULT;return CF_OK;
}
