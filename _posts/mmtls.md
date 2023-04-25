
![image](https://user-images.githubusercontent.com/8308226/234161851-298a1b93-57cf-4589-828b-b9f2741d3cad.png)



(1)客户端没有PSK，为了安全性，这时和长连接的握手方式一样，使用1-RTT ECDHE；
(2)客户端有PSK，这时为了减少网络时延，应该使用0-RTT PSK或0-RTT PSK-ECDHE，在这两种握手方式下，由于业务请求包始终是基于PSK进行保护的，同一个PSK多次协商出来的对称加密key是同一个，这个对称加密key的安全性依赖于ticket_key的安全性，因此0-RTT情况下，业务请求包始终是无法做到前向安全性。0-RTT PSK-ECDHE这种方式，只能保证本短连接业务响应回包的前向安全性，这带来安全性上的优势是比较小的，但是与0-RTT PSK握手方式相比，0-RTT PSK-ECDHE在每次握手对server会多2次ECDH运算和1次ECDSA运算。微信的短连接是非常频繁的，这对性能影响极大，因此综合考虑，在客户端有PSK的情况下，我们选择使用0-RTT PSK握手。由于0-RTT PSK握手安全性依赖ticket_key，为了加强安全性，在实现上，PSK必须要限制过期时间，避免长期用同一个PSK来进行握手协商；ticket_key必须定期轮换，且具有高度机密的运维级别。

1-RTT ECDHE握手、1-RTT PSK握手、0-RTT PSK握手
client端本身的完整性，非mmtls协议保护的范畴，仅对 server端进行 ecdsa认证，意思是 server端 需要进行 sign，client端 需要进行 verify。

如何避免签名密钥sign_key泄露带来的影响？
沿用现有逻辑。
　　如果sign_key泄露，那么任何人都可以伪造成Server欺骗Client，因为它拿到了sign_key，它就可以签发任何内容，Client用verify_key去验证签名必然验签成功。因此sign_key如果泄露必须要能够对verify_key进行撤销，重新派发新的公钥。这其实和前一问题是紧密联系的，前一问题是公钥派发问题，本问题是公钥撤销问题。TLS是通过CRL和OCSP两种方式来撤销公钥的，但是这两种方式存在撤销不及时或给验证带来额外延迟的副作用。由于mmtls是通过内置·verify_key·在客户端，必要时通过强制升级客户端的方式就能完成公钥撤销及更新。另外，sign_key是需要Server高度保密的，一般不会被泄露，对于微信后台来说，类似于sign_key这样，需要长期私密保存的密钥在之前也有存在，早已形成了一套方法和流程来应对长期私密保存密钥的问题。

用sign_key进行签名的内容仅仅只包含svr_pub_key是否有隐患？
　　回顾一下，上面描述的带认证的ECDH协商过程，似乎已经足够安全，无懈可击了，但是，面对成亿的客户端发起ECDH握手到成千上万台接入层机器，每台机器对一个TCP连接随机生成不同的ECDH公私钥对，这里试想一种情况，假设某一台机器某一次生成的ECDH私钥svr_pri_key1泄露，这实际上是可能的，因为临时生成的ECDH公私钥对本身没有做任何保密保存的措施，是明文、短暂地存放在内存中，一般情况没有问题，但在分布式环境，大量机器大量随机生成公私钥对的情况下，难保某一次不被泄露。
这样用sign_key（sign_key是长期保存，且分布式环境共享的）对svr_pub_key1进行签名得到签名值Signature1，此时攻击者已经拿到svr_pri_key1，svr_pub_key1和Signature1，这样他就可以实施中间人攻击，让客户端每次拿到的服务器ECDH公钥都是svr_pub_key1：客户端随机生成ECDH公私钥对（cli_pub_key, cli_pri_key）并将cli_pub_key发给Server，中间人将消息拦截下来，将client_pub_key替换成自己生成的client_pub_key’，并将svr_pub_key1和Signature1回给Client，这样Client就通过计算ECDH_Compute_Key(svr_pub_key1, cli_pri_key)=Key1, Server通过计算ECDH_Compute_Key(client_pub_key’, svr_pub_key)=Key’，中间人既可以计算出Key1和Key’，这样它就可以用Key1和Client通信，用Key’和Server进行通信。发生上述被攻击的原因在于一次握手中公钥的签名值被用于另外一次握手中，如果有一种方法能够使得这个签名值和一次握手一一对应，那么就能解决这个问题。
解决办法也很简单，就是在握手请求的ClientHello消息中带一个Client_Random随机值，然后在签名的时候将Client_Random和svr_pub_key一起做签名，这样得到的签名值就与Client_Random对应了。mmtls在实际处理过程中，为了避免Client的随机数生成器有问题，造成生成不够随机的Client_Random，实际上Server也会生成一个随机数Server_Random，然后在对公钥签名的时候将Client_Random、Server_Random、svr_pub_key一起做签名，这样由Client_Random、Server_Random保证得到的签名值唯一对应一次握手。


1-RTT ECDHE

细节：
随机数生成算法， 防重放攻击，client random，server random，选择3.

1）random函数：使用线性同余算法生成伪随机数（最初级随机数，不够随机）
2）random_device：linux系统中为抓取/dev/urandom设备中生成的随机数流（真随机数，但还是不够随机）
3）mt19937：梅森旋转法，理论上可以产生完全随机数，一般使用random_device作为种子
4）uniform_int_distribution：整数均匀分布，对生成的随机数作处理，转换成一定范围均匀分布的随机数 

密钥扩展
TLS1.3明确要求通信双方使用的对称加密Key不能完全一样，否则在一些对称加密算法下会被完全攻破，即使是使用AES-GCM算法，如果通信双方使用完全相同的加密密钥进行通信，在使用的时候也要小心翼翼的保证一些额外条件，否则会泄露部分明文信息。另外，AES算法的初始化向量（IV）如何构造也是很有讲究的，一旦用错就会有安全漏洞。也就是说，对于handshake协议协商得到的pre_master_secret不能直接作为双方进行对称加密密钥，需要经过某种扩展变换，得到六个对称加密参数：


```
Client Write MAC Key    （用于Client算消息认证码，以及Server验证消息认证码）
Server Write MAC Key   （用于Server算消息认证码，以及Client验证消息认证码）
Client Write Encryption Key（用做Client做加密，以及Server解密）
Server Write Encryption Key（用做Server做加密，以及Client解密）
Client Write IV  （Client加密时使用的初始化向量）　
Server Write IV  （Server加密时使用的初始化向量）
```


当然，使用AES-GCM作为对称加密组件，MAC Key和Encryption Key只需要一个就可以了。
　　握手生成的pre_master_secret只有48个字节，上述几个加密参数的长度加起来肯定就超过48字节了，所以需要一个函数来把48字节延长到需要的长度，在密码学中专门有一类算法承担密钥扩展的功能，称为密钥衍生函数（Key Derivation Function）。TLS1.3使用的HKDF做密钥扩展，mmtls也是选用的HKDF做密钥扩展。
　　在前文中，我用pre_master_secret代表握手协商得到的对称密钥，在TLS1.2之前确实叫这个名字，但是在TLS1.3中由于需要支持0-RTT握手，协商出来的对称密钥可能会有两个，分别称为Static Secret(SS)和Ephemeral Secret（ES）。从TLS1.3文档中截取一张图进行说明一下：
  
  ![image](https://user-images.githubusercontent.com/8308226/234161990-9965d48a-17bb-4c1d-a0f9-6563390b1412.png)


　　上图中Key Exchange就是代表握手的方式，在1-RTT ECDHE握手方式下
  
  ```
  ES=SS = ECDH_Compute_Key(svr_pub_key, cli_pri_key);
  ```
  
  　在0-RTT ECDH下,
   
   ```
   SS=ECDH_Compute_Key(static_svr_pub_key, cli_pri_key), 
ES=ECDH_Compute_Key(svr_pub_Key, cli_pri_Key);
   ```
   
   在0-RTT/1-RTT PSK握手下，
   
   ```
   ES=SS=pre-shared key;
   ```
   
   在0-RTT PSK-ECDHE握手下，
   ```
   SS=pre-shared key，
ES=ECDH_Compute_Key(svr_pub_key, cli_pri_key);
   ```
   
   　　前面说过mmtls使用的密钥扩展组件为HKDF，该组件定义了两个函数来保证扩展出来的密钥具有伪随机性、唯一性、不能逆推原密钥、可扩展任意长度密钥。两个函数分别是：
     
     ```
     HKDF-Extract( salt, initial-keying-material )
     ```
     
     　该函数的作用是对initial-keying-material进行处理，保证它的熵均匀分别，足够的伪随机。
      
      ```
      HKDF-Expand( pseudorandom key, info, out_key_length )
      ```
      
      
      　参数pseudorandom key是已经足够伪随机的密钥扩展材料，HKDF-Extract的返回值可以作为pseudorandom key，info用来区分扩展出来的Key是做什么用，out_key_length表示希望扩展输出的key有多长。mmtls最终使用的密钥是有HKDF-Expand扩展出来的。mmtls把info参数分为：length，label，handshake_hash。其中length等于out_key_length，label是标记密钥用途的固定字符串，handshake_hash表示握手消息的hash值，这样扩展出来的密钥保证连接内唯一。
       
       ![image](https://user-images.githubusercontent.com/8308226/234162280-f526093e-14d7-40ca-86ae-77848939f98e.png)
       
 TLS1.3草案中定义的密钥扩展方式比较繁琐，如上图所示。为了得到最终认证加密的对称密钥，需要做3次HDKF-Extract和4次HKDF-Expand操作，实际测试发现，这种密钥扩展方式对性能影响是很大的，尤其在PSK握手情况（PSK握手没有非对称运算）这种密钥扩展方式成为性能瓶颈。TLS1.3之所以把密钥扩展搞这么复杂，本质上还是因为TLS1.3是一个通用的协议框架，具体的协商算法是可以选择的，在有些协商算法下，协商出来的pre_master_key（SS和ES）就不满足某些特性（如随机性不够），因此为了保证无论选择什么协商算法，用它来进行通信都是安全的，TLS1.3就在密钥扩展上做了额外的工作。而mmtls没有TLS1.3这种包袱，可以针对微信自己的网络通信特点进行优化（前面在握手方式选择上就有体现）。mmtls在不降低安全性的前提下，对TLS1.3的密钥扩展做了精简，使得性能上较TLS1.3的密钥扩展方式有明显提升。
　　在mmtls中，pre_master_key(SS和ES)经过密钥扩展，得到了一个长度为2*enc_key_length+2*iv_length的一段buffer，用key_block表示，其中：
  
  ```
  client_write_key = key_block[0...enc_key_length-1]
client_write_key = key_block[enc_key_length...2*enc_key_length-1]
client_write_IV  = key_block[2*enc_key_length...2*enc_key_length+iv_length-1]
server_write_IV  = key_block[2*enc_key_length+iv_length...2*enc_key_length+2*iv_length-1]
  ```
  
  防重放：
AES-GCM  nonce（随机数），认证成功即可。


client端 verify_pub_key 如何更新的问题？？
* Verify_Key如何下发给客户端？
　　这实际上是公钥派发的问题，TLS是使用证书链的方式来派发公钥（证书），对于微信来说，如果使用证书链的方式来派发Server的公钥（证书），无论自建Root CA还是从CA处申请证书，都会增加成本且在验签过程中会存在额外的资源消耗。由于客户端是由我们自己发布的，我们可以将verify_key直接内置在客户端，这样就避免证书链验证带来的时间消耗以及证书链传输带来的带宽消耗。
  
  server端
  
  ![image](https://user-images.githubusercontent.com/8308226/234162401-d630b188-b512-4f18-9224-89b684c8145e.png)
  
  参考资料：
1、https://yqf3139.github.io/2015/12/13/high-perf-network-in-chrome-trans/

![image](https://user-images.githubusercontent.com/8308226/234162488-cfb26107-4044-4455-a332-46ae04a57ce9.png)


2、https://mp.weixin.qq.com/s?__biz=MzAwNDY1ODY2OQ==&mid=2649286266&idx=1&sn=f5d049033e251cccc22e163532355ddf&scene=0&key=b28b03434249256b2a5d4fdf323a185a798eaf972317ca3a47ef060d35c5cd8a4ae35715466d5bb5a558e424d20bef6c&ascene=0&uin=Mjc3OTU3Nzk1&devicetype=iMac+MacBookPro10%2C1+OSX+OSX+10.10.5+build%2814F1713%29&version=11020201&pass_ticket=8lpzOjRJO3IS%2BmKcvsqRN%2FlzlWyR2q2fmKv15GKO2PPYAKDGPXDhyfntueC4bIod



      
