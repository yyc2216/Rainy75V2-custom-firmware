/* Offline native mode1 adapter. No flash or USB operations.
 * Only original heap, image APIs and tick source are called.
 * Cached root/image/buffer stay alive for the lifetime of the OEM scene.
 */
#include "ui_api.h"
#include "scene_assets.h"
#include <stdint.h>
typedef uint32_t word;
#define FN(ret,addr,...) ((ret (*)(__VA_ARGS__))(uintptr_t)((addr)|1u))
#define SHARED() FN(uint8_t*,0x08019cf0,void)()
#define TICK() FN(word,0x0803a2ba,void)()
#define ALLOC(n) FN(void*,0x08025c08,word)(n)
#define FREE(p) FN(void,0x0802ab34,void*)(p)
#define ROOT() FN(word,0x0802cd06,word)(0)
#define IMG(root) FN(word,0x0805c5b6,word)(root)
#define SET_SRC(img,src) FN(void,0x0805c5cc,word,void*)(img,src)
#define UI_CALL(addr,a,b,c) FN(void,addr,word,word,word)(a,b,c)
typedef struct{
 word root,image,verified,stage;
 uint8_t reserved[16];
 uint8_t latch,pad[3];
 word last_key_tick;
 word color;
 scene_state saved_state;
 word saved_rng;
} legacy_slot;
typedef struct{
 word header,bytes,data;
} image_desc;
typedef struct{
 image_desc desc;
 scene_state state;
 word rng,last_draw,needs_draw;
 uint8_t palette[1024];
 uint8_t frame[SCENE_FRAME_BYTES];
 uint8_t cloth_cache[185*154];
 uint16_t font_cache[SCENE_FONT_ROWS];
} color_block;
_Static_assert(sizeof(void*)==4,"ARM only");
_Static_assert(sizeof(legacy_slot)==224,"slot contract");
_Static_assert(sizeof(color_block)<=90000,"bounded cached block");
_Static_assert(__builtin_offsetof(legacy_slot,latch)==32,"original latch");
_Static_assert(__builtin_offsetof(legacy_slot,color)==40,"new cache");
_Static_assert(__builtin_offsetof(color_block,frame)==__builtin_offsetof(color_block,palette)+1024,"contiguous image");
extern const uint8_t v86_ly_table[LY_TABLE_SIZE];
static word prng(word x){if(!x)x=0x9e3779b9u;x^=x<<13;x^=x>>17;x^=x<<5;return x;}
static legacy_slot*slot(uint8_t*h){return (legacy_slot*)(void*)(h+0x3ca0);}
static word epoch(uint8_t*h,word tick,int*valid){
 const word*c=(const word*)(const void*)(h+0x3c80);
 *valid=(c[0]==0x54494d45u&&c[6]==~0x54494d45u);
 return *valid?c[1]+(tick-c[2])/1000u:0;
}
static int render(color_block*b,word tick){
 chart_stats st;ly_table_t t={v86_ly_table,LY_TABLE_SIZE};
 int rc=scene_render(&b->state,&t,tick,b->frame,SCENE_FRAME_BYTES,&st,b->cloth_cache,b->font_cache);
 if(rc)return 0;
 b->last_draw=tick;b->needs_draw=0;return 1;
}
__attribute__((used,noinline,section(".entry.life")))
word v86_lifecycle(uint8_t*h){
 if(!h)return 0;
 legacy_slot*s=slot(h);
 color_block*b=(color_block*)(uintptr_t)s->color;
 word now=TICK();
 if(!b){
  b=ALLOC(sizeof(*b));if(!b)return 0;
  for(unsigned i=0;i<__builtin_offsetof(color_block,palette);i++)((uint8_t*)b)[i]=0;
  b->desc.header=0x1585000a;b->desc.bytes=56064;
  b->desc.data=(word)(uintptr_t)b->palette;
  make_palette(b->palette);scene_prepare_cloth(b->cloth_cache,(int16_t*)b->font_cache);scene_prepare_fonts(b->font_cache);
  if(s->stage){
   for(unsigned i=0;i<sizeof(scene_state);i++)((uint8_t*)&b->state)[i]=((const uint8_t*)&s->saved_state)[i];
   b->rng=s->saved_rng;
  }else{scene_reset(&b->state);b->rng=prng(now^0x83f3a711u);}
  b->needs_draw=1;
  if(!render(b,now)){FREE(b);return 0;}
  // Root may be cached on an image-allocation failure; no image points
  // into the block until SET_SRC. No buffer is leaked on either failure.
  if(!s->root){
   word root=ROOT();if(!root){FREE(b);return 0;}
   s->root=root;UI_CALL(0x08036c64,root,0xffff,0);UI_CALL(0x08036c7e,root,0xff,0);
  }
  if(!s->image){
   word image=IMG(s->root);if(!image){FREE(b);return 0;}
   s->image=image;
  }
  s->color=(word)(uintptr_t)b;
  SET_SRC(s->image,&b->desc);
  UI_CALL(0x0802fa78,s->image,9,0);
  UI_CALL(0x0802f244,s->image,0,0);
  UI_CALL(0x0802f274,s->image,0,0);
  return s->root;
 }
 if(!s->root||!s->image)return 0;
 if(b->state.error==1){
  int valid;epoch(h,now,&valid);
  if(valid){b->state.error=0;b->needs_draw=1;s->latch=0;}
 }
 if(b->state.flow.phase==CF_FLYING){
  ly_table_t t={v86_ly_table,LY_TABLE_SIZE};
  int rc=scene_tick(&b->state,&t,now);
  if(rc==CF_OK||b->state.error)b->needs_draw=1;
  if(now-b->last_draw>=16u)b->needs_draw=1;
 }
 if(b->needs_draw&&render(b,now))SET_SRC(s->image,&b->desc);
 return s->root;
}
__attribute__((used,noinline,section(".entry.key")))
int v86_key(word key){
 uint8_t*h=SHARED();if(!h)return 1;
 legacy_slot*s=slot(h);
 if(*(volatile uint8_t*)0x2003edb2!=1||!s->color)return 1;
 color_block*b=(color_block*)(uintptr_t)s->color;
 if(key==0u||key==0xffffffffu){s->latch=0;return 0;}
 if(key!=0x52u&&key!=0x51u&&key!=0x28u)return 1;
 word now=TICK();
 /* Press-only packets are valid; reject burst repeats, not the next toss. */
 if(s->latch==key&&now-s->last_key_tick<180u){s->last_key_tick=now;return 0;}
 s->latch=(uint8_t)key;s->last_key_tick=now;
 if(key==0x28u){scene_reset(&b->state);b->needs_draw=1;return 0;}
 if(key==0x51u){if(!scene_show(&b->state))b->needs_draw=1;return 0;}
 if(b->state.flow.phase!=CF_READY&&b->state.flow.phase!=CF_LANDED)return 0;
 int valid;word e=epoch(h,now,&valid);
 b->rng=prng(b->rng^now);word mask=b->rng&7u;
 b->rng=prng(b->rng);
 if(scene_launch(&b->state,(uint8_t)mask,e,valid,now,b->rng)==LY_ERR_CLOCK)s->latch=0;
 b->needs_draw=1;return 0;
}



