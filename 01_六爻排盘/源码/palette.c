#include <stdint.h>
extern const uint8_t palette_small[165];
static unsigned even(unsigned n){unsigned q=n/1000,r=n%1000;return q+(r>500||(r==500&&(q&1)));}
void make_palette(uint8_t*out){
 for(unsigned i=0;i<256;i++){out[4*i+3]=255;for(unsigned k=0;k<3;k++)out[4*i+k]=0;}
 for(unsigned i=0;i<40;i++)for(unsigned k=0;k<3;k++)out[4*i+k]=palette_small[3*i+k];
 for(unsigned l=0;l<12;l++)for(unsigned i=0;i<15;i++)for(unsigned k=0;k<3;k++){
 unsigned v=even(palette_small[120+i*3+k]*(310+105*l)+(l>8?(l-8)*1000*(k==0?3:k==1?6:8):0));
 out[(40+l*15+i)*4+k]=v>255?255:v;
 }
 for(unsigned s=0;s<2;s++)for(unsigned i=0;i<16;i++)for(unsigned k=0;k<3;k++)
 out[(220+s*16+i)*4+k]=even(palette_small[(8+2*i)*3+k]*(s?720:430));
 out[682]=195;
}
