// Research-only native continuous-batching ordering experiment. MIT license.
#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <numeric>
#include <random>
#include <stdexcept>
#include <unordered_set>
#include <vector>

namespace Generators::CacheResearch {
constexpr size_t kFeatures = 8;
struct Row {
  bool prefill{};
  size_t pending{}, cached{}, private_blocks{}, wait{};
  std::vector<size_t> retained_ids;
  size_t group{};
};

inline std::vector<size_t> Order(const std::vector<Row>& rows, int action) {
  if (action < 0 || action > 2) throw std::invalid_argument("Invalid ordering action");
  std::vector<size_t> result, pending;
  for (size_t i=0;i<rows.size();++i)
    (rows[i].prefill ? pending : result).push_back(i);
  std::unordered_set<size_t> charged;
  while (!pending.empty()) {
    auto score = [&](size_t i) {
      const auto& r=rows[i];
      if (r.wait>=64) return -1e12-static_cast<double>(r.wait);
      if (action==0) return static_cast<double>(i);
      if (action==1) return static_cast<double>(r.pending);
      size_t charge=r.private_blocks;
      for (auto id:r.retained_ids) charge+=charged.count(id)==0;
      size_t siblings=0;
      if (r.cached) for (auto j:pending) siblings+=rows[j].cached && rows[j].group==r.group;
      return (static_cast<double>(r.pending)+256.0*charge)/(1.0+0.5*siblings);
    };
    auto best=std::min_element(pending.begin(),pending.end(),[&](size_t a,size_t b){return score(a)<score(b);});
    const size_t i=*best;
    result.push_back(i);
    charged.insert(rows[i].retained_ids.begin(),rows[i].retained_ids.end());
    pending.erase(best);
  }
  return result;
}

inline std::array<double,kFeatures> Features(const std::vector<Row>& rows,size_t residents,size_t row_limit,size_t blocks) {
  size_t q=0,decode=0,wait=0,minimum=~size_t{0},maximum=0;
  double hit=0,charge=0;
  for(const auto& r:rows) {
    if(!r.prefill){++decode;continue;}
    ++q;wait=std::max(wait,r.wait);minimum=std::min(minimum,r.pending);maximum=std::max(maximum,r.pending);
    hit+=static_cast<double>(r.cached)/std::max(size_t{1},r.cached+r.pending);
    charge+=r.private_blocks+r.retained_ids.size();
  }
  return {1.0,std::min(2.0,std::log1p(q)/std::log(65.0)),
    static_cast<double>(decode)/std::max(size_t{1},rows.size()),hit/std::max(size_t{1},q),
    static_cast<double>(residents)/std::max(size_t{1},row_limit),
    charge/std::max(size_t{1},q*std::max(size_t{1},blocks)),
    q ? static_cast<double>(maximum-minimum)/std::max(size_t{1},maximum):0.0,
    std::min(1.0,static_cast<double>(wait)/64.0)};
}

struct Controller {
  const char* mode=std::getenv("GENAI_RESEARCH_CACHE_POLICY");
  bool trace=std::getenv("GENAI_RESEARCH_CACHE_TRACE")!=nullptr;
  std::array<std::array<double,kFeatures>,3> weights{};
  std::mt19937_64 rng{[](){const char* s=std::getenv("GENAI_RESEARCH_CACHE_SEED");return s?std::strtoull(s,nullptr,10):1ULL;}()};
  Controller() {
    if(!mode) return;
    if(std::strcmp(mode,"fifo") && std::strcmp(mode,"shortest") && std::strcmp(mode,"cache") &&
       std::strcmp(mode,"rl_train") && std::strcmp(mode,"rl")) throw std::invalid_argument("Unknown research cache policy");
    const char* p=std::getenv("GENAI_RESEARCH_CACHE_WEIGHTS");
    if(p) {
      for(auto& row:weights) for(auto& value:row) {
        char* end=nullptr;value=std::strtod(p,&end);
        if(end==p || !std::isfinite(value)) throw std::invalid_argument("Invalid actor weights");
        p=end;while(*p==' ' || *p==',')++p;
      }
      if(*p) throw std::invalid_argument("Extra actor weights");
    }
  }
  bool Enabled() const {return mode!=nullptr;}
  std::vector<size_t> Select(const std::vector<Row>& rows,size_t residents,size_t limit,size_t blocks) {
    std::array<std::vector<size_t>,3> orders{Order(rows,0),Order(rows,1),Order(rows,2)};
    std::array<bool,3> valid{true,orders[1]!=orders[0],orders[2]!=orders[0] && orders[2]!=orders[1]};
    auto state=Features(rows,residents,limit,blocks);
    std::array<double,3> probability{};
    int action=0;
    if(!std::strcmp(mode,"cache"))action=2;
    if(!std::strcmp(mode,"shortest"))action=1;
    if(!std::strncmp(mode,"rl",2)) {
      double maximum=-1e300;
      for(size_t a=0;a<3;++a) if(valid[a]) {
        for(size_t k=0;k<kFeatures;++k)probability[a]+=weights[a][k]*state[k];
        maximum=std::max(maximum,probability[a]);
      }
      double sum=0;
      for(size_t a=0;a<3;++a){probability[a]=valid[a]?std::exp(probability[a]-maximum):0;sum+=probability[a];}
      for(auto& p:probability)p/=sum;
      if(!std::strcmp(mode,"rl_train")) action=std::discrete_distribution<int>(probability.begin(),probability.end())(rng);
      else action=static_cast<int>(std::max_element(probability.begin(),probability.end())-probability.begin());
    } else probability[action]=1;
    if(trace && (valid[1]||valid[2])) {
      std::fprintf(stderr,"CACHE_ACTOR {\"action\":%d,\"state\":[",action);
      for(size_t k=0;k<kFeatures;++k)std::fprintf(stderr,"%s%.17g",k?",":"",state[k]);
      std::fprintf(stderr,"],\"probability\":[%.17g,%.17g,%.17g],\"mask\":[%d,%d,%d]}\n",
        probability[0],probability[1],probability[2],valid[0],valid[1],valid[2]);
    }
    return orders[action];
  }
};
inline Controller& Policy(){static Controller controller;return controller;}
}  // namespace Generators::CacheResearch
