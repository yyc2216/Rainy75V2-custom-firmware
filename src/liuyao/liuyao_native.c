#include "liuyao_native.h"

/* No libc calls. Binary source table follows V41 checked layout exactly. */
static const uint8_t kDaysInMonth[12]={31,28,31,30,31,30,31,31,30,31,30,31};
static const uint8_t kTriByBits[8]={7,3,5,1,6,2,4,0};
static const uint8_t kPalaceElement[8]={3,3,1,0,0,4,2,2};
static const uint8_t kBranchElement[12]={4,2,0,0,2,1,1,2,3,3,2,4};
static const uint8_t kShi[8]={6,1,2,3,4,5,4,3};
static const uint8_t kYing[8]={3,4,5,6,1,2,1,6};
static const uint8_t kSpiritStart[10]={0,0,1,1,2,3,4,4,5,5};
static uint8_t leap(uint32_t y) {
    return (uint8_t)((y%4==0 && y%100!=0) || (y%400==0));
}
static uint8_t days_month(uint16_t year,uint8_t month) {
    return (uint8_t)(kDaysInMonth[month-1] + (month==2 && leap(year)));
}
static uint32_t u32le(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1]<<8) |
           ((uint32_t)p[2]<<16) | ((uint32_t)p[3]<<24);
}
static uint32_t jie_index(const ly_table_t*t,unsigned year,unsigned month){
 const uint8_t *p=t->data+LY_TABLE_JIE_OFFSET;
 unsigned bit=11*(year*12+month);const uint8_t*q=p+48+(bit>>3);
 uint32_t d=((q[0]|((uint32_t)q[1]<<8)|((uint32_t)q[2]<<16))>>(bit&7))&2047;
 return u32le(p+4*month)+year*31556926u+d;
}
int ly_check_table(const ly_table_t *t) {
    if (!t || !t->data || t->length!=LY_TABLE_SIZE)return LY_ERR_TABLE;
    const uint8_t *p=t->data;
    if(p[0]!='L'||p[1]!='Y'||p[2]!='4'||p[3]!='1'||
       p[4]!=24||p[5]!=45||p[6]!=64||p[7]!=8)return LY_ERR_TABLE;
    for(unsigned i=0;i<64;i++) {
        if(p[8+i]>=64 || p[72+i]<1 || p[72+i]>64)return LY_ERR_TABLE;
        if(p[184+i]>=143)return LY_ERR_TABLE;
    }
    for(unsigned i=0;i<48;i++) {
        if((p[136+i]>>4)>=10 || (p[136+i]&15)>=12)return LY_ERR_TABLE;
    }
    for(unsigned year=0;year<22;year++)
        for(unsigned k=1;k<12;k++)
            if(jie_index(t,year,k) <=
               jie_index(t,year,k-1))
                return LY_ERR_TABLE;
    return LY_OK;
}
const char *ly_hexagram_name(const ly_table_t *t,uint8_t kingwen) {
    if(ly_check_table(t)!=LY_OK || kingwen<1 || kingwen>64)return (const char*)0;
    uint16_t offset=t->data[184+(uint32_t)(kingwen-1)];
    return (const char*)(t->data+248+offset);
}
static uint32_t jie(const ly_table_t *t,uint16_t year,uint8_t m0) {
    return jie_index(t,year-2024,m0);
}
static uint8_t xun(uint8_t stem,uint8_t branch) {
    for(uint8_t x=0;x<60;x++)
        if(x%10==stem && x%12==branch)return (uint8_t)(x/10);
    return 255;
}
static uint8_t rel(uint8_t palace,uint8_t branch) {
    uint8_t mine=kPalaceElement[palace];
    uint8_t other=kBranchElement[branch];
    return (uint8_t)((other+5-mine)%5);
}
static uint8_t najia(const ly_table_t *t,uint8_t gua,uint8_t i) {
    uint8_t three=(i<3)?(gua&7):((gua>>3)&7);
    uint8_t tr=kTriByBits[three];
    return t->data[136+(uint32_t)tr*6+i];
}
static uint8_t marker(uint8_t role,uint8_t line_no) {
    if(kShi[role]==line_no)return 1;
    if(kYing[role]==line_no)return 2;
    return 0;
}
static int convert_civil(uint32_t sec,ly_result_t *out,uint32_t *days_out) {
    uint32_t day_count=sec/86400u;
    uint32_t year=2000,days=day_count;
    while(year<=2045) {
        unsigned d=365+leap(year);
        if(days<d)break;
        days-=d;year++;
    }
    if(year<2024 || year>2045)return LY_ERR_DATE;
    uint8_t month=1;
    for(;month<=12;month++) {
        uint8_t n=days_month((uint16_t)year,month);
        if(days<n)break;
        days-=n;
    }
    if(month>12)return LY_ERR_DATE;
    out->year=(uint16_t)year;
    out->month=month;
    out->day=(uint8_t)(days+1);
    uint32_t seconds_of_day=sec%86400u;
    out->hour=(uint8_t)(seconds_of_day/3600u);
    out->minute=(uint8_t)((seconds_of_day%3600u)/60u);
    out->second=(uint8_t)(seconds_of_day%60u);
    *days_out=day_count;
    return LY_OK;
}
static void pillar_fill(ly_pillar_t *p,uint8_t stem,uint8_t branch) {
    p->stem=stem;p->branch=branch;p->xun=xun(stem,branch);
}
static int calculate_four_pillars(const ly_table_t *t,uint32_t seconds,
                                  uint32_t days,ly_result_t *out) {
    uint16_t year=out->year;
    uint8_t hour=out->hour;
    uint8_t before_lichun=(uint8_t)(seconds<jie(t,year,1));
    unsigned cyc=(unsigned)((year-(before_lichun?1:0)-1984)%60);
    unsigned m_idx=0;
    if(seconds<jie(t,year,1)) {
        m_idx=(seconds<jie(t,year,0))?10:11;
    } else {
        for(uint8_t m=2;m<12;m++)
            if(seconds>=jie(t,year,m))m_idx=(unsigned)(m-1);
    }
    uint8_t year_s=(uint8_t)(cyc%10),year_b=(uint8_t)(cyc%12);
    uint8_t month_s=(uint8_t)(((year_s%5)*2+2+m_idx)%10);
    uint8_t month_b=(uint8_t)((2+m_idx)%12);
    uint8_t day_idx=(uint8_t)((54+days)%60);
    uint8_t hour_b=(hour==0 || hour==23)?0:(uint8_t)((hour+1)/2);
    uint8_t hour_s=(uint8_t)((day_idx%5*2+hour_b)%10);
    pillar_fill(&out->pillar[0],year_s,year_b);
    pillar_fill(&out->pillar[1],month_s,month_b);
    pillar_fill(&out->pillar[2],(uint8_t)(day_idx%10),(uint8_t)(day_idx%12));
    pillar_fill(&out->pillar[3],hour_s,hour_b);
    return LY_OK;
}
int ly_calculate(const ly_table_t *t,uint32_t sec,
                 const uint8_t yao[6],ly_result_t *out) {
    if(!out || !yao)return LY_ERR_INPUT;
    if(ly_check_table(t)!=LY_OK)return LY_ERR_TABLE;
    uint8_t mask=0,changed_mask=0,moving=0;
    for(uint8_t i=0;i<6;i++) {
        if(yao[i]<6 || yao[i]>9)return LY_ERR_INPUT;
        uint8_t yang=(uint8_t)(yao[i]==7 || yao[i]==9);
        uint8_t change=(uint8_t)(yao[i]==6 || yao[i]==9);
        if(yang)mask|=(uint8_t)(1u<<i);
        if(yang ^ change)changed_mask|=(uint8_t)(1u<<i);
        if(change)moving|=(uint8_t)(1u<<i);
    }
    uint32_t days=0;
    int ok=convert_civil(sec,out,&days);
    if(ok!=LY_OK)return ok;
    out->frozen_epoch=sec;
    out->original_mask=mask;out->changed_mask=changed_mask;
    out->moving_mask=moving;out->has_change=(uint8_t)(moving!=0);
    uint8_t origin=t->data[8+mask],changed=t->data[8+changed_mask];
    out->original_palace=(uint8_t)(origin>>3);
    out->original_role=(uint8_t)(origin&7);
    out->changed_palace=(uint8_t)(changed>>3);
    out->changed_role=(uint8_t)(changed&7);
    out->original_kingwen=t->data[72+mask];
    out->changed_kingwen=t->data[72+changed_mask];
    calculate_four_pillars(t,sec,days,out);
    uint8_t spirits=kSpiritStart[out->pillar[2].stem];
    uint8_t pure_trigram_bits=0;
    static const uint8_t kTriBits[8]={7,3,5,1,6,2,4,0};
    pure_trigram_bits=kTriBits[out->original_palace];
    uint8_t pure_gua=(uint8_t)(pure_trigram_bits|(pure_trigram_bits<<3));
    uint8_t relation_mask=0;
    for(uint8_t i=0;i<6;i++) {
        ly_line_t *line=out->line+i;
        line->original_najia=najia(t,mask,i);
        line->changed_najia=najia(t,changed_mask,i);
        line->original_relation=rel(out->original_palace,(uint8_t)(line->original_najia&15));
        line->changed_relation=rel(out->original_palace,(uint8_t)(line->changed_najia&15));
        relation_mask|=(uint8_t)(1u<<line->original_relation);
        line->original_marker=marker(out->original_role,(uint8_t)(i+1));
        line->changed_marker=marker(out->changed_role,(uint8_t)(i+1));
        line->original_yang=(uint8_t)((mask>>i)&1);
        line->changed_yang=(uint8_t)((changed_mask>>i)&1);
        line->moving=(uint8_t)((moving>>i)&1);
        line->spirit=(uint8_t)((spirits+i)%6);
        line->hidden_najia=0;
        line->hidden_relation=0;
        line->hidden_present=0;
    }
    for(uint8_t i=0;i<6;i++) {
        ly_line_t *line=out->line+i;
        uint8_t candidate=najia(t,pure_gua,i);
        uint8_t candidate_rel=rel(out->original_palace,(uint8_t)(candidate&15));
        if(!(relation_mask & (1u<<candidate_rel)) &&
           candidate_rel!=line->original_relation) {
            line->hidden_najia=candidate;
            line->hidden_relation=candidate_rel;
            line->hidden_present=1;
        }
    }
    return LY_OK;
}
void ly_session_reset(ly_session_t *s) {
    if(!s)return;
    s->frozen_epoch=0;s->valid_time=0;s->count=0;
    for(uint8_t i=0;i<6;i++)s->values[i]=0;
}
int ly_session_throw(ly_session_t *s,const uint8_t coins[3],
                     uint32_t now,int clock_valid) {
    if(!s || !coins)return LY_ERR_INPUT;
    if(s->count>=6)return LY_ERR_STATE;
    if(coins[0]>1 || coins[1]>1 || coins[2]>1)return LY_ERR_INPUT;
    if(s->count==0) {
        if(!clock_valid)return LY_ERR_CLOCK;
        s->frozen_epoch=now;
        s->valid_time=1;
    }
    s->values[s->count++]=(uint8_t)(6+coins[0]+coins[1]+coins[2]);
    return LY_OK;
}
int ly_session_finish(const ly_table_t *t,const ly_session_t *s,ly_result_t *out) {
    if(!s)return LY_ERR_INPUT;
    if(s->count!=6)return LY_ERR_STATE;
    if(!s->valid_time)return LY_ERR_CLOCK;
    return ly_calculate(t,s->frozen_epoch,s->values,out);
}

