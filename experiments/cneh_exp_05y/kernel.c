/* Portable scalar binary64 DP5(4). MPFR is the software transcendental engine.
 * No BLAS, no native exp/pow/sqrt, no fused multiply-add in this object.
 * Stage products and sums are ordered and separately rounded; the embedded\n * error dot alone is correctly rounded over exact binary64 inputs.
 */
#include <float.h>
#include <fenv.h>
#include <math.h>
#include <stdint.h>
#include <string.h>
#include <mpfr.h>

static _Thread_local int initialized, fault;
static _Thread_local mpfr_t a,b,y,lo,hi;
static void init(void) {
    if(!initialized) {
        mpfr_inits2(53,a,b,y,lo,hi,(mpfr_ptr)0);
        initialized=1;
    }
}
static uint64_t bits(double x){uint64_t u;memcpy(&u,&x,8);return u;}
static int op(mpfr_ptr z,int kind,mpfr_rnd_t rnd) {
    if(kind==0)return mpfr_exp(z,a,rnd);
    if(kind==1)return mpfr_pow(z,a,b,rnd);
    return mpfr_sqrt(z,a,rnd);
}
static double soft(int kind,double x,double exponent) {
    init();
    if(!isfinite(x)||!isfinite(exponent)||(kind==1&&x<=0.)||(kind==2&&x<0.)){
        fault=1;return NAN;
    }
    mpfr_set_d(a,x,MPFR_RNDN);mpfr_set_d(b,exponent,MPFR_RNDN);
    mpfr_set_prec(y,53);
    op(y,kind,MPFR_RNDN);
    double v=mpfr_get_d(y,MPFR_RNDN);
    /* For a finite normal result away from exponent boundaries, the
       correctly rounded 53-bit MPFR value is exactly representable. */
    if(isfinite(v)&&v>=2.*DBL_MIN&&v<=DBL_MAX/2.)return v;
    const int precisions[]={96,160,256,512};
    for(int i=0;i<4;i++){
        mpfr_set_prec(lo,precisions[i]);mpfr_set_prec(hi,precisions[i]);
        op(lo,kind,MPFR_RNDD);op(hi,kind,MPFR_RNDU);
        double l=mpfr_get_d(lo,MPFR_RNDN),h=mpfr_get_d(hi,MPFR_RNDN);
        if(bits(l)==bits(h)&&isfinite(l))return l;
    }
    fault=1;return NAN;
}
double soft_exp(double x){fault=0;return soft(0,x,0.);}
double soft_pow(double x,double p){fault=0;return soft(1,x,p);}
double soft_sqrt(double x){fault=0;return soft(2,x,0.);}
double separate_mul_add(double x,double y0,double z){double p=x*y0;return p+z;}
const char *software_version(void){return mpfr_get_version();}
int numeric_environment(void) {
    volatile double tiny=0x0.0000000000001p-1022;
    volatile double half=0.5,normal=DBL_MIN;
    return sizeof(double)==8&&FLT_RADIX==2&&DBL_MANT_DIG==53&&
           fegetround()==FE_TONEAREST&&bits(tiny+tiny)==2&&
           bits(normal*half)==0x0008000000000000ULL;
}

