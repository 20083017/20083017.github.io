
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
#include <algorithm>
#include <unordered_map>
#include <errno.h>
#include <string.h>

#include <cstddef>
#include <iostream>

class lru{
private:
    std::list<std::pair<int,int>> l;
    std::unordered_map<int,std::list<std::pair<int,int>>::iterator> ump;
    int capacity_;
public:
    lru(int capacity):capacity_(capacity){
        
    }

    ~lru(){
        
    }

    void put(int key,int value){
        if(ump.count(key) ==  0)
        {
            if(l.size() < static_cast<size_t>(capacity_))
            {
                l.emplace_front(std::make_pair(key,value));
                ump[key] = l.begin();
            }else{
                ump.erase(l.back().first);
                l.pop_back();

                ump[key] = l.begin();
                l.emplace_front(std::make_pair(key,value));
            }
        }else{
            l.remove(*ump[key]);
            ump.erase(key);

            l.emplace_front(std::make_pair(key,value));
            ump[key] = l.begin();
        }
    }

    std::pair<int,int> get(int key){
        if(ump.count(key) ==  0)
        {
            return std::make_pair(-1,-1);
        }

        l.remove(*ump[key]);
        std::pair<int,int> t = *ump[key];
        l.emplace_front(std::make_pair(key,t.second));
        ump[key] = l.begin();

        return t;
    }

    void print(){
        for(auto iter = l.begin(); iter != l.end(); ++iter){
                std::cout << iter->first << " "  << iter->second << std::endl;
        }
    }
    
};

int main()
{

    lru my_lru(3);

    my_lru.put(1,1);
    my_lru.put(2,2);
    my_lru.put(3,3);

    // my_lru.print();
    
    my_lru.put(4,4);

    // my_lru.print();
    
    my_lru.get(2);

    my_lru.print();   
}
```
