#include "research_cache_policy.h"
#include <cassert>
#include <random>
using namespace Generators::CacheResearch;
int main() {
  std::mt19937 rng(701);
  for (int trial=0; trial<2000; ++trial) {
    std::vector<Row> rows;
    std::vector<size_t> decodes;
    const size_t count=rng()%65;
    for (size_t i=0;i<count;++i) {
      Row row;
      row.prefill=rng()%4!=0;row.pending=1+rng()%8192;
      row.cached=rng()%2?1024:0;row.private_blocks=rng()%33;
      row.wait=rng()%80;row.group=rng()%8;
      if(row.cached)row.retained_ids={row.group*2,row.group*2+1};
      if(!row.prefill)decodes.push_back(i);
      rows.push_back(row);
    }
    for (int action=0;action<3;++action) {
      auto order=Order(rows,action);
      assert(order.size()==rows.size());
      assert(std::equal(decodes.begin(),decodes.end(),order.begin()));
      auto sorted=order;std::sort(sorted.begin(),sorted.end());
      for(size_t i=0;i<sorted.size();++i)assert(sorted[i]==i);
      bool ordinary=false;
      for(auto i:order)if(rows[i].prefill){
        if(rows[i].wait<64)ordinary=true;
        else assert(!ordinary);
      }
    }
    auto state=Features(rows,0,16,128);
    for(auto value:state)assert(std::isfinite(value));
  }
}