/* Exact binary64 coefficients of the frozen SciPy RK45 tableau. */
static const double C[6]={0x0p+0,0x1.999999999999ap-3,0x1.3333333333333p-2,0x1.999999999999ap-1,0x1.c71c71c71c71cp-1,0x1p+0};
static const double A[6][5]={
{0,0,0,0,0},{0x1.999999999999ap-3,0,0,0,0},
{0x1.3333333333333p-4,0x1.ccccccccccccdp-3,0,0,0},
{0x1.f49f49f49f49fp-1,-0x1.ddddddddddddep+1,0x1.c71c71c71c71cp+1,0,0},
{0x1.79eec0fc37181p+1,-0x1.7310bd29520e4p+3,0x1.3a552363c5290p+3,-0x1.29c9eba1e3345p-2,0},
{0x1.6c52bf5a814b0p+1,-0x1.583e0f83e0f84p+3,0x1.1d016a3721e8bp+3,0x1.1d1745d1745d1p-2,-0x1.1818970d9cc2fp-2}};
static const double B[6]={0x1.7555555555555p-4,0,0x1.cc0499a5605fbp-2,0x1.4d55555555555p-1,-0x1.4a1cfb2b78c13p-2,0x1.0c30c30c30c31p-3};
static const double E[7]={-0x1.4320fedcba987p-10,0,0x1.16b5a550abfc4p-8,-0x1.2eeeeeeeeeeefp-5,0x1.a0ad1d2ca1858p-5,-0x1.5748a7bdaf0e2p-5,0x1.999999999999ap-6};
static const double P[7][4]={
{0x1p+0,-0x1.6d421c90ad023p+1,0x1.892ee3cc04af1p+1,-0x1.208439215a046p+0},
{0,0,0,0},
{0,0x1.017b046ccf5e3p+2,-0x1.8ff4e27046a46p+2,0x1.56744f3b9a987p+1},
{0,-0x1.ddbf58f446418p+1,0x1.423501cf78761p+3,-0x1.6bdfac7a2320cp+2},
{0,0x1.4703cfd92b80bp+1,-0x1.998b0ea409b10p+2,0x1.c2ceae0978c92p+1},
{0,-0x1.5fda423d67152p+0,0x1.a2e673007345fp+1,-0x1.c46c8b61f95e5p+0},
{0,0x1.61e97be1b9227p+0,-0x1.e1e97be1b9227p+1,0x1.30f4bdf0dc914p+1}};

/* Correctly rounded dot of the represented binary64 tableau and stages.
 * MPFR dot rounds the sum of exact products, not the seven rounded
 * binary64 products. MPFR's wider exponent range avoids intermediate
 * over/underflow. Near binary64 exponent boundaries use outward bounds.
 */
static _Thread_local int dot_initialized;
static _Thread_local mpfr_t dot_e[7],dot_k[7],dot_y,dot_lo,dot_hi;
static _Thread_local mpfr_ptr dot_ep[7],dot_kp[7];

static void init_dot(void){
    if(dot_initialized)return;
    for(int k=0;k<7;k++){
        mpfr_init2(dot_e[k],53);mpfr_init2(dot_k[k],53);
        mpfr_set_d(dot_e[k],E[k],MPFR_RNDN);
        dot_ep[k]=dot_e[k];dot_kp[k]=dot_k[k];
    }
    mpfr_init2(dot_y,53);mpfr_init2(dot_lo,128);mpfr_init2(dot_hi,128);
    dot_initialized=1;
}
static double dot_component(const double *K,int i){
    if(i!=0&&i!=1){fault=1;return NAN;}
    init_dot();
    for(int k=0;k<7;k++){
        if(!isfinite(K[2*k+i])){fault=1;return NAN;}
        mpfr_set_d(dot_k[k],K[2*k+i],MPFR_RNDN);
    }
    mpfr_dot(dot_y,dot_ep,dot_kp,7,MPFR_RNDN);
    if(mpfr_zero_p(dot_y))return 0.;
    double v=mpfr_get_d(dot_y,MPFR_RNDN);
    if(isfinite(v)&&fabs(v)>=2.*DBL_MIN&&fabs(v)<=DBL_MAX/2.)return v;
    const int precisions[]={128,256,512,1024,4352};
    for(int k=0;k<5;k++){
        mpfr_set_prec(dot_lo,precisions[k]);mpfr_set_prec(dot_hi,precisions[k]);
        mpfr_dot(dot_lo,dot_ep,dot_kp,7,MPFR_RNDD);
        mpfr_dot(dot_hi,dot_ep,dot_kp,7,MPFR_RNDU);
        double l=mpfr_get_d(dot_lo,MPFR_RNDN),h=mpfr_get_d(dot_hi,MPFR_RNDN);
        if(bits(l)==bits(h)&&isfinite(l))return l;
    }
    fault=1;return NAN;
}
double error_dot(const double *K,int i){
    fault=0;
    if(!numeric_environment())return NAN;
    return dot_component(K,i);
}
static double embedded_error(const double *K,double h,const double *scale){
    double sq=0.;
    for(int i=0;i<2;i++){
        if(!isfinite(scale[i])||scale[i]<=0.){fault=1;return NAN;}
        double sum=dot_component(K,i);
        double z=(h*sum)/scale[i];
        double product=z*z;sq=sq+product;
    }
    return soft(2,sq/2.,0.);
}
double error_norm(const double *K,double h,const double *scale){
    fault=0;
    if(!numeric_environment()||!isfinite(h)||h<=0.)return NAN;
    double result=embedded_error(K,h,scale);
    return fault||!isfinite(result)?NAN:result;
}

