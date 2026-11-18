#include "scene.h"
#include "scene_assets.h"
#define Q 4096
#define G 1000
typedef struct {int32_t x,y,h,lean,angle,tilt,face;} pose_t;
static int min(int a,int b){return a<b?a:b;}
static int max(int a,int b){return a>b?a:b;}
static int abs_i(int a){return a<0?-a:a;}
static int mulq(int a,int b){return (a*b)/Q;}
static int clamp(int x,int lo,int hi){return max(lo,min(hi,x));}
#include "trig_table.h"
static int trig_at(unsigned i){unsigned j=i&63;int v=trig[i&64?64-j:j];return i&128?-v:v;}
static int sinq(int a){unsigned i=(unsigned)a&4095;unsigned j=i>>4;int u=(int)(i&15);return (trig_at(j)*(16-u)+trig_at(j+1)*u)/16;}
static int cosq(int a){return sinq(a+1024);}
static uint32_t rng(uint32_t*s){uint32_t x=*s;x^=x<<13;x^=x>>17;x^=x<<5;return *s=x;}
static int rand_range(uint32_t*s,int lo,int hi){return lo+(int)(rng(s)%(unsigned)(hi-lo+1));}
static int dist2(int x,int y,int a,int b){int dx=x-a,dy=y-b;return dx*dx+dy*dy;}
static void paths(coin_path*p,uint32_t seed){
 uint32_t s=seed?seed:0x9e3779b9;
 for(unsigned restart=0;restart<32;restart++){
  int n=0;
  for(int i=0;i<3;i++){
   int x=0,y=0,ok=0;
   for(int attempt=0;attempt<200;attempt++){
    x=rand_range(&s,155,276);y=rand_range(&s,42,112);ok=1;
    for(int j=0;j<i;j++)if(dist2(x,y,p[j].x,p[j].y)<37*37)ok=0;
    if(ok)break;
   }
   if(!ok)break;
   p[i]=(coin_path){(int16_t)x,(int16_t)y,(int16_t)rand_range(&s,-2048,2047),(int16_t)rand_range(&s,-7,7),(uint16_t)rand_range(&s,1597,1884),(uint16_t)rand_range(&s,750,1200),(uint8_t)rand_range(&s,2,4),(int8_t)(rng(&s)&1?1:-1)};
   n++;
  }
  if(n==3)return;
 }
 // Bounded fallback only on improbable rejection exhaustion.
 for(int i=0;i<3;i++)p[i]=(coin_path){(int16_t)(158+55*i),(int16_t)(i==1?101:53),(int16_t)rand_range(&s,-2048,2047),0,1720,950,3,1};
}
void scene_reset(scene_state*s){cf_reset(&s->flow);s->error=0;}
int scene_launch(scene_state*s,uint8_t mask,uint32_t epoch,int valid,uint32_t tick,uint32_t seed){
 int rc=cf_launch(&s->flow,mask,epoch,valid,tick);
 if(rc==LY_ERR_CLOCK)s->error=1;
 if(!rc){paths(s->path,seed);s->error=0;}
 return rc;
}
int scene_tick(scene_state*s,const ly_table_t*t,uint32_t tick){
 if(s->flow.session.count==6&&!s->flow.chart_ready){
  int rc=cf_compute(&s->flow,t,&s->chart);
  if(rc){s->error=2;return rc;}
 }
 return cf_update(&s->flow,tick);
}
int scene_show(scene_state*s){return cf_show(&s->flow);}
static pose_t pose(const coin_path*p,int i,int t,int face){
 int T=p->impact,vin=G*T/(2*Q)+10*Q/T;
 int e=460+80*(p->energy-750)/450;
 int v1=vin*e/1000,v2=v1*42/100,d1=2*v1*Q/G,d2=2*v2*Q/G;
 int end=T+d1+d2,span=Q-T,norm=T+span*29/100;
 int q,theta,angle,h,u,x,y;
 const int touch=1728;
 if(t<T){
  u=t*Q/T;q=t*Q/norm;h=mulq(T-t,10*Q/T+G*t/(2*Q));
  theta=p->direction*(touch+p->flips*(Q-u));
  angle=p->angle+p->direction*(2162+4779*(Q-u)/Q);
 }else{
  u=(t-T)*Q/span;q=Q-mulq(Q-T*Q/norm,mulq(Q-u,Q-u));
  if(t<T+d1){int dt=t-T;int z=dt*Q/d1;h=3*mulq(dt,v1-G*dt/(2*Q));theta=p->direction*(touch-mulq(828,z));}
  else if(t<end){int dt=t-T-d1,z=dt*Q/d2;h=4*mulq(dt,v2-G*dt/(2*Q));theta=p->direction*(900-mulq(280,z));}
  else {int z=clamp((t-end)*Q/max(1,Q-end),0,Q);h=0;theta=p->direction*mulq(mulq(620,mulq(Q-z,Q-z)),cosq(mulq(4915,z)+mulq(11469,mulq(z,z))));}
  angle=p->angle+p->direction*mulq(2162,mulq(Q-u,Q-u));
 }
 int sx=211+(i-1)*25,sy=105+(i%2)*3;
 q=clamp(q,0,Q);
 x=p->x-mulq(p->x-sx,Q-q)+(t<T?mulq(p->drift,sinq(t*2048/T))/4:0);
 y=p->y-mulq(p->y-sy,Q-q);
 if(t>=Q){x=p->x;y=p->y;theta=h=0;angle=p->angle;}
 if(t>=end){if(abs_i(theta)<=8)theta=0;if(abs_i(angle-p->angle)<=4)angle=p->angle;}
 int c=cosq(theta);return (pose_t){x,y,max(h,0),c<0?-sinq(theta):sinq(theta),angle,max(348,abs_i(c)),c>=0?face:1-face};
}
static uint8_t coin_index(int face,int x,int y){
 if((unsigned)x>=32||(unsigned)y>=32)return 0;
 unsigned idx=(unsigned)y*32+(unsigned)x;
 uint8_t b=scene_coins[face*512+(idx>>1)];
 return (uint8_t)((idx&1)?b&15:b>>4);
}
static void put(uint8_t*fb,int x,int y,uint8_t col){
 // All animations are clipped to the cloth region, never the record panel.
 if(x>=123&&x<308&&y>=9&&y<163)fb[y*320+x]=col;
}
static void shadow(uint8_t*fb,pose_t p){
 int x=p.x+1+p.h*52/100,y=p.y+2+p.h*65/100;
 int rx=16,ry=7+mulq(9,p.tilt),ca=cosq(p.angle),sa=sinq(p.angle);
 for(int j=-19;j<=19;j++)for(int i=-19;i<=19;i++){
  int u=mulq(i,ca)-mulq(j,sa),v=mulq(i,sa)+mulq(j,ca);
  if(u*u*ry*ry+v*v*rx*rx>rx*rx*ry*ry)continue;
  int a=x+i,b=y+j;
  if(a<123||a>=308||b<9||b>=163)continue;
  // Shadow uses precomputed, darkened matching cloth palette entries.
  uint8_t c=fb[b*320+a];if(c>=8&&c<40)fb[b*320+a]=(uint8_t)((p.h<10?220:236)+(c-8)/2);
 }
}
static void coin(uint8_t*fb,pose_t p){
 p.y-=p.h/3;
 int d=35+p.h*14/100,ca=cosq(p.angle),sa=sinq(p.angle);
 int ct=p.tilt,st=p.lean;
 int depth=max(1,abs_i(st)*d*94/(Q*1000)); /* V99: stronger low-resolution rim; face unchanged */
 int rx=d/2+2,ry=max(1,(d/2*ct+Q/2)/Q);
 int lx=mulq(-1761,ca)-mulq(-2171,sa);
 int ly=mulq(-1761,sa)+mulq(-2171,ca);
 int lz=2994;
 int faceLight=mulq(-ly,st)+mulq(lz,ct);
 int lit=clamp(2+faceLight*8/Q,0,11);
 // Blinn-Phong-style highlight lobe, without stored animation frames.
 int hz=mulq(ly,-st)+mulq(3934,ct);int spe=clamp(hz,0,Q);
 spe=mulq(spe,spe);spe=mulq(spe,spe);spe=mulq(spe,spe);spe=mulq(spe,spe);
 lit=clamp(lit+mulq(3,spe),0,11);
 for(int j=-rx-3;j<=rx+3;j++)for(int i=-rx-3;i<=rx+3;i++){
  int u=mulq(i,ca)-mulq(j,sa),v=mulq(i,sa)+mulq(j,ca);
  int tx=16+u*16/max(1,d/2),ty=16+v*16/max(1,ry);
  uint8_t a=coin_index(p.face,tx,ty);
  if(a){int level=lit;
   // A thin rim with scene-relative normal, never a baked highlight.
   int xx=tx-16,yy=ty-16,r2=xx*xx+yy*yy;
   if(r2>180)level=clamp(lit+(xx*lx+yy*ly)/(Q*6),0,11);
   put(fb,p.x+i,p.y+j,(uint8_t)(40+level*15+a-1));
  }else {
   int edge=st>=0?depth:-depth;
   int side_v=v-edge;
   if((side_v^v)<0)side_v=0; /* continuous projected side */
   a=coin_index(p.face,tx,16+side_v*16/max(1,ry));
   if(a){int level=clamp(3+(lx*u+ly*v)/(Q*6),0,11);put(fb,p.x+i,p.y+j,(uint8_t)(40+level*15+a-1));}
  }
 }
}


