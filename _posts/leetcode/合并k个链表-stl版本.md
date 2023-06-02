
```
#include <iostream>  
#include <atomic>
#include <thread>      
#include <vector>  
#include <iterator>
// can be checked without being set
#include <type_traits>
#include <memory>
#include <list>
#include <queue>

int main() {

    std::list<int> l1;
    l1.emplace_back(1);
    l1.emplace_back(20);
    l1.emplace_back(25);
    std::list<int> l2;
    l2.emplace_back(2);
    l2.emplace_back(10);
    l2.emplace_back(33);

    std::vector<std::list<int>> lists = {l1,l2};

    typedef std::pair<int,std::list<int>::iterator> listIterator;

    auto cmp = [](listIterator p1, listIterator p2){ return *(p2.second) < *(p1.second); };
    
    std::priority_queue< listIterator, std::vector<listIterator>, decltype(cmp) > pq(cmp);

    for(size_t i = 0; i < lists.size(); ++i)
        {
            pq.emplace(std::make_pair(i,lists[i].begin()));
        }

    std::list<int> ret;
    
    while(!pq.empty())
        {
            listIterator t = pq.top();
            pq.pop();
            ret.emplace_back(*(t.second));
            
            if(++t.second != lists[t.first].end())
            {
                pq.emplace(std::make_pair(t.first, t.second));
            }
        }

    auto iter = ret.begin();
    while(iter != ret.end())
        {
            std::cout << (*iter) << std::endl;
            ++iter;
        }
    

    return 0;
}
```
