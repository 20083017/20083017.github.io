

1、 创建应用

应用列表获取 
grant_type： 必须参数，固定为client_credentials；
client_id： 必须参数，应用的API Key；
client_secret： 必须参数，应用的Secret Key；

2、运行脚本获取 access key
access key  有效期 30天
```
import requests
import json


def main():
        
    url = "https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id=x8ougYUHJ7YbstWTS2rVa3rr&client_secret=D663Yu4bdrD9ITBgRSyiI8joLR6JnUEZ"
    
    payload = ""
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    response = requests.request("POST", url, headers=headers, data=payload)
    
    print(response.text)
    

if __name__ == '__main__':
    main()
```


3、ocr 

```
import requests
import json


def main():
        
    url = "https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id=AMBDOhXAPwC4HVDcrsMAQrY1&client_secret=pjx1RTdgTjUX2qiYvhLXdowawidDrigs"
    
    payload = ""
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    response = requests.request("POST", url, headers=headers, data=payload)
    
    print(response.text)
    

if __name__ == '__main__':
    main()
```




