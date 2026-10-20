#include "research_cache_policy.h"
#include <cassert>
using namespace Generators::CacheResearch;
int main() {
  std::vector<Row> rows(6);
  rows[0].prefill=false;
  for(size_t i=1;i<6;++i){rows[i].prefill=true;rows[i].pending=100;rows[i].leading_tokens={1,2,3};}
  rows[3].leading_tokens={1,2,4};
  auto order=Order(rows,2);
  auto selected=Coalesce(rows,order);
  assert((selected==std::vector<size_t>{0,1,3}));
  rows[1].resident=true;
  selected=Coalesce(rows,order);assert((selected==std::vector<size_t>{0,1,3}));
  rows[4].wait=64;
  selected=Coalesce(rows,Order(rows,2));
  assert(std::find(selected.begin(),selected.end(),4)!=selected.end());
  assert(std::find(selected.begin(),selected.end(),1)!=selected.end());
  rows[2].leading_tokens.clear();
  selected=Coalesce(rows,Order(rows,2));
  assert(std::find(selected.begin(),selected.end(),2)!=selected.end());
  assert(Coalesce({},{}).empty());
  // A leader's cancellation/removal must not strand its queued followers.
  std::vector<Row> cold(3);
  for(auto& row:cold){row.prefill=true;row.pending=600;row.leading_tokens={1,2,3};}
  assert(Coalesce(cold,Order(cold,2)).size()==1);
  cold.erase(cold.begin());
  assert(Coalesce(cold,Order(cold,2)).size()==1);
  // Reusable prefixes bypass cold-prefix deferral: native adapter leaves keys empty.
  for(auto& row:cold){row.cached=512;row.leading_tokens.clear();}
  assert(Coalesce(cold,Order(cold,2)).size()==2);
}