void tableau(double *out){
    int k=0;
    for(int i=0;i<6;i++)out[k++]=C[i];
    for(int i=0;i<6;i++)for(int j=0;j<5;j++)out[k++]=A[i][j];
    for(int i=0;i<6;i++)out[k++]=B[i];
    for(int i=0;i<7;i++)out[k++]=E[i];
    for(int i=0;i<7;i++)for(int j=0;j<4;j++)out[k++]=P[i][j];
}
static double decay(double g,double dt,double tau){
    /* Analytically exact zero shortcut, no hidden transcendental rounding. */
    return g==0.?g:g*soft(0,-dt/tau,0.);
}
/* params: segment origin, g_AMPA(0), g_NMDA(0), g_GABA(0), current. */
static void rhs(double t,const double *s,const double *p,double *out){
    double V=s[0],w=s[1],dt=t-p[0];
    double ga=decay(p[1],dt,2.5),gn=decay(p[2],dt,100.),gg=decay(p[3],dt,6.);
    double nterm=0.;
    if(gn!=0.){
        double z=-.062*V,block;
        if(z>700.){double e=soft(0,-z,0.);block=e/(e+1./3.57);}
        else block=1./(1.+soft(0,z,0.)/3.57);
        nterm=gn*block*V;
    }
    double syn=ga*V+nterm+gg*(V+70.);
    double x=(V+55.)/2.;
    if(x>20.)x=20.;
    double ie=20.*soft(0,x,0.);
    double dv=(-10.*(V+70.)+ie-w-syn+p[4])/150.;
    double dw=(2.*(V+70.)-w)/200.;
    out[0]=dv;out[1]=dw;
    if(!isfinite(dv)||!isfinite(dw))fault=1;
}
int dp_trial(double t,double end,const double *s,const double *p,double rtol,double atol,
             double *K,double *next,double *scale,double *err,double *times){
    fault=0;
    double h=end-t;
    if(!(h>0.)||!numeric_environment())return 1;
    times[0]=t;rhs(t,s,p,K);
    for(int stage=1;stage<6;stage++){
        double tmp[2];
        for(int i=0;i<2;i++){
            double sum=0.;
            for(int k=0;k<stage;k++){double product=K[2*k+i]*A[stage][k];sum=sum+product;}
            tmp[i]=s[i]+h*sum;
        }
        double ts=stage==5?end:t+C[stage]*h;
        if(ts<t||ts>end)return 2;
        times[stage]=ts;rhs(ts,tmp,p,K+2*stage);
    }
    for(int i=0;i<2;i++){
        double sum=0.;
        for(int k=0;k<6;k++){double product=K[2*k+i]*B[k];sum=sum+product;}
        next[i]=s[i]+h*sum;
        double a0=fabs(s[i]),a1=fabs(next[i]);
        scale[i]=atol+rtol*(a0>a1?a0:a1);
    }
    times[6]=end;rhs(end,next,p,K+12);
    *err=embedded_error(K,h,scale);
    return fault||!isfinite(*err)||!isfinite(next[0])||!isfinite(next[1])?3:0;
}
void dp_dense(const double *K,double *Q){
    for(int i=0;i<2;i++)for(int j=0;j<4;j++){
        double sum=0.;
        for(int k=0;k<7;k++){double product=K[2*k+i]*P[k][j];sum=sum+product;}
        Q[4*i+j]=sum;
    }
}
void dp_sample(const double *old,const double *Q,double h,double x,double *out){
    for(int i=0;i<2;i++){
        double y=Q[4*i+3];
        for(int j=2;j>=0;j--)y=y*x+Q[4*i+j];
        out[i]=old[i]+h*(x*y);
    }
}
