/* Public policy boundary. Included after router snapshot helpers so that policy
   values remain explicit stack arguments, never mutable global/TLS settings. */
void bs_default_operational_policy(BSOperationalPolicyV1 *p){
    if(!p)return;
    p->struct_size=sizeof(*p);
    p->dependence_threshold=ABS_DEPENDENCE_THRESHOLD;
    p->growth_threshold=ABS_GROWTH_THRESHOLD;
    p->compatibility_tolerance=2e-10;
    p->quality_threshold=ABS_QUALITY_THRESHOLD;
}
int bs_validate_operational_policy(const BSOperationalPolicyV1 *p){
    if(!p || p->struct_size<sizeof(*p))return BS_POLICY_INVALID_ARGUMENT;
    double v[4]={p->dependence_threshold,p->growth_threshold,
                 p->compatibility_tolerance,p->quality_threshold};
    for(int i=0;i<4;i++)if(bs_nonfinite(v[i]) || !(v[i]>0.0) || v[i]>1.0)
        return BS_POLICY_INVALID_ARGUMENT;
    return p->dependence_threshold<p->growth_threshold ? 0 : BS_POLICY_INVALID_ARGUMENT;
}
void bs_init_operational_result(BSOperationalResultV1 *out){
    if(!out)return;
    memset(out,0,sizeof(*out));out->struct_size=sizeof(*out);
    out->operational_status=ABS_STATUS_FAIL;out->operational_certainty=3;
    out->router_meta[0]=ABS_STATUS_FAIL;out->router_meta[1]=3;
    out->router_meta[5]=NAN;out->router_meta[6]=NAN;out->router_meta[10]=NAN;
    out->core_rank_interval[0]=out->core_rank_interval[1]=-1;out->core_qr_rank=-1;
    out->exact_source_status=BS_EXACT_SOURCE_UNKNOWN;
    out->exact_source_verification=BS_EXACT_VERIFY_NOT_VERIFIED;
}
int bsolve_router_policy_api(const double*A,const double*b,const double*xt,
    int m,int n,int sp,int qv,int alpha,unsigned long long seed,int full,
    const BSOperationalPolicyV1 *policy,BSOperationalResultV1 *out){
    if(!out || out->struct_size<sizeof(*out))return BS_POLICY_INVALID_ARGUMENT;
    size_t size=out->struct_size;
    /* Snapshot the policy before clearing output (allows policy=&out->policy_used). */
    BSOperationalPolicyV1 p;int invalid=bs_validate_operational_policy(policy);
    if(!invalid){p=*policy;p.struct_size=sizeof(p);}
    bs_init_operational_result(out);out->struct_size=size;
    if(invalid)return BS_POLICY_INVALID_ARGUMENT;
    out->policy_used=p;
    if(m<=0 || n<=0 || sp<=0 || qv<=0 || alpha<=0 || !A || !b ||
       sp>INT_MAX/m || n>INT_MAX/2 || alpha>INT_MAX/(n+1) ||
       (size_t)m>SIZE_MAX/(size_t)n || (size_t)m*(size_t)n>SIZE_MAX/sizeof(double) ||
       (size_t)n>(SIZE_MAX/sizeof(double))/(size_t)n ||
       (size_t)qv>(SIZE_MAX/sizeof(double))/(size_t)n ||
       bs_any_nonfinite(A,(size_t)m*n) || bs_any_nonfinite(b,(size_t)m) ||
       (xt && bs_any_nonfinite(xt,(size_t)n)))return BS_POLICY_INVALID_ARGUMENT;
    BSOperationalPolicyV1 def;bs_default_operational_policy(&def);
    ABSRouterSnapshot s;
    if(p.dependence_threshold==def.dependence_threshold && p.growth_threshold==def.growth_threshold &&
       p.compatibility_tolerance==def.compatibility_tolerance && p.quality_threshold==def.quality_threshold){
        abs_router_snapshot_internal(A,b,xt,m,n,sp,qv,alpha,seed,full,&s);
    }else{
        unsigned long long before[3]={g_fg_checks,g_fg_escalations,g_source_qrcp_calls};
        memset(&s,0,sizeof(s));diag_reset();g_source_rank_lo=g_source_rank_hi=-1;
        g_last_berr=0;g_last_berr_valid=0;
        Result r={0};double t=now_sec();
        int rc=source_qrcp_policy(A,b,xt,m,n,p.compatibility_tolerance,&r,
                                  p.dependence_threshold,p.growth_threshold,p.quality_threshold);
        if(rc<0){BS_FAIL_RESULT(r,t);}
        if(r.cls==CLS_UNIQUE && (!g_last_berr_valid || bs_nonfinite(g_last_berr) || g_last_berr>p.quality_threshold)){
            r.cls=CLS_UNDECIDABLE;r.relres=NAN;r.relx=NAN;
        }
        s.meta[0]=r.cls;s.meta[1]=(r.cls==CLS_FAIL||r.cls==CLS_UNDECIDABLE)?3:1;
        s.meta[2]=r.rank;s.meta[3]=r.rank;s.meta[4]=r.rank;
        if(r.cls==CLS_UNDECIDABLE && g_source_rank_lo>=0){s.meta[3]=g_source_rank_lo;s.meta[4]=g_source_rank_hi;}
        s.meta[5]=(r.cls==CLS_FAIL||r.cls==CLS_UNDECIDABLE)?NAN:r.relres;
        s.meta[6]=(r.cls==CLS_INCONSISTENT||r.cls==CLS_FAIL||r.cls==CLS_UNDECIDABLE)?NAN:r.relx;
        s.meta[7]=r.sec;s.meta[8]=r.fallback;s.meta[9]=r.cls;
        s.meta[10]=r.cls==CLS_UNIQUE?g_last_berr:NAN;
        capture_router_diagnostics(&s,before);
    }
    out->operational_status=(int)s.meta[0];out->operational_certainty=(int)s.meta[1];
    memcpy(out->router_meta,s.meta,sizeof(s.meta));
    out->grey_distinct_count=s.grey_distinct_count;out->grey_total_events=s.grey_total_events;
    memcpy(out->grey_rows,s.grey_rows,sizeof(s.grey_rows));out->last_orth_eta=s.last_orth_eta;
    memcpy(out->core_rank_interval,s.core_rank_interval,sizeof(s.core_rank_interval));
    out->core_qr_rank=s.core_qr_rank;
    memcpy(out->formation_guard_counters,s.formation_guard_counters,sizeof(s.formation_guard_counters));
    return out->operational_status==ABS_STATUS_FAIL?BS_POLICY_SOLVER_FAILED:BS_POLICY_OK;
}
