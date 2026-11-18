.syntax unified
.thumb
.cpu cortex-m4

/* V95 application patch, no flash operations. Use LICK only; retain backup domain, never reset it. */
.section .prep,"ax",%progbits
.global probe_hook
.thumb_func
probe_hook:
 ldr r0,=0x40023800
 ldr r1,[r0,#0x40]
 orr r1,r1,#0x10000000
 str r1,[r0,#0x40]
 b.w prep_rest
.ltorg
.section .prep_rest,"ax",%progbits
.global prep_rest
.thumb_func
prep_rest:
 ldr r1,=0x40007000
 ldr r2,[r1]
 orr r2,r2,#0x100
 str r2,[r1]
 ldr r1,[r0,#0x74]
 movs r2,#1
 orrs r1,r2
 str r1,[r0,#0x74]
 movs r0,#1
 str r0,[r5,#16]
 bx lr
.ltorg

.section .set,"ax",%progbits
.global set_hook
.thumb_func
set_hook:
 push {r4,r6,r7,lr}
 str r0,[r5,#4] /* stock RAM remains authoritative while powered */
 mov r4,r0
 ldr r6,=0x40023870
 ldr r0,[r6,#4] /* CTRLSTS: internal oscillator ready */
 lsls r0,r0,#30
 bpl done
 ldr r0,[r6]
 lsls r1,r0,#23 /* reject existing source 1 or 3, never reset backup domain */
 bmi done
 orr r0,r0,#0x8200
 str r0,[r6]
 ldr r6,=0x40002800
 movs r0,#0xca
 str r0,[r6,#0x24]
 movs r0,#0x53
 str r0,[r6,#0x24]
 movs r0,#0
 str r0,[r6,#0x54]
 mvns r0,r0
 str r0,[r6,#0xc] /* SDK init-mode entry */
 movw r7,#60000
wait:
 ldr r0,[r6,#0xc]
 tst r0,#0x40
 bne ready
 subs r7,#1
 bne wait
 b exit_init
ready:
 movs r0,#0x20
 str r0,[r6,#8] /* 24h, direct read */
 ldr r0,=0x007c013f
 str r0,[r6,#0x10]
 movs r0,#0
 str r0,[r6]
 movw r0,#0xc101 /* Saturday, 2000-01-01 */
 str r0,[r6,#4]
 str r4,[r6,#0x50]
exit_init:
 mvn r0,#0x80
 str r0,[r6,#0xc]
 cbz r7,lock_rtc
 ldr r0,=0x98319a7d
 str r0,[r6,#0x54]
lock_rtc:
 movs r0,#255
 str r0,[r6,#0x24]
done:
 bl native_tick
 pop {r4,r6,r7,pc}
.ltorg

/* Reuse the native query code space. Remain ABI-compatible with V95,
   only returning an epoch when the retained hardware marker is valid. */
.section .epoch,"ax",%progbits
.global epoch
.thumb_func
epoch:
 push {r4,lr}
 mov r4,r2
 add.w r0,r0,#0x3c80
 bl clock_read
 cmp r0,#0
 ite ne
 movne r1,#1
 moveq r1,#0
 str r1,[r4]
 pop {r4,pc}
.global clock_read
.thumb_func
clock_read:
 ldr r3,[r0]
 ldr r2,=0x54494d45
 cmp r3,r2
 bne no_ram
 ldr r3,[r0,#24]
 mvns r2,r2
 cmp r3,r2
 bne no_ram
 ldr r2,[r0,#8]
 subs r1,r1,r2
 movw r2,#1000
 udiv r1,r1,r2
 ldr r0,[r0,#4]
 add r0,r1
 bx lr
no_ram:
 b.w rtc_read
.ltorg

.section .query,"ax",%progbits
.global query_hook
.thumb_func
query_hook:
 ldrb r0,[r4,#5]
 cmp r0,#0xa5
 beq rtc_diag
 cmp r0,#0xa6
 beq bp_diag
 bl native_tick
 mov r1,r0
 mov r0,r5
 bl clock_read
 /* Fixed local narrow branches; build audit checks exact disassembly. */
 .short 0xb170 /* cbz r0, native_unsynced at 0x0807fbc2 */
 .short 0xe005 /* b native_query_reply at 0x0807fbb2 */
rtc_diag:
 bl rtc_read
 .short 0xe002 /* b native_query_reply; zero is diagnostic failure, not error ACK */
bp_diag:
 .short 0x483b /* ldr r0,[pc,#236], literal 0x0807fc9c -> CRM BPDC */
 ldr r0,[r0]
 nop

.section .read,"ax",%progbits
.global rtc_read
.thumb_func
rtc_read:
 push {r4,r5,r6,lr}
 ldr r0,=0x40023870
 ldr r0,[r0]
 movw r1,#0x8300
 ands r0,r1
 movw r1,#0x8200
 cmp r0,r1
 bne invalid
 ldr r4,=0x40002800
 ldr r0,[r4,#0x54]
 ldr r1,=0x98319a7d
 cmp r0,r1
 bne invalid
 ldr r5,[r4]
 ldr r6,[r4,#4]
 ldr r0,[r4]
 cmp r0,r5
 bne invalid
 movw r0,#0xc101
 cmp r6,r0
 bne invalid
 /* Trial supports one elapsed day; retains normal RAM clock beyond that. */
 b.w rtc_decode
invalid:
 movs r0,#0
 pop {r4,r5,r6,pc}
.ltorg
.section .decode,"ax",%progbits
.global rtc_decode
.thumb_func
rtc_decode:
 ldr r0,=0x000f0f0f
 ands r0,r5
 lsrs r5,r5,#4
 ldr r1,=0x00030707
 ands r5,r1
 add.w r5,r5,r5,lsl #2
 add.w r5,r0,r5,lsl #1
 b.w decode_tail
.ltorg
.section .decode_tail,"ax",%progbits
.global decode_tail
.thumb_func
decode_tail:
 lsrs r0,r5,#16
 ubfx r1,r5,#8,#8
 movs r2,#60
 mla r0,r0,r2,r1
 uxtb r1,r5
 mla r0,r0,r2,r1

 ldr r1,[r4,#0x50]
 add r0,r1
 pop {r4,r5,r6,pc}
.ltorg

.section .reply,"ax",%progbits
.global reply_hook
.thumb_func
reply_hook:
 ldr r0,=0x0b081abe
 str r0,[sp]
 orr.w r0,r6,r7,lsl #8
 orr.w r0,r0,#0xed000000
 str r0,[sp,#4]
 mov r0,sp
 b.w native_send
.ltorg
