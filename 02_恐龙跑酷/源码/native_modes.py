# -*- coding: utf-8 -*-
"""V19 add-on to exact V18: native, self-contained Chrome Dino third screen mode.
ONLY prepares candidate firmware and strict manifest; NEVER flashes USB/HID.
The sole source of changes is the V18 SHA-256 verified ROM plus original
upstream source sprites. Original boot header, scene0, scene1 and OEM assets stay.
"""
from pathlib import Path
import hashlib,struct,json,sys,re
ROOT=Path(__file__).resolve().parent
ASSET_ROOT=ROOT.parent/'V19_dino'  # Original downloaded sources shared read-only
PR=ROOT.parents[2]
sys.path.insert(0,str(PR/'reverse_tools'))
from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
BA=0x08004000
D=PR/'firmware_study/OFFLINE_DO_NOT_FLASH'
SRC=D/'ips_blink_V18_REAL_OEM_40ms_CHARGING_OFFLINE.bin'
B=SRC.read_bytes()
EXPECTED='61f5b824e3b66ecd10fef524e7c98b39545e399e2b52de7a4c58cac23824d416'
assert len(B)==502925 and hashlib.sha256(B).hexdigest()==EXPECTED
V18=json.loads((D/'V18_REAL_OEM_40ms_CHARGING_manifest.json').read_text(encoding='utf8'))
V14=json.loads((D/'V14_BATTERY_CLEAN_CHARGE_ANIMATION_manifest.json').read_text(encoding='utf8'))
assert V18['flash_cave_spare']==2528 and V14['resource_spare']==7261
FW=bytearray(B); P=[]
ks=Ks(KS_ARCH_ARM,KS_MODE_THUMB)
cs=Cs(CS_ARCH_ARM,CS_MODE_THUMB)
def asm(addr,source):
 # This Keystone build lacks UDIV encoding. Use a real four-byte Thumb NOP
 # placeholder (not .byte, because Keystone miscounts byte directives during
 # absolute BL relocation), then replace each placeholder with verified ARMv7M
 # Thumb2 UDIV T1 machine code after full source assembly.
 original=source
 lines=[];udivs=[]
 for line in source.splitlines():
  m=re.fullmatch(r'\s*udiv\s+r(\d+)\s*,\s*r(\d+)\s*,\s*r(\d+)\s*',line)
  if m:
   rd,rn,rm=map(int,m.groups())
   assert all(0<=x<=12 for x in (rd,rn,rm))
   udivs.append((rd,rn,rm))
   lines.append('nop.w')
  else:lines.append(line)
 source='\n'.join(lines)
 try: b=bytearray(ks.asm(source,addr=addr)[0])
 except Exception as e: raise RuntimeError(f'ASM_FAILED @ {addr:#x}\n{original}\n{e}')
 assert b and len(b)%2==0
 if udivs:
  placeholders=[i for i in cs.disasm(bytes(b),addr) if i.mnemonic=='nop.w']
  assert len(placeholders)==len(udivs),('UDIV PLACEHOLDER MISMATCH',addr,len(placeholders),len(udivs))
  for ins,(rd,rn,rm) in zip(placeholders,udivs):
   actual=struct.pack('<HH',0xfbb0|rn,0xf0f0|(rd<<8)|rm)
   decoded=list(cs.disasm(actual,ins.address))
   assert len(decoded)==1 and decoded[0].mnemonic=='udiv',decoded
   assert decoded[0].op_str==f'{["r"+str(rd) if rd<9 else "sb" if rd==9 else "sl" if rd==10 else "fp" if rd==11 else "ip"][0]}, {("r"+str(rn)) if rn<9 else "sb" if rn==9 else "sl" if rn==10 else "fp" if rn==11 else "ip"}, {("r"+str(rm)) if rm<9 else "sb" if rm==9 else "sl" if rm==10 else "fp" if rm==11 else "ip"}',decoded
   off=ins.address-addr
   assert bytes(b[off:off+4])==bytes(ks.asm('nop.w',addr=ins.address)[0])
   b[off:off+4]=actual
 return bytes(b)
def put(addr,data,why):
 o=addr-BA; z=o+len(data)
 assert 0<=o<z<=0x08080000-BA,(hex(addr),why)
 if z>len(FW):
  assert o>=len(B),('CANNOT_EXTEND_ROM_FOR_EXISTING_DATA',why)
  FW.extend(b'\xff'*(z-len(FW)))
 for lo,hi,name in P:assert z<=lo or o>=hi,('OVERLAP',name,why,hex(addr))
 FW[o:z]=data
 P.append((o,z,why))
def op(addr,original,mnemonic,payload,why):
 d=list(cs.disasm(B[addr-BA:addr-BA+len(original)],addr))
 assert B[addr-BA:addr-BA+len(original)]==original,(why,'unexpected original bytes')
 encoded=asm(addr,payload)
 assert len(encoded)==len(original),(why,'encoded_len',len(encoded),'expected',len(original),d)
 put(addr,encoded,why)
 return encoded
def align(n):return (n+3)&~3

