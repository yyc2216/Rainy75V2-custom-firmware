#include "scene.h"
#include "compact_font.h"
enum {BG,INK,MUTE,LINE,TEAL,RED,GOLD,MOVING};
typedef struct {uint8_t *fb;chart_stats *st;const uint16_t *fonts;} ctx;
static const char *stems[10]={"\170","\031","\025","\020","\127","\113","\122","\227","\066","\173"};
static const char *branches[12]={"\100","\023","\106","\052","\230","\114","\050","\147","\171","\233","\130","\036"};
static const char *elem[5]={"\146","\164","\063","\235","\156"};
static const char *relations[5]={"\041\124","\100\101","\076\224","\103\252","\165\154"};
static const char *spirits[6]={"\246\255","\151\243","\046\241","\214\212","\174\211","\167\153"};
static const char *palaces[8]={"\032","\042","\201","\245","\115","\064","\205","\065"};
static const char *roles[8]={"\150\104","\017\024","\033\024","\021\024","\061\024","\034\024","\163\253","\125\253"};
static const char *xunkong[6]={"\130\036","\171\233","\050\147","\230\114","\106\052","\100\023"};
static uint8_t branch_el(uint8_t b) {
    static const uint8_t w[12]={4,2,0,0,2,1,1,2,3,3,2,4};
    return b<12?w[b]:0;
}
static void pix(ctx *c,int x,int y,unsigned v){
 if((unsigned)x>=320 || (unsigned)y>=172){c->st->outside++;return;}
 if(y<3||y>=169)return;
 c->fb[(unsigned)y*320+(unsigned)x]=(uint8_t)v;
}
static void fill(ctx *c,int x,int y,int w,int h,unsigned ink){
 for(int j=0;j<h;j++)for(int i=0;i<w;i++)pix(c,x+i,y+j,ink);
}


