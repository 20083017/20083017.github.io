

```
//最小堆
class KthLargest {
private:
    std::priority_queue<int, std::vector<int>, std::greater<int>> p;
    int k;
public:
    KthLargest(int k, vector<int>& nums) {
        this->k = k;
        for(auto item: nums)
        {
            add(item);
        }
    }
    
    int add(int val) {
        if(p.size() < k)
        {
            p.emplace(val);
            return p.top();
        }
        int t = p.top();
        // std::cout << t << std::endl;
        if(val > t)
        {
            p.pop();
            p.emplace(val);
        }
        return p.top();
    }
};
```