#include "proc_cloth.h"
static int cloth_wave(int pos,int side){
 return (sinq(pos*150+side*606)*100+sinq(pos*319+side*1108)*37+sinq(pos*62+side*1304)*23)/4096;
}
static int shade_cloth(int x,int y,const int16_t*wave_table){
 int dx=abs_i(x-92)-77,dy=abs_i(2*y-153)/2-61;
 int sd=max(dx,dy)-5;
 if(dx>0&&dy>0)sd+=min(dx,dy)*3/8;
 int side=0,edge=y-10;
 if(143-y<edge){side=1;edge=143-y;}
 if(x-10<edge){side=2;edge=x-10;}
 if(174-x<edge)side=3;
 int pos=side<2?x:y,q=max(0,sd);
 int wave=wave_table[side*224+16+pos+(sd>0?q/2:sd/5)];
 int corner=abs_i(abs_i(x-92)-82)<13&&abs_i(abs_i(2*y-153)/2-66)<13;
 if(corner)wave=wave*145/100;
 int outer=71+16*wave/100;
 int alpha=clamp((outer-sd*10)*6/10+2,0,4);
 int l;
 if(sd<=0){
  int idx=clamp(sd+16,0,16);
  l=110+rim_l[idx]+inner_l[idx]*wave/100;
 }else{
  int t=clamp(q*1000/max(outer,1),0,100);
  l=-90-110*t/100+drop_l[clamp(q,0,13)]+(70+130*t/100)*wave/100+(side==0||side==2?30:-40);
 }
 /* No alternating brightness: IPS quantization makes this visible. */
 unsigned value=clamp(l/10,-64,48)+64,i=cloth_offsets[alpha];
 while(value>=cloth_runs[i])i+=2;
 return alpha&&cloth_runs[i+1]==10?11:cloth_runs[i+1];
}
void scene_prepare_cloth(uint8_t*cache,int16_t*wave_table){
 for(int side=0;side<4;side++)for(int pos=-16;pos<208;pos++)wave_table[side*224+pos+16]=(int16_t)cloth_wave(pos,side);
 for(int y=0;y<154;y++)for(int x=0;x<185;x++)cache[y*185+x]=(uint8_t)shade_cloth(x,y,wave_table);
}
void scene_draw_right(const scene_state*s,uint32_t tick,uint8_t*fb,const uint8_t*cache){
 for(unsigned y=0;y<154;y++)for(unsigned x=0;x<185;x++)fb[(9+y)*320+123+x]=cache[y*185+x];
 if(!s->flow.session.count)return;
 uint32_t elapsed=tick-s->flow.started;
 int t=s->flow.phase==CF_FLYING?(int)((elapsed>1300?1300:elapsed)*Q/1300):Q;
 pose_t p[3];for(int i=0;i<3;i++){p[i]=pose(&s->path[i],i,t,(s->flow.last_mask>>i)&1);shadow(fb,p[i]);}
 for(int i=0;i<3;i++)for(int j=i+1;j<3;j++)if(p[j].h<p[i].h){pose_t tmp=p[i];p[i]=p[j];p[j]=tmp;}
 for(int i=0;i<3;i++)coin(fb,p[i]);
}


