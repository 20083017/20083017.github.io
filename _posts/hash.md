

```
加密哈希算法
在安全方面应用主要体现在以下三个方面： （1) 文件校验 （2) 数字签名 （3) 鉴权协议
1、 MD5 MD5即Message-Digest Algorithm 5（信息-摘要算法5），用于确保信息传输完整一致。是计算机广泛使用的杂凑算法之一，主流编程语言普遍已有MD5实现。将数据（如汉字）运算为另一固定长度值，是杂凑算法的基础原理，MD5的前身有MD2、MD3和MD4。 MD5是输入不定长度信息，输出固定长度128-bits的算法。经过程序流程，生成四个32位数据，最后联合起来成为一个128-bits散列。基本方式为，求余、取余、调整长度、与链接变量进行循环运算。得出结果。 
MD5一度被广泛应用于安全领域。但是在2004年王小云教授公布了MD5、MD4、HAVAL-128、RIPEMD-128几个 Hash函数的碰撞。这是近年来密码学领域最具实质性的研究进展。使用他们的技术，在数个小时内就可以找到MD5碰撞。使本算法不再适合当前的安全环境。目前，MD5计算广泛应用于错误检查。例如在一些BitTorrent下载中，软件通过计算MD5和检验下载到的碎片的完整性。

2、SHA-1 SHA-1曾经在许多安全协议中广为使用，包括TLS和SSL、PGP、SSH、S/MIME和IPsec，曾被视为是MD5的后继者。 SHA-1是如今很常见的一种加密哈希算法，HTTPS传输和软件签名认证都很喜欢它，但它毕竟是诞生于1995年的老技术了(出自美国国安局NSA)，已经渐渐跟不上时代，被破解的速度也是越来越快。 微软在2013年的Windows 8系统里就改用了SHA-2，Google、Mozilla则宣布2017年1月1日起放弃SHA-1。 当然了，在普通民用场合，SHA-1还是可以继续用的，比如校验下载软件之类的，就像早已经被淘汰的MD5。

3、SHA-2 SHA-224、SHA-256、SHA-384，和SHA-512并称为SHA-2。 新的哈希函数并没有接受像SHA-1一样的公众密码社区做详细的检验，所以它们的密码安全性还不被大家广泛的信任。 虽然至今尚未出现对SHA-2有效的攻击，它的算法跟SHA-1基本上仍然相似；因此有些人开始发展其他替代的哈希算法。

4、SHA-3 SHA-3，之前名为Keccak算法，是一个加密杂凑算法。 由于对MD5出现成功的破解，以及对SHA-0和SHA-1出现理论上破解的方法，NIST感觉需要一个与之前算法不同的，可替换的加密杂凑算法，也就是现在的SHA-3。5、RIPEMD-160 RIPEMD-160 是一个 160 位加密哈希函数。 它旨在用于替代 128 位哈希函数 MD4、MD5 和 RIPEMD。 RIPEMD-160没有输入大小限制，在处理速度方面比SHA2慢。 安全性也没SHA-256和SHA-512好。

查找哈希算法
1、lookup3 Bob Jenkins在1997年发表了一篇关于哈希函数的文章《A hash function for hash Table lookup》，这篇文章自从发表以后现在网上有更多的扩展内容。这篇文章中，Bob广泛收录了很多已有的哈希函数，这其中也包括了他自己所谓的“lookup2”。随后在2006年，Bob发布了lookup3。 Bob很好的实现了散列的均匀分布，但是相对来说比较耗时，它有两个特性，1是具有抗篡改性，既更改输入参数的任何一位都将带来一半以上的位发生变化，2是具有可逆性，但是在逆运算时，它非常耗时。
2、Murmur3 murmurhash是 Austin Appleby于2008年创立的一种非加密哈希算法，适用于基于哈希进行查找的场景。murmurhash最新版本是MurMurHash3，支持32位、64位及128位值的产生。 MurMur经常用在分布式环境中，比如Hadoop，其特点是高效快速，但是缺点是分布不是很均匀。
3、FNV-1a FNV又称Fowler/Noll/Vo，来自3位算法设计者的名字（Glenn Fowler、Landon Curt Noll和Phong Vo）。FNV有3种：FNV-0（已过时）、FNV-1、FNV-1a，后两者的差别极小。FNV-1a生成的哈希值有几个特点：无符号整形；哈希值的bits数，是2的n次方（32, 64, 128, 256, 512, 1024），通常32 bits就能满足大多数应用。
4、CityHash 2011年，google发布CityHash（由Geoff Pike 和Jyrki Alakuijala编写）,其性能好于MurmurHash。 但后来CityHash的哈希算法被发现容易受到针对算法漏洞的攻击，该漏洞允许多个哈希冲突发生。
5、SpookyHash 又是Bob Jenkins哈希牛人的一巨作，于2011年发布的新哈希函数性能优于MurmurHash，但是只给出了128位的输出，后面发布了SpookyHash V2，提供了64位输出。
6、FarmHash FarmHash也是google发布的，FarmHash从CityHash继承了许多技巧和技术，是它的后继。FarmHash声称从多个方面改进了CityHash。
7、xxhash xxhash由Yann Collet发表，http://cyan4973.github.io/xxHash/ 这是它的官网，据说性能很好，似乎被很多开源项目使用，Bloom Filter的首选。
```
