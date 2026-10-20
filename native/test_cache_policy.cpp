#include "research_cache_policy.h"
#include <cassert>
#include <limits>
using namespace Generators::CacheResearch;
int main(){
 std::vector<Row> rows{{false,1,0,0,0,{},0},{true,100,512,1,0,{10,11},11},{true,300,512,2,0,{10,11},11},{true,80,0,4,0,{},0}};
 for(int a=0;a<3;++a){auto order=Order(rows,a);assert(order[0]==0);assert(order.size()==4);}
 assert((Order(rows,0)==std::vector<size_t>{0,1,2,3}));
 assert((Order(rows,1)==std::vector<size_t>{0,3,1,2}));
 assert(Order(rows,2)[1]==1);
 rows[3].wait=std::numeric_limits<size_t>::max();
 for(int a=0;a<3;++a)assert(Order(rows,a)[1]==3);
 auto f=Features(rows,2,16,128);for(auto x:f)assert(std::isfinite(x));
 assert(Order({},2).empty());
}