/* Match old sky ownership: native cleanup first. If the active root is
 * our own, load the already-existing native blink root while the stock
 * transition is dark. No additional scheduler or PWM calls. */
__attribute__((used,noinline,section(".entry.cleanup")))
void v91_cleanup(void){
 FN(void,0x0805a6bc,void)();
 uint8_t*h=SHARED();if(!h)return;
 legacy_slot*s=slot(h);
 color_block*b=(color_block*)(uintptr_t)s->color;
 if(!b||!s->root||!s->image)return;
 word display=FN(word,0x0802a7f0,void)();
 if(!display)return;
 volatile word*active=(volatile word*)(uintptr_t)(display+16);
 if(*active==s->root){
  word blink=*(volatile word*)0x2004c9c4;
  if(!blink||blink==s->root)return;
  FN(void,0x0802b0e0,word)(blink);
  if(*active!=blink)return;
 }
 for(unsigned i=0;i<sizeof(scene_state);i++)((uint8_t*)&s->saved_state)[i]=((const uint8_t*)&b->state)[i];
 s->saved_rng=b->rng;s->stage=1;s->latch=0;
 SET_SRC(s->image,(void*)0);
 FN(void,0x0802c758,word)(s->root);
 s->root=0;s->image=0;s->color=0;
 FREE(b);
}

