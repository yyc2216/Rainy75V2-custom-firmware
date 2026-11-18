#ifndef CAST_FLOW_H
#define CAST_FLOW_H
#include "liuyao_native.h"
enum { CF_READY, CF_FLYING, CF_LANDED, CF_COMPLETE, CF_RESULT };
enum { CF_OK=0, CF_BLOCK=1, CF_TOO_EARLY=2, CF_ANIMATION_MS=1300 };
typedef struct {
 ly_session_t session;
 uint32_t started;
 uint8_t phase,visible,last_mask,chart_ready;
} cast_flow_t;
void cf_reset(cast_flow_t *s);
int cf_launch(cast_flow_t *s,uint8_t mask,uint32_t epoch,int valid,uint32_t tick);
int cf_update(cast_flow_t *s,uint32_t tick);
int cf_compute(cast_flow_t *s,const ly_table_t *t,ly_result_t *r);
int cf_show(cast_flow_t *s);
#endif