# ORIGINAL upstream sprites, compact RLE palette indexes, 22 sprites.
manifest=json.loads((ASSET_ROOT/'dino_assets/sprites_native_manifest.json').read_text('utf8'))
raw=(ASSET_ROOT/'dino_assets/sprites_native.rle2').read_bytes()
assert len(raw)==3351 and manifest['sprite_count']==22
assert hashlib.sha256(raw).hexdigest()==manifest['payload_sha256']
## V18 LIVE charging animation reads the OEM 20%-battery source from
## 0x08023fa8, so the old proposed 'V14 resource spare' is NOT free flash.
## Place all V19-only resources strictly after the original V18 binary, below
## the end of the first 512 KiB flash bank (AT32F435 1024 KiB model).
RES_BEGIN=align(BA+len(B))
RES_END=0x08080000
assert RES_BEGIN==0x0807ec90
assert RES_END-RES_BEGIN>=len(raw)+22*12+20
rescur=RES_BEGIN
def add_resource(b,name):
 global rescur
 a=align(rescur); assert a+len(b)<=RES_END,(name,len(b),hex(a),hex(RES_END))
 put(a,b,name);rescur=a+len(b)
 return a
RLE_ADDR=add_resource(raw,'22_original_source_sprites_RLE_palette_indices')
table=[]
for item in manifest['items']:
 pal=item['palette']
 assert len(pal)<=4 and pal[0]==0xF81F
 # Map RGB565 original shade to the same V18 4-step monochrome LVGL palette.
 mapping=[]
 for color in pal:
  if color==0xF81F:mapping.append(255) # TRANSPARENT
  else:
   r=((color>>11)&31)*255//31; g=((color>>5)&63)*255//63;bl=(color&31)*255//31
   luma=(r*30+g*59+bl*11)//100
   mapping.append(min(3,max(0,(255-luma+42)//85)))
 mapping+= [255]*(4-len(mapping))
 table.append(struct.pack('<IHHBBBB',
  RLE_ADDR+item['offset'],item['w'],item['h'],*mapping))
 assert item['offset']+item['length']<=len(raw)
SPRITES=add_resource(b''.join(table),'22_sprite_pointer_geometry_and_palette_table')
assert len(table)==22
# digits 3x5; bit index row-major from MSB of 15-bit mask
rows=[
 ['111','101','101','101','111'], #0
 ['010','110','010','010','111'], #1
 ['111','001','111','100','111'], #2
 ['111','001','111','001','111'], #3
 ['101','101','111','001','001'], #4
 ['111','100','111','001','111'], #5
 ['111','100','111','101','111'], #6
 ['111','001','001','001','001'], #7
 ['111','101','111','101','111'], #8
 ['111','101','111','001','111'], #9
]
bits=[int(''.join(x),2) for x in rows]
FONT_ADDR=add_resource(struct.pack('<10H',*bits),'ten_numeric_glyphs_3x5')

CODE_END=0x801B0E0
CODE_BEGIN=CODE_END-V18['flash_cave_spare']
assert CODE_BEGIN==0x801a700
code_regions=[
 [CODE_BEGIN,CODE_END,CODE_BEGIN,'V18_original_verified_code_cave']]
current=0
CODE_SNIPS=[]
def add_code(name,source):
 global current
 for idx in range(current,len(code_regions)):
  begin,end,cur,label=code_regions[idx]
  at=align(cur)
  b=asm(at,source)
  if at+len(b)<=end:
   put(at,b,'ARM_Thumb_'+name)
   CODE_SNIPS.append((name,at,source,b))
   code_regions[idx][2]=at+len(b);current=idx
   print('ARM',name,hex(at),'BYTES',len(b),label,flush=True)
   return at
 raise RuntimeError(f'INSUFFICIENT_ROM_FOR_{name}: '+str([(hex(x[2]),hex(x[1]))for x in code_regions]))

# State in a private extension to V18's own image-buffer allocation.
S=0x3c10; MAGIC=0x44494e4f
PHASE=4; SCORE=8; HI=12; OX=16; TYPE=20; Y=24; VEL=28; SPEED=32
TICKS=36; LAST=40; RNG=44; JUMP=48; DUCK=52; CLOUDX=56; CLOUDY=60; BIRDY=64
FRAME=68; GROUND=72; ACTIVE=76; GROUP=80; BLINKUNTIL=84
GAME_ROOT=88; GAME_IMAGE=92; RELEASED=96; UP_HELD=100
LAST_VISIBLE_MODE=104; REFRESH_ON_RETURN=108
TOTAL=align(S+112)
assert TOTAL==15488
# Existing V18 allocation is exactly 15376B; increase only on scene setup.
original=B[0x8019e6e-BA:0x8019e72-BA]
assert len(original)==4 and list(cs.disasm(original,0x8019e6e))[0].mnemonic=='movw'
op(0x8019e6e,original,'movw',f'movw r0,#{TOTAL}','extend V18 private image allocation by 112 bytes')
# Third mode maps to the same native type0 scene manager (without introducing
# a new LVGL root or touching the original types 0/1 and deletion logic).
assert B[0x805b3f3-BA]==2
put(0x805b3f3,b'\x00','S1_slot2_native_type0_mode_instead_of_deleted_wallpaper')

# Pixel primitives: r0 pointer to 2bpp screen pixels, r1 x, r2 y, r3 index 0..3.
pixel=add_code('paint_one_indexed2_pixel_checked',r"""
cmp r1,#0
blt px_done
cmp.w r1,#320
bhs px_done
cmp r2,#0
blt px_done
cmp.w r2,#172
bhs px_done
add.w r12,r2,r2,lsl #2
lsl.w r12,r12,#6
add r12,r1
lsr.w r12,r12,#2
add r0,r12
and r1,r1,#3
rsb r1,r1,#3
lsls r1,r1,#1
ldrb r2,[r0]
movs r12,#3
lsl.w r12,r12,r1
bic.w r2,r2,r12
lsl.w r3,r3,r1
orr.w r2,r2,r3
strb r2,[r0]
px_done:
bx lr
""")

# RLE sprite compositing, uses original 22 sprite masks exactly.
sprite=add_code('draw_original_sprite_RLE_checked',f"""
push {{r4,r5,r6,r7,r8,r9,r10,r11,lr}}
sub sp,#4
mov r4,r0
mov r5,r1
mov r6,r2
movw r12,#12
mul r3,r3,r12
ldr r7,={hex(SPRITES)}
add r7,r3
ldr r8,[r7]
ldrh r9,[r7,#4]
ldrh r10,[r7,#6]
ldr r11,[r7,#8]
movs r7,#0
movs r3,#0
sprite_run:
ldrb r12,[r8],#1
mov r0,r12
lsrs r0,#6
lsls r0,#3
lsr.w r0,r11,r0
uxtb r0,r0
str r0,[sp]
mov r0,r12
and r0,#63
adds r0,#1
sprite_pixel:
ldr r12,[sp]
cmp r12,#255
beq sprite_advance
push {{r0,r1,r2,r3}}
mov r0,r4
add r1,r5,r7
add r2,r6,r3
ldr r3,[sp,#16]
bl 0x{pixel:x}
pop {{r0,r1,r2,r3}}
sprite_advance:
adds r7,#1
cmp r7,r9
blo sprite_next
movs r7,#0
adds r3,#1
cmp r3,r10
bhs sprite_end
sprite_next:
subs r0,#1
bne sprite_pixel
b sprite_run
sprite_end:
add sp,#4
pop {{r4,r5,r6,r7,r8,r9,r10,r11,pc}}
""")
# NOTE: color is stored at [sp] before inner push, so at [sp,#16] inside push.
# 3x5 digits, drawn with the same pixel primitive and no duplicate renderer.
digit=add_code('draw_four_score_digits',f"""
push {{r4,r5,r6,r7,r8,r9,r10,r11,lr}}
sub sp,#4
mov r4,r0
mov r5,r1
mov r6,r2
mov r7,r3
movw r8,#3
movw r10,#10
digits_loop:
udiv r9,r7,r10
mls r11,r9,r10,r7
mov r7,r9
ldr r12,={hex(FONT_ADDR)}
add.w r12,r12,r11,lsl #1
ldrh r11,[r12]
movw r9,#0
digits_bitloop:
movw r12,#14
sub.w r12,r12,r9
lsr.w r0,r11,r12
tst r0,#1
beq digits_nextbit
push {{r7,r8,r9,r10,r11}}
sub sp,#12
movw r12,#3
udiv r1,r9,r12
mls r0,r1,r12,r9
mov r3,r8
movw r12,#8
mul r3,r3,r12
add.w r2,r6,r1,lsl #1
add r1,r5,r3
add.w r1,r1,r0,lsl #1
str r1,[sp]
str r2,[sp,#4]
mov r0,r4
movs r3,#3
bl 0x{pixel:x}
ldr r1,[sp]
adds r1,#1
ldr r2,[sp,#4]
mov r0,r4
movs r3,#3
bl 0x{pixel:x}
ldr r1,[sp]
ldr r2,[sp,#4]
adds r2,#1
mov r0,r4
movs r3,#3
bl 0x{pixel:x}
ldr r1,[sp]
adds r1,#1
ldr r2,[sp,#4]
adds r2,#1
mov r0,r4
movs r3,#3
bl 0x{pixel:x}
add sp,#12
pop {{r7,r8,r9,r10,r11}}
digits_nextbit:
add.w r9,r9,#1
cmp r9,#15
blo digits_bitloop
subs.w r8,r8,#1
bpl digits_loop
add sp,#4
pop {{r4,r5,r6,r7,r8,r9,r10,r11,pc}}
""")

# Shared obstacle spawn: shape + group + bird altitude + independent
# randomized interval. Also used for first spawn and after restart.
spawn=add_code('random_obstacle_shape_group_height_and_safe_gap',f"""
push {{r4,r5,r6,r7,r8,lr}}
mov r4,r0
ldr r5,[r4,#{RNG}]
eor.w r5,r5,r5,lsl #13
eor.w r5,r5,r5,lsr #17
eor.w r5,r5,r5,lsl #5
str r5,[r4,#{RNG}]
movw r7,#12
udiv r8,r5,r7
mls r6,r8,r7,r5
add r6,#6
ldr r7,[r4,#{SCORE}]
cmp r7,#1200
blo spawn_cactus
and r7,r5,#7
cmp r7,#0
bne spawn_cactus
movs r6,#20
spawn_cactus:
cmp r6,#16
bne spawn_shape_allowed
ldr r7,[r4,#{SPEED}]
cmp r7,#5
bhs spawn_shape_allowed
movs r6,#12
spawn_shape_allowed:
str r6,[r4,#{TYPE}]
movs r8,#1
cmp r6,#20
beq spawn_group_done
ldr r7,[r4,#{SPEED}]
cmp r6,#12
blo spawn_maybe_double
cmp r7,#8
blo spawn_group_done
cmp r6,#16
beq spawn_group_done
spawn_maybe_double:
cmp r7,#6
blo spawn_group_done
lsrs r8,r5,#12
and r8,#3
cmp r8,#0
bne spawn_single
movs r8,#2
b spawn_group_done
spawn_single:
movs r8,#1
spawn_group_done:
str r8,[r4,#{GROUP}]
cmp r6,#20
bne spawn_choose_gap
lsrs r7,r5,#8
and r7,#3
movw r8,#50
cmp r7,#1
blo spawn_bird_height_ready
movw r8,#70
cmp r7,#2
blo spawn_bird_height_ready
movw r8,#90
spawn_bird_height_ready:
str r8,[r4,#{BIRDY}]
spawn_choose_gap:
eor.w r5,r5,r5,lsl #13
eor.w r5,r5,r5,lsr #17
eor.w r5,r5,r5,lsl #5
str r5,[r4,#{RNG}]
movw r7,#180
udiv r8,r5,r7
mls r6,r8,r7,r5
ldr r7,[r4,#{SPEED}]
movs r8,#24
mul r7,r7,r8
add.w r6,r6,#300
add r6,r7
str r6,[r4,#{OX}]
pop {{r4,r5,r6,r7,r8,pc}}
""")

# Reset new round without discarding highscore. State pointer r0.
reset=add_code('reset_game_round_without_losing_highscore',f"""
push {{r4,lr}}
mov r4,r0
movs r1,#1
str r1,[r4,#{PHASE}]
movs r1,#0
str r1,[r4,#{SCORE}]
str r1,[r4,#{VEL}]
str r1,[r4,#{JUMP}]
str r1,[r4,#{DUCK}]
str r1,[r4,#{TICKS}]
str r1,[r4,#{FRAME}]
str r1,[r4,#{GROUND}]
str r1,[r4,#{BLINKUNTIL}]
str r1,[r4,#{RELEASED}]
str r1,[r4,#{UP_HELD}]
movs r1,#1
str r1,[r4,#{GROUP}]
movw r1,#470
str r1,[r4,#{OX}]
movs r1,#6
str r1,[r4,#{TYPE}]
movw r1,#150
str r1,[r4,#{Y}]
movs r1,#4
str r1,[r4,#{SPEED}]
movw r1,#360
str r1,[r4,#{CLOUDX}]
movs r1,#40
str r1,[r4,#{CLOUDY}]
movs r1,#70
str r1,[r4,#{BIRDY}]
mov r0,r4
ldr r12,={hex(spawn|1)}
blx r12
pop {{r4,pc}}
""")

# OEM native packet type 0x15 sends 16-bit USB HID usage code (confirmed from
# ROM 0x805B440 and the OEM typing handler 0x805C4AC). 0x52 Up, 0x51 Down,
# 0x2C Space; 0x28 is ENTER and 0x20 is number 3, so neither is a game key.
gamekey=add_code('native_IPS_keycode_to_jump_crouch_restart',f"""
push {{r4,r5,r6,lr}}
mov r4,r0
mov r5,r1
ldr r0,[r5]
ldr r1,={hex(MAGIC)}
cmp r0,r1
bne key_done
ldr r0,[r5,#{ACTIVE}]
cmp r0,#1
bne key_done
cmp r4,#0
beq key_release
cmn r4,#1
beq key_release
cmp r4,#0x51
beq duck_key
cmp r4,#0x52
beq action_key
b key_done
key_release:
ldr r0,[r5,#{UP_HELD}]
cmp r0,#1
bne key_done
movs r0,#0
str r0,[r5,#{UP_HELD}]
movs r0,#1
str r0,[r5,#{RELEASED}]
b key_done
duck_key:
movs r0,#0
str r0,[r5,#{UP_HELD}]
bl 0x0803a2ba
add.w r0,r0,#320
str r0,[r5,#{DUCK}]
b key_done
action_key:
ldr r0,[r5,#{PHASE}]
cmp r0,#1
beq queue_jump
mov r0,r5
bl 0x{reset:x}
b key_done
queue_jump:
movs r0,#0
str r0,[r5,#{RELEASED}]
movs r0,#1
str r0,[r5,#{UP_HELD}]
str r0,[r5,#{JUMP}]
key_done:
pop {{r4,r5,r6,pc}}
""")

# Actual game update: fixed 40ms clock (not one physics step per arbitrary
# CPU cycle); score, gravity/jump, stochastic obstacle choice, collisions,
# clouds, speed-up, game over, local highscore.
step=add_code('native_fixed_40ms_game_physics_and_collision',f"""
push {{r4,r5,r6,r7,r8,r9,r10,lr}}
mov r4,r0
ldr r5,[r4,#{PHASE}]
cmp r5,#1
bne no_simulation
ldr r5,[r4,#{TICKS}]
adds r5,#1
str r5,[r4,#{TICKS}]
movw r6,#125
udiv r7,r5,r6
mls r6,r7,r6,r5
cmp r6,#0
bne keep_speed
ldr r6,[r4,#{SPEED}]
adds r6,#1
cmp r6,#10
bls cap_speed_ok
movs r6,#10
cap_speed_ok:
str r6,[r4,#{SPEED}]
keep_speed:
ldr r6,[r4,#{SCORE}]
adds r6,#2
str r6,[r4,#{SCORE}]
ldr r7,[r4,#{JUMP}]
cbz r7,check_falling
movs r0,#0
str r0,[r4,#{JUMP}]
ldr r7,[r4,#{Y}]
cmp r7,#150
bne check_falling
mvn r7,#13
str r7,[r4,#{VEL}]
check_falling:
ldr r6,[r4,#{VEL}]
adds r6,#1
ldr r7,[r4,#{Y}]
add r7,r6
cmp r7,#150
ble vertical_ok
movw r7,#150
movs r6,#0
vertical_ok:
str r6,[r4,#{VEL}]
str r7,[r4,#{Y}]
ldr r0,[r4,#{RELEASED}]
cmp r0,#1
bne jump_cut_done
cmp r7,#119
bgt jump_cut_done
cmn r6,#5
bge jump_cut_done
mvn r6,#4
str r6,[r4,#{VEL}]
jump_cut_done:
ldr r5,[r4,#{SPEED}]
ldr r7,[r4,#{GROUND}]
subs r7,r7,r5
movw r8,#1200
cmn r7,r8
bgt ground_still_scrolling
movs r7,#0
ground_still_scrolling:
str r7,[r4,#{GROUND}]
ldr r6,[r4,#{OX}]
subs r6,r6,r5
str r6,[r4,#{OX}]
cmn r6,#65
bge obstacle_ready
mov r0,r4
ldr r12,={hex(spawn|1)}
blx r12
obstacle_ready:
ldr r5,[r4,#{CLOUDX}]
subs r5,#2
cmn r5,#48
bge cloud_ready
movw r5,#320
ldr r6,[r4,#{RNG}]
ldr r8,[r4,#{TICKS}]
eor.w r6,r6,r8,lsl #2
and r8,r6,#31
add r5,r8
lsrs r6,r6,#5
and r6,r6,#63
add.w r6,r6,#15
str r6,[r4,#{CLOUDY}]
cloud_ready:
str r5,[r4,#{CLOUDX}]
ldr r5,[r4,#{OX}]
cmp r5,#80
bgt no_simulation
ldr r6,[r4,#{TYPE}]
cmp r6,#20
beq collision_bird
cmp r6,#18
blo collision_cactus
b no_simulation
collision_cactus:
cmp r6,#12
blo small_cactus
movs r7,#24
movw r8,#50
# Original cactus_big_5 is a 51px-wide triple cactus, not 24px.
cmp r6,#16
bne collision_horizontal
movs r7,#51
b collision_horizontal
small_cactus:
movs r7,#17
movw r8,#35
collision_horizontal:
ldr r10,[r4,#{GROUP}]
cmp r10,#2
bne single_cactus
add.w r7,r7,#21
single_cactus:
add r7,r5
cmp r7,#45
blt no_simulation
ldr r6,[r4,#{Y}]
rsb r8,r8,#155
cmp r6,r8
ble no_simulation
b collision_hit
collision_bird:
# Ducking at ground level reduces the effective dinosaur hitbox for birds.
ldr r7,[r4,#{DUCK}]
cmp r7,#0
beq bird_standing_collision
ldr r12,=0x0803a2bb
blx r12
cmp r0,r7
bhs bird_standing_collision
ldr r7,[r4,#{Y}]
cmp r7,#150
beq no_simulation
bird_standing_collision:
add.w r6,r5,#46
cmp r6,#45
blt no_simulation
ldr r6,[r4,#{Y}]
ldr r7,[r4,#{BIRDY}]
adds r7,#5
cmp r6,r7
ble no_simulation
ldr r7,[r4,#{BIRDY}]
add.w r7,r7,#31
sub.w r6,r6,#42
cmp r6,r7
bge no_simulation
collision_hit:
movs r0,#2
str r0,[r4,#{PHASE}]
ldr r0,[r4,#{SCORE}]
movs r5,#10
udiv r0,r0,r5
ldr r1,[r4,#{HI}]
cmp r0,r1
bls no_simulation
str r0,[r4,#{HI}]
no_simulation:
pop {{r4,r5,r6,r7,r8,r9,r10,pc}}
""")

# Present original sprites, ground, dynamic cloud and current obstacle in
# reusable full-screen indexed2 LVGL buffer, no approximate re-drawing of art.
render=add_code('native_320x172_game_render_in_original_V18_canvas',f"""
push {{r4,r5,r6,r7,r8,r9,r10,lr}}
mov r4,r0
mov r5,r1
add.w r6,r4,#0xa0
mov r7,r6
movw r8,#3440
movs r9,#0
clear_screen_indexed2:
str r9,[r7],#4
subs r8,#1
bne clear_screen_indexed2
mov r0,r6
ldr r1,[r5,#{GROUND}]
movw r2,#144
movs r3,#19
bl 0x{sprite:x}
ldr r1,[r5,#{GROUND}]
movw r7,#880
cmn r1,r7
bge skip_ground_second
add.w r1,r1,#1200
mov r0,r6
movw r2,#144
movs r3,#19
bl 0x{sprite:x}
skip_ground_second:
ldr r1,[r5,#{CLOUDX}]
mov r0,r6
ldr r2,[r5,#{CLOUDY}]
movs r3,#18
bl 0x{sprite:x}
ldr r1,[r5,#{OX}]
ldr r3,[r5,#{TYPE}]
movs r2,#115
cmp r3,#12
blo obs_draw
movs r2,#100
cmp r3,#20
bne obs_draw
ldr r2,[r5,#{BIRDY}]
ldr r0,[r5,#{TICKS}]
lsrs r0,#2
tst r0,#1
beq obs_draw
movs r3,#21
obs_draw:
mov r0,r6
bl 0x{sprite:x}
ldr r7,[r5,#{GROUP}]
cmp r7,#2
bne obstacle_group_done
ldr r1,[r5,#{OX}]
add.w r1,r1,#21
mov r0,r6
movw r2,#115
ldr r3,[r5,#{TYPE}]
bl 0x{sprite:x}
obstacle_group_done:
ldr r7,[r5,#{PHASE}]
ldr r2,[r5,#{Y}]
cmp r7,#2
bne not_dead
movs r3,#3
b dino_sprite
not_dead:
movs r3,#0
ldr r0,[r5,#{TICKS}]
movs r7,#3
udiv r8,r0,r7
udiv r9,r8,r7
mls r3,r9,r7,r8
ldr r7,[r5,#{DUCK}]
cbz r7,dino_sprite
bl 0x0803a2ba
cmp r0,r7
bhs dino_sprite
ldr r7,[r5,#{Y}]
cmp r7,#150
bne dino_sprite
movs r3,#4
ldr r0,[r5,#{TICKS}]
tst r0,#4
beq dino_sprite
movs r3,#5
dino_sprite:
# The real OEM millisecond clock at 0x0803A2BA overwrites R2 using LDR.
# Reacquire the foot Y coordinate before sprite positioning.
ldr r2,[r5,#{Y}]
adds r2,#1
cmp r3,#4
blo dino_standing
sub r2,#30
b draw_dino
dino_standing:
sub r2,#47
draw_dino:
mov r0,r6
movs r1,#40
bl 0x{sprite:x}
ldr r0,[r5,#{SCORE}]
movs r7,#10
udiv r3,r0,r7
mov r0,r6
movw r1,#284
movs r2,#12
bl 0x{digit:x}
ldr r3,[r5,#{HI}]
mov r0,r6
movw r1,#244
movs r2,#12
bl 0x{digit:x}
pop {{r4,r5,r6,r7,r8,r9,r10,pc}}
""")

# Hide/show the same four V18 icon LVGL objects in a common loop.
# r0= private alloc; r1=show 0 or 1.
icon_toggle=add_code('toggle_existing_four_V18_status_icons',f"""
push {{r4,r5,r6,r7,lr}}
sub sp,#4
mov r4,r0
mov r5,r1
movs r6,#4
movw r7,#120
icon_loop:
ldr r0,[r4,r7]
cbz r0,icon_next
movs r1,#1
cmp r5,#0
beq icon_hide
bl 0x802cda6
b icon_next
icon_hide:
bl 0x802cd1c
icon_next:
adds r7,#4
subs r6,#1
bne icon_loop
add sp,#4
pop {{r4,r5,r6,r7,pc}}
""")

# Unlike V19/V20/V21, mode2 owns a SEPARATE LVGL native screen, with one
# image child. It never steals the V18 blink screen's image source. Reuse the
# same OEM lv_obj_create/lv_img_create/lv_img_set_src/lv_scr_load functions.
# r0: game state pointer, which stores both LVGL pointers after initialization.
ensure_active_root=add_code('ensure_dedicated_game_screen_and_image',f"""
push {{r4,r5,r6,lr}}
mov r4,r0
ldr r5,[r4,#{GAME_ROOT}]
cbnz r5,game_have_root
movs r0,#0
bl 0x802cd06
mov r5,r0
cbz r5,game_screen_done
str r5,[r4,#{GAME_ROOT}]
mov r0,r5
movw r1,#0xffff
movs r2,#0
bl 0x8036c64
mov r0,r5
movs r1,#0xff
movs r2,#0
bl 0x8036c7e
game_have_root:
ldr r6,[r4,#{GAME_IMAGE}]
cbnz r6,game_have_image
mov r0,r5
bl 0x805c5b6
mov r6,r0
cbz r6,game_screen_done
str r6,[r4,#{GAME_IMAGE}]
mov r0,r6
movw r1,#{S}
sub r1,r4,r1
bl 0x805c5cc
mov r0,r6
movs r1,#9
bl 0x802fa78
mov r0,r6
movs r1,#0
bl 0x802f244
mov r0,r6
movs r1,#0
bl 0x802f274
game_have_image:
bl 0x802a7f0
cbz r0,game_screen_done
ldr r1,[r0,#0x10]
cmp r1,r5
beq game_screen_done
mov r0,r5
bl 0x802b0e0
game_screen_done:
pop {{r4,r5,r6,pc}}
""")

# V21 tick path; when mode is not 2, delegates to V18's existing exact
# blink and OEM charging path (0x8019f68) unchanged.
tick=add_code('V29_game_mode_with_stock_lvgl_scheduler_once_per_main_loop',f"""
push {{r4,r5,r6,r7,lr}}
sub sp,#4
ldr r4,=0x2003eda0
ldrb r0,[r4,#0x12]
mov r7,r0
bl 0x8019cf0
mov r5,r0
cmp r5,#0
beq.w delegate_v18_no_state
movw r6,#{S}
add r6,r5
# Remember the last active mode so a return to mode0 refreshes cached OEM
# connection/battery immediately, rather than waiting for a new status packet.
ldr r0,[r6,#{LAST_VISIBLE_MODE}]
cmp r0,r7
beq tracked_current_mode
str r7,[r6,#{LAST_VISIBLE_MODE}]
cmp r7,#0
bne tracked_current_mode
movs r0,#1
str r0,[r6,#{REFRESH_ON_RETURN}]
tracked_current_mode:
cmp r7,#2
bne not_dino_screen
# This is the actual OEM LVGL task handler displaced by V18 main-loop hook.
# V18 calls it inside 0x8019f68 for modes0/1; the custom mode2 path MUST
# call it once, or the LCD flush pipeline never executes during gameplay.
bl 0x802dca8
ldr r1,[r6]
ldr r0,={hex(MAGIC)}
cmp r1,r0
beq magic_good
movs r0,#0
str r0,[r6,#{HI}]
str r0,[r6,#{ACTIVE}]
str r0,[r6,#{GAME_ROOT}]
str r0,[r6,#{GAME_IMAGE}]
ldr r0,={hex(MAGIC)}
str r0,[r6]
magic_good:
mov r0,r6
bl 0x{ensure_active_root:x}
ldr r0,[r6,#{GAME_IMAGE}]
cmp r0,#0
beq.w delegate_v18
ldr r0,[r6,#{ACTIVE}]
cmp r0,#1
beq game_active
mov r0,r6
bl 0x{reset:x}
movs r0,#0
str r0,[r6,#{PHASE}]
movs r0,#1
str r0,[r6,#{ACTIVE}]
mov r0,r5
movs r1,#0
bl 0x{icon_toggle:x}
bl 0x0803a2ba
str r0,[r6,#{LAST}]
movw r1,#0x5a5a
eor.w r0,r0,r1
orr.w r0,r0,#1
str r0,[r6,#{RNG}]
mov r0,r6
ldr r12,={hex(spawn|1)}
blx r12
b draw_game_frame
game_active:
bl 0x0803a2ba
mov r7,r0
ldr r0,[r6,#{LAST}]
subs r0,r7,r0
cmp r0,#40
blo tick_exit
str r7,[r6,#{LAST}]
mov r0,r6
bl 0x{step:x}
draw_game_frame:
mov r0,r5
mov r1,r6
bl 0x{render:x}
ldr r0,[r6,#{GAME_IMAGE}]
cbz r0,tick_exit
ldr r1,[r6,#{FRAME}]
adds r1,#1
cmp r1,#9
bls frame_in_range
movs r1,#0
frame_in_range:
str r1,[r6,#{FRAME}]
movs r2,#12
mul r1,r1,r2
add r1,r5
bl 0x805c5cc
b tick_exit
not_dino_screen:
ldr r0,[r6]
ldr r1,={hex(MAGIC)}
cmp r0,r1
bne delegate_v18
ldr r0,[r6,#{ACTIVE}]
cmp r0,#0
beq delegate_v18
movs r0,#0
str r0,[r6,#{ACTIVE}]
mov r0,r5
movs r1,#0
bl 0x8019dcc
movs r0,#0
strb r0,[r5,#0x88]
ldr r0,=0x2004c9bc
ldr r0,[r0,#0x0c]
cbz r0,restore_icons
mov r1,r5
bl 0x805c5cc
restore_icons:
mov r0,r5
movs r1,#1
bl 0x{icon_toggle:x}
delegate_v18:
# The stock status parser continuously updates mode bytes even while mode0
# is hidden. Force the exact ORIGINAL V18 decoder only ONCE on returning to
# mode0, after any previously hidden OEM icons have been made visible.
cmp r7,#0
bne delegate_v18_no_state
ldr r0,[r6,#{REFRESH_ON_RETURN}]
cbz r0,delegate_v18_no_state
movs r0,#0
str r0,[r6,#{REFRESH_ON_RETURN}]
bl 0x8019d38
delegate_v18_no_state:
bl 0x8019f68
tick_exit:
add sp,#4
pop {{r4,r5,r6,r7,pc}}
""")

keyhook=add_code('V29_original_keyboard_dispatch_preserving_non_game_keys',f"""
push {{r4,r5,lr}}
ldr r5,=0x2003eda0
ldrb r1,[r5,#0x12]
cmp r1,#2
bne original_key_continue
sub sp,#4
mov r4,r0
bl 0x8019cf0
cbz r0,v19_key_exit
movw r1,#{S}
add r1,r0
mov r0,r4
bl 0x{gamekey:x}
v19_key_exit:
add sp,#4
pop {{r4,r5,pc}}
original_key_continue:
b.w 0x805ac78
""")

# Strong exact hook assertions. The original entrance push+load instruction
# sequence is replaced with B.W trampoline + nop, preserving original
# prologue semantics on mode0/1, including the same saved registers.
key_entry=0x805ac72
oldkey=B[key_entry-BA:key_entry-BA+6]
assert oldkey.hex()=='30b5dff8e056'
op(key_entry,oldkey,'B.W',f'b.w 0x{keyhook:x}\nnop','redirect_original_key_entry_only_for_native_mode2')
tick_site=0x807a73e
oldtick=B[tick_site-BA:tick_site-BA+4]
ins=next(cs.disasm(oldtick,tick_site))
assert ins.mnemonic=='bl' and ins.op_str=='#0x8019f68'
op(tick_site,oldtick,'BL',f'bl 0x{tick:x}','mode_aware_tick_V18_unchanged_for_modes_0_and_1')
# OEM V18 status packet still checks SAVED mode at MODE+0x0D even after
# the native screen manager has made MODE+0x12 current. Thus game->blink leaves
# four original OEM icons stale. Switch this SINGLE preexisting gate to the
# real CURRENT mode; do not redraw or replace any factory sprites.
refresh_gate=0x08019D3E
oldgate=B[refresh_gate-BA:refresh_gate-BA+2]
assert list(cs.disasm(oldgate,refresh_gate))[0].op_str=='r0, [r4, #0xd]'
op(refresh_gate,oldgate,'LDRB', 'ldrb r0,[r4,#0x12]', 'V29_OEM_battery_connection_refresh_uses_current_visible_mode')
# The real V18 nine-frame charging function at 0x0801A604 ALSO checks
# SAVED mode. Change only the mode guard. The unused legacy
# charging routine remains untouched. Fix icon, blink and charging guards.
for guard,base_reg,why in (
 (0x08019F76,'r7','original_blink_animation'),
 (0x0801A60A,'r4','real_V18_nine_frame_charging_animation')):
 before=B[guard-BA:guard-BA+2]
 code=list(cs.disasm(before,guard))
 assert len(code)==1 and code[0].mnemonic=='ldrb'
 assert code[0].op_str==f'r0, [{base_reg}, #0xd]'
 op(guard,before,'LDRB',f'ldrb r0,[{base_reg},#0x12]',
    'V29_V18_'+why+'_uses_current_visible_mode')
assert FW[:256]==B[:256]
assert len(FW)>len(B) and BA+len(FW)<=RES_END
assert (len(FW)+511)//512*512<=RES_END-BA
assert FW[0x8023fa8-BA:0x8025c05-BA]==B[0x8023fa8-BA:0x8025c05-BA], 'ORIGINAL_V18_CHARGING_PIXELS_OVERWRITTEN'
# Independent exact diff whitelist including appended flash bytes.
actual={i for i in range(len(FW)) if FW[i]!=(B[i] if i<len(B) else 0xff)}
allow=set()
for lo,hi,name in P:allow.update(range(lo,hi))
assert actual<=allow and all(lo>=256 for lo in actual)
assert FW[0x8050000-BA:0x805ac72-BA]==B[0x8050000-BA:0x805ac72-BA]
assert FW[0x805ac78-BA:0x805b3f3-BA]==B[0x805ac78-BA:0x805b3f3-BA]
assert FW[0x805b3f4-BA:0x8069000-BA]==B[0x805b3f4-BA:0x8069000-BA]
assert FW[0x805b3f3-BA]==0
assert FW[0x805b3f4-BA]==1
report=dict(version='V29_OEM_ICONS_CORRECT_AND_CLEAN_DINO',
 base_v18_sha256=EXPECTED,version_written_to_hardware=False,validated_by_unicorn=False,
 source='pablosguajardo/esp32-chrome-dino-game',
 sprite_count=22,source_sprite_pixels=42316,sprite_rle_bytes=len(raw),
 image_buffer_bytes=TOTAL,immediate_status_on_mode0_return=True,game_state_offset=hex(S),model='mode2_dedicated_native_lvgl_screen_and_image_with_stock_API_reuse',
 screen_width=320,screen_height=172,engine_timestep_ms=40,
 flash_regions=[dict(name=x[3],start=hex(x[0]),end=hex(x[1]),used=x[2]-x[0],free=x[1]-x[2]) for x in code_regions],
 source_unchanged_v18_icon_and_blink_except_explicit_hooks=True,
 original_oem_asset_source_unmodified=True,icon_connection_refresh_follows_active_mode=True,
 v18_status_refresh_gate_patch='0x08019D3E',
 v18_real_charging_mode_gate_patch='0x0801A60A',v18_blink_mode_gate_patch='0x08019F76',
 source_unchanged_keyboard_maincore_and_receiver=True,
 original_v18_image_bytes=len(B),new_v28_image_bytes=len(FW),
 original_v18_battery_assets_preserved=True,
 appended_assets_range=[hex(RES_BEGIN),hex(rescur)],
 max_first_bank_end=hex(RES_END),
 screen_ownership_check=hex(ensure_active_root),oem_lvgl_scheduler_call='0x0802DCA8',
 verified_scheduler_integration='V18_scheduler_in_delegate_plus_native_scheduler_in_game_mode',
 active_mode_source='0x2003EDA0+0x12',saved_mode_source='0x2003EDA0+0x0D',
 icon_refresh_mode_source='0x2003EDA0+0x12',
 input_trace_overlay_enabled=False,
 jump_key_HID='0x52_UP',duck_key_HID='0x51_DOWN',space_key_HID='0x2C_DISABLED',jump_velocity=-14,gravity_per_tick=1,score_digit_scale=2,visible_ground_line_y=148,random_first_obstacle=True,random_gap_range=[300,479],maximum_speed=10,release_sentinel_codes=[0,65535],release_event_proven_on_hardware=False,
 raw_keycode_path='0x805ac72',key_trampoline=hex(keyhook),tick_dispatch=hex(tick),
 routines=dict(pixel=hex(pixel),sprite=hex(sprite),digit=hex(digit),reset=hex(reset),
  gamekey=hex(gamekey),step=hex(step),render=hex(render),icon_toggle=hex(icon_toggle)),
 modifications=[dict(address=hex(BA+lo),end=hex(BA+hi),why=why)for lo,hi,why in P],
 changed_bytes=len(actual),sha256=hashlib.sha256(FW).hexdigest())
out=ROOT/'V29_第三模式_候选固件_仅离线禁止刷写.bin'
out.write_bytes(FW)
(ROOT/'V29_第三模式_候选固件_清单.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print('V29_CANDIDATE_BUILD_OK',hex(keyhook),hex(tick),
 'CHANGED',len(actual),'SHA',report['sha256'],
 'CODE_FREE',[(x[3],x[1]-x[2])for x in code_regions],flush=True)
