#ifdef _WIN32
#define SC5_EXPORT __declspec(dllexport)
#else
#define SC5_EXPORT __attribute__((visibility("default")))
#endif
/* Native AOT side of the reference comparison; uses the retained Forge MIT decoder. */
#define main diagnostic_main
#include "sc5-boot-probe.c"
#undef main
SC5_EXPORT void sc5_reset(const unsigned char *image){
 external_read=0;external_write=0;external_retire=0;external_clock=0;external_service=0;external_queue_write=0;deferred_code_guard=0;ram=internal_ram;
 memset(&s,0,sizeof(s));memset(ram,0,0x1000000);memcpy(ram+0x10000,image,0x260000);
 memset(intc,0,sizeof(intc));steps=0;ccr=0;model_ccr=1;host_services=0;
 u32 crc=0xffffffffu;for(u32 j=0;j<0x260000u;j++){crc^=image[j];for(u32 bit=0;bit<8;bit++)crc=(crc>>1)^((0u-(crc&1u))&0xedb88320u);}
 if((crc^0xffffffffu)!=EXPECTED_CRC32){s.pc=0x8c010000u;s.fault=12;return;}
 s.pc=0x8c010000;s.pr=0xac00e0b0;s.r[15]=0x8c00f400;s.vbr=0x8c00f400;set_sr(0x700000f0);set_fpscr(0x40000);
}
SC5_EXPORT void sc5_run(u32 budget){run(budget);}
/* Relative chunks avoid the diagnostic's 32-bit absolute instruction limit. */
SC5_EXPORT u32 sc5_run_chunk(u32 budget){steps=0;run(budget);return steps;}
SC5_EXPORT u32 sc5_state(u32 index){
 if(index<16)return s.r[index];
 switch(index){case 16:return s.pc;case 17:return s.pr;case 18:return get_sr();case 19:return steps;case 20:return s.fault;default:return 0;}
}
SC5_EXPORT const unsigned char *sc5_ram(void){return ram;}
SC5_EXPORT State *sc5_context(void){return &s;}
SC5_EXPORT void sc5_set_retire(Retire callback){external_retire=callback;}
SC5_EXPORT void sc5_set_fast_clock(NativeFastClock *clock){
#ifdef SC5_STATIC_TIMING
 if(clock)for(u32 op=0;op<65536;op++){
  if(native_static_timing[op]!=(u32)(clock->timing[op].unit|(clock->timing[op].issue<<8))){
   fprintf(stderr,"Native static timing mismatch opcode=%04x; using host retirement\n",op);external_clock=0;return;
  }
 }
#endif
 external_clock=clock;
}
SC5_EXPORT void sc5_set_service(Service callback){external_service=callback;}
SC5_EXPORT void sc5_set_queue_write(QueueWrite callback){external_queue_write=callback;}
SC5_EXPORT void sc5_div1(u32 n,u32 m){divide_step(n,m);}
SC5_EXPORT void sc5_float(u32 n,u32 m,u32 kind){float_arithmetic(n,m,kind);}
SC5_EXPORT void sc5_float_extended(u32 n,u32 m,u32 kind){float_extended(n,m,kind);}
SC5_EXPORT void sc5_fmov(u32 n,u32 m,u32 kind){fmov_single(n,m,kind);}
SC5_EXPORT void sc5_transform(u32 n){float_transform(n);}
SC5_EXPORT void sc5_sincos(u32 n){float_sincos(n);}
SC5_EXPORT void sc5_inner(u32 n,u32 m){float_inner(n,m);}
SC5_EXPORT void sc5_precision(u32 n,u32 direction){float_precision(n,direction);}
SC5_EXPORT void sc5_convert(u32 n,u32 kind){float_convert(n,kind);}
SC5_EXPORT void sc5_use_bus(unsigned char *shared_ram,BusRead read,BusWrite write){
 memcpy(shared_ram,ram,0x1000000);ram=shared_ram;external_read=read;external_write=write;
 deferred_code_guard=1; /* Every executed instruction and delay slot still verifies its expected bytes. */
 host_services=1;wr(0x8c0000b0u,0x8c000100u,4);
}
/* Attach another round's AOT image to the existing native device state.  The
   shared RAM is already populated by the disc service, so unlike sc5_use_bus
   this does not overwrite it. */
SC5_EXPORT void sc5_attach_bus(unsigned char *shared_ram,BusRead read,BusWrite write){
 ram=shared_ram;external_read=read;external_write=write;deferred_code_guard=1;host_services=1;
}
