ENTRY(epoch)
native_tick = 0x0803a2bb;
native_unsynced = 0x0807fbc3;
native_query_reply = 0x0807fbb3;
native_send = 0x0805a51b;
SECTIONS {
 .epoch 0x0804828c : { KEEP(*(.epoch)) }
 .prep 0x080482d0 : { KEEP(*(.prep)) }
 .query 0x0807fb8c : { KEEP(*(.query)) }
 .reply 0x0807fbd4 : { KEEP(*(.reply)) }
 .decode_tail 0x0807fbec : { KEEP(*(.decode_tail)) }
 .set 0x0807fc34 : { KEEP(*(.set)) }
 .prep_rest 0x0807fcac : { KEEP(*(.prep_rest)) }
 .read 0x0807ff9c : { KEEP(*(.read)) }
 .decode 0x0807ffe0 : { KEEP(*(.decode)) }
 /DISCARD/ : { *(.ARM.exidx*) *(.comment*) *(.note*) }
}
ASSERT(SIZEOF(.epoch)<=0x44,"epoch overflow")
ASSERT(SIZEOF(.prep)<=0x1a,"prep overflow")
ASSERT(SIZEOF(.query)<=0x26,"query overflow")
ASSERT(SIZEOF(.reply)<=0x18,"reply overflow")
ASSERT(SIZEOF(.decode_tail)<=0x18,"decode tail overflow")
ASSERT(SIZEOF(.set)<=0x78,"set overflow")
ASSERT(SIZEOF(.prep_rest)<=0x20,"prep rest overflow")
ASSERT(SIZEOF(.read)<=0x44,"read overflow")
ASSERT(SIZEOF(.decode)<=0x20,"decode overflow")