static unsigned readbits(const uint8_t*src,unsigned *pos,unsigned n){
 unsigned p=*pos,i=p>>3;unsigned v=src[i];
 if((p&7)+n>8)v|=(unsigned)src[i+1]<<8;
 if((p&7)+n>16)v|=(unsigned)src[i+2]<<16;
 *pos=p+n;return(v>>(p&7))&((1u<<n)-1);
}
static void unpackfont(uint16_t*out,const uint8_t*src,const uint16_t*dict,unsigned count,unsigned sz,unsigned d){
 unsigned pos=0;
 for(unsigned i=0;i<count;i++){
 unsigned flag=readbits(src,&pos,1);
 out[i]=flag?dict[readbits(src,&pos,d)]:readbits(src,&pos,sz);
 }
}
void scene_prepare_fonts(uint16_t*out){
 unpackfont(out,stream10,dict10,ROWS10,10,4);
 unpackfont(out+ROWS10,stream12,dict12,ROWS12,12,5);
}
static int glyph(ctx*c,int x,int y,uint16_t cp,unsigned sz,unsigned ink){
 c->st->glyphs++;
 int idx=255;
 if(cp<=MAX_GLYPH_ID){
  const uint8_t*id=(sz==12?id12:id10)+2*(cp>>3);
  unsigned bit=1u<<(cp&7),v=id[0];
  if(v&bit){
   v&=bit-1;v=v-((v>>1)&0x55);v=(v&0x33)+((v>>2)&0x33);
   idx=id[1]+((v+(v>>4))&15);
  }
 }
 if(idx==255){c->st->missing++;return x+sz;}
 const uint16_t*rows=c->fonts+(sz==12?ROWS10:0)+idx*sz;
 int narrow=cp<ASCII_LIMIT,left=0,right=sz-1;
 if(narrow){
  unsigned mask=0;for(unsigned j=0;j<sz;j++)mask|=rows[j];
  if(!mask)return x+3;
  while(left<(int)sz-1 && !(mask&(1u<<(sz-1-left))))left++;
  while(right>left && !(mask&(1u<<(sz-1-right))))right--;
 }
 for(unsigned j=0;j<sz;j++){
  unsigned bits=rows[j];
  for(int i=left;i<=right;i++)if(bits&(1u<<(sz-1-i)))pix(c,x+i-left,y+j,ink);
 }
 return x+(narrow?right-left+2:sz);
}
static int str(ctx *c,int x,int y,const char *s,unsigned sz,unsigned ink){
 while(*s)x=glyph(c,x,y,(uint8_t)*s++,sz,ink);
 return x;
}
static int num(ctx*c,int x,int y,unsigned n,unsigned digits){
 char b[10];b[digits]=0;for(unsigned i=digits;i>0;i--){b[i-1]=(char)(DIGIT_ZERO+n%10);n/=10;}return str(c,x,y,b,10,INK);
}
static void relation(ctx*c,int x,int y,uint8_t rel,uint8_t packed,unsigned ink){
 x=str(c,x,y,relations[rel],10,ink);x=str(c,x,y,stems[packed>>4],10,ink);
 x=str(c,x,y,branches[packed&15],10,ink);str(c,x,y,elem[branch_el(packed&15)],10,ink);
}
static void heading(ctx*c,int x,const char*tag,const ly_table_t*t,uint8_t king,uint8_t pal,uint8_t role,unsigned ink){
 int z=str(c,x,42,tag,12,ink);str(c,z+4,42,ly_hexagram_name(t,king),12,ink);
 z=str(c,x,58,palaces[pal],10,MUTE);z=str(c,z,58,"\104",10,MUTE);str(c,z+5,58,roles[role],10,MUTE);
}
static void yao(ctx*c,int x,int y,int w,int yang,unsigned ink){
 if(yang)fill(c,x,y+4,w,2,ink);
 else{int a=(w-5)/2;fill(c,x,y+4,a,2,ink);fill(c,x+w-a,y+4,a,2,ink);}
}
static void marker(ctx*c,int x,int y,int mark,unsigned ink){
 if(mark)str(c,x,y,mark==1?"\024":"\121",10,ink);
}
static void moving(ctx*c,int x,int y,int yang,unsigned ink){
 if(yang){for(int i=1;i<6;i++){pix(c,x+i,y,ink);pix(c,x+i,y+6,ink);pix(c,x,y+i,ink);pix(c,x+6,y+i,ink);}}
 else for(int i=0;i<7;i++){pix(c,x+i,y+i,ink);pix(c,x+6-i,y+i,ink);}
}
static int chart_color(const ly_result_t*d,const ly_table_t*t,uint8_t*fb,unsigned bytes,chart_stats*st,const uint16_t*fonts){
 if(!d||!t||!fb||!st||bytes<SCENE_FRAME_BYTES||ly_check_table(t))return LY_ERR_INPUT;
 st->glyphs=st->missing=st->outside=0;ctx inst={fb,st,fonts},*c=&inst;
 for(unsigned i=0;i<SCENE_FRAME_BYTES;i++)fb[i]=0;
 int x=5;
 x=num(c,x,6,d->year,4);x=str(c,x,6,"\001",10,INK);x=num(c,x,6,d->month,2);
 x=str(c,x,6,"\001",10,INK);x=num(c,x,6,d->day,2);x+=4;
 x=num(c,x,6,d->hour,2);x=str(c,x,6,"\015",10,INK);x=num(c,x,6,d->minute,2);x=str(c,x,6,"\015",10,INK);num(c,x,6,d->second,2);
 str(c,184,6,"\140\202",10,GOLD);str(c,273,6,"\234\123",10,MUTE);
 fill(c,5,18,310,1,LINE);
 const char*labels[4]={"\120","\144","\137","\141"};
 for(unsigned k=0;k<4;k++){
  int j=5+79*k;ly_pillar_t p=d->pillar[k];
  str(c,j,24,labels[k],10,MUTE);
  x=str(c,j+13,23,stems[p.stem],12,INK);str(c,x,23,branches[p.branch],12,INK);
  str(c,j+42,25,xunkong[p.xun],10,GOLD);
 }
 fill(c,5,39,310,1,LINE);
 str(c,5,46,"\043\200",10,MUTE);str(c,29,46,"\040\200",10,MUTE);
 heading(c,88,"\150\051",t,d->original_kingwen,d->original_palace,d->original_role,INK);
 heading(c,201,"\053\051",t,d->changed_kingwen,d->changed_palace,d->changed_role,TEAL);
 if(!d->has_change)str(c,254,58,"\247",10,MUTE);
 fill(c,5,70,310,1,LINE);
 for(int i=0;i<6;i++){
  const ly_line_t*r=&d->line[5-i];int y=73+16*i;
  if(r->moving)fill(c,4,y-2,312,15,MOVING);
  str(c,5,y,spirits[r->spirit],10,INK);
  if(r->hidden_present)relation(c,29,y,r->hidden_relation,r->hidden_najia,INK);
  else str(c,29,y,"\016",10,INK);
  unsigned ink=r->moving?(r->original_yang?RED:TEAL):INK;
  relation(c,88,y,r->original_relation,r->original_najia,ink);
  yao(c,145,y,23,r->original_yang,ink);
  marker(c,171,y,r->original_marker,INK);
  if(r->moving)moving(c,186,y+2,r->original_yang,ink);
  relation(c,201,y,r->changed_relation,r->changed_najia,INK);
  yao(c,260,y,27,r->changed_yang,r->moving?TEAL:INK);
  marker(c,299,y,r->changed_marker,TEAL);
  if(i<5)fill(c,5,y+13,310,1,LINE);
 }
 fill(c,84,43,1,123,LINE);fill(c,197,43,1,123,LINE);
 return st->outside||st->missing?LY_ERR_STATE:LY_OK;
}
static void arrow(ctx*c,int x,int y,int down){
 fill(c,x+3,y,1,9,BG);
 for(int i=0;i<4;i++){int yy=down?y+8-i:y+i;pix(c,x+3-i,yy,BG);pix(c,x+3+i,yy,BG);}
}
int scene_render(const scene_state*s,const ly_table_t*t,uint32_t tick,uint8_t*fb,uint32_t bytes,chart_stats*st,const uint8_t*cache,const uint16_t*fonts){
 if(!s||!t||!fb||!st||bytes<SCENE_FRAME_BYTES)return LY_ERR_INPUT;
 if(s->flow.phase==CF_RESULT){
  if(!s->flow.chart_ready)return LY_ERR_STATE;
  return chart_color(&s->chart,t,fb,bytes,st,fonts);
 }
 st->glyphs=st->missing=st->outside=0;ctx inst={fb,st,fonts},*c=&inst;
 for(unsigned i=0;i<SCENE_FRAME_BYTES;i++)fb[i]=0;
 str(c,12,9,"\043\166",12,INK);
 int x=num(c,71,12,s->flow.visible,2);x=str(c,x+2,12,"\002",10,GOLD);num(c,x+2,12,6,2);
 fill(c,12,30,97,1,LINE);
 const char*levels[6]={"\044","\033","\021","\061","\034","\022"};
 const char*names[4]={"\204\240","\110\237","\110\240","\204\237"};
 for(int i=5;i>=0;i--){
  int y=36+(5-i)*19;
  str(c,15,y,levels[i],10,MUTE);
  if(i<s->flow.visible){
   int n=s->flow.session.values[i];if(n<6||n>9)return LY_ERR_STATE;
   unsigned ink=n==6?TEAL:n==9?RED:INK;
   yao(c,35,y,24,n==7||n==9,ink);
   if(n==6||n==9)moving(c,63,y+1,n==9,ink);
   str(c,75,y,names[n-6],10,ink);glyph(c,103,y,(uint16_t)(DIGIT_ZERO+n),10,ink);
  }else{fill(c,35,y+4,24,1,LINE);str(c,103,y,"\016",10,MUTE);}
  if(i>0)fill(c,12,y+13,97,1,LINE);
 }
 str(c,12,153,"\234\123",10,MUTE);
 scene_draw_right(s,tick,fb,cache);
 if(s->error)str(c,199,139,s->error==1?"\147\152\141":"\236\221",10,BG);
 else if(s->flow.phase!=CF_FLYING){
  int down=s->flow.phase==CF_COMPLETE&&s->flow.chart_ready;
  if(s->flow.phase==CF_COMPLETE&&!s->flow.chart_ready)str(c,199,139,"\217\203\026",10,BG);
  else{arrow(c,194,140,down);str(c,205,139,down?"\133\176":"\131\116",10,BG);}
 }
 return st->outside||st->missing?LY_ERR_STATE:LY_OK;
}

