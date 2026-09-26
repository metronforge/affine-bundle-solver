#define _GNU_SOURCE
#pragma STDC FENV_ACCESS ON
#include <fenv.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

static uint64_t tick(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC_RAW,&t);return(uint64_t)t.tv_sec*1000000000ULL+(uint64_t)t.tv_nsec;}
static uint64_t control(unsigned long long n){uint64_t s=tick();for(unsigned long long i=0;i<n;++i)__asm__ __volatile__("":::"memory");return tick()-s;}
static uint64_t same_mode(unsigned long long n){int old=fegetround();fesetround(FE_DOWNWARD);uint64_t s=tick();for(unsigned long long i=0;i<n;++i)(void)fesetround(FE_DOWNWARD);uint64_t d=tick()-s;fesetround(old);return d;}
int main(int argc,char**argv){
 unsigned long long n=argc>1?strtoull(argv[1],0,10):1000000ULL;int trials=argc>2?atoi(argv[2]):11;
 (void)same_mode(n);(void)control(n);puts("trial,calls,same_mode_ns,control_ns,net_ns,net_per_call_ns");
 for(int i=0;i<trials;++i){uint64_t a,b;if(i&1){b=control(n);a=same_mode(n);}else{a=same_mode(n);b=control(n);}uint64_t net=a>b?a-b:0;printf("%d,%llu,%llu,%llu,%llu,%.9f\n",i,n,(unsigned long long)a,(unsigned long long)b,(unsigned long long)net,(double)net/(double)n);}
 return 0;
}
