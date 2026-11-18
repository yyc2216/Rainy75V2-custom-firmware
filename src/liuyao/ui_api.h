#ifndef V85_UI_API
#define V85_UI_API
#include "scene.h"
#if defined(_WIN32)
#define UI_EXPORT __declspec(dllexport)
#else
#define UI_EXPORT
#endif
enum {UI_RESET,UI_UP,UI_DOWN,UI_TICK,UI_DRAW};
typedef struct {uint32_t action,tick,epoch,valid,mask,seed;} ui_input;
UI_EXPORT unsigned ui_state_bytes(void);
UI_EXPORT int ui_step(scene_state*,const uint8_t*,uint8_t*,const ui_input*,chart_stats*);
#endif
