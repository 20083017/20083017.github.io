

```
/**
 * Definition for singly-linked list.
 * struct ListNode {
 *     int val;
 *     ListNode *next;
 *     ListNode() : val(0), next(nullptr) {}
 *     ListNode(int x) : val(x), next(nullptr) {}
 *     ListNode(int x, ListNode *next) : val(x), next(next) {}
 * };
 */
class Solution {
public:
    ListNode* mergeKLists(vector<ListNode*>& lists) {
        ListNode* m_list = nullptr;
        ListNode* m_list_head = nullptr;
        if(lists.size() == 0)
        {
            return nullptr;
        }

        auto cmp = [](std::pair<int,int> p1, std::pair<int,int> p2){return p2.second < p1.second;};
        std::priority_queue<std::pair<int,int> ,std::vector<std::pair<int,int> >, decltype(cmp) > pq(cmp);

        std::unordered_map<int, ListNode*> mp;

        for(int i = 0; i < lists.size(); ++i)
        {
            if(lists[i] != nullptr)
            {
                pq.push(std::make_pair(i, lists[i]->val));
                mp[i] = lists[i];
            }
        }

        while(!pq.empty())
        {
            std::pair<int,int> t = pq.top();
            if(m_list_head == nullptr)
            {
                m_list = mp[t.first];
                m_list_head = mp[t.first];
            }else
            {
                m_list->next = mp[t.first];
                m_list = m_list->next;
            }
            pq.pop();
            if(mp[t.first]->next != nullptr)
            {
                mp[t.first] = mp[t.first]->next;
                pq.push(std::make_pair(t.first, mp[t.first]->val));
            }
        }

        return m_list_head;
    }
};
```
