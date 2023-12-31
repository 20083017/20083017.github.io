

疑似未生效
```
    CURLcode ret1;
    ret1 = curl_easy_setopt(curl_handle, CURLOPT_SSLVERSION,  CURL_SSLVERSION_TLSv1_2);
    if(ret1 != CURLE_OK)
    {
        MiLogE("request.url: CURLOPT_SSLVERSION failed ! ret = %d", ret1);
    }
   ret1 = curl_easy_setopt(curl_handle, CURLOPT_SSL_CIPHER_LIST,
                       // "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256" ":"
                       // "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384"
                       // "TLS-ECDHE-ECDSA-WITH-AES-256-GCM-SHA384"
                       "ECDHE-ECDSA-AES256-GCM-SHA384" ":"
                       "ECDHE-ECDSA-AES128-GCM-SHA256"
                        ":"
                       "ECDHE-ECDSA-AES256-SHA384"     ":"
                       "DHE-RSA-AES256-GCM-SHA384"     ":"
                       "ECDHE-RSA-AES256-GCM-SHA384"   ":"
                       "ECDHE-RSA-AES128-GCM-SHA256"   ":"
                       "ECDHE-ECDSA-AES128-SHA"        ":"
                       "ECDHE-ECDSA-AES128-SHA256"     ":"
                       "ECDHE-RSA-CHACHA20-POLY1305"   ":"
                       "ECDHE-RSA-AES256-SHA384"       ":"
                       "ECDHE-RSA-AES128-SHA256"       ":"
                       "ECDHE-ECDSA-CHACHA20-POLY1305" ":"
                       "ECDHE-ECDSA-AES256-SHA"        ":"
                       "ECDHE-RSA-AES128-SHA"          ":"
                       "DHE-RSA-AES128-GCM-SHA256"
                   );
   // curl_easy_setopt(curl_handle, CURLOPT_SSLVERSION,  CURL_SSLVERSION_TLSv1_1|CURL_SSLVERSION_TLSv1_2 |  CURL_SSLVERSION_TLSv1_3 | CURL_SSLVERSION_TLSv1 | CURL_SSLVERSION_SSLv2 | CURL_SSLVERSION_SSLv3);
   if(ret1 != CURLE_OK)
   {
       MiLogE("request.url:CURLOPT_SSL_CIPHER_LIST  ret = %d", ret1);
   }

    // curl_easy_setopt(curl_handle, CURLOPT_TLS13_CIPHERS,
    //                     // "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256" ":"
    //                     // "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384" 
    //                     "TLS-ECDHE-ECDSA-WITH-AES-256-GCM-SHA384"
    //                 );
```



### 坑

android ndk版本 ，ndk23.版本   ndk25版本存在问题，ndk26版本存在问题？具体啥问题忘记了。。。
疑似这个问题，换低版本好使了，高版本为啥不好使，还是不知道。。
![image](https://github.com/20083017/20083017.github.io/assets/8308226/59fe9871-a8e3-4fc4-b58e-4983a351c30b)

区别  clang版本不同，lto支持不同，低版本可能不支持lto，
android lto 坑，cxx link 需要同时增加lto  报错信息 file format not recognized


### 抓包结果

![image](https://github.com/20083017/20083017.github.io/assets/8308226/f753f8f2-27e7-4140-a3f9-0c24991baa4b)


### 坑
裁剪后，同步修改mbedtls_config.h

### 


