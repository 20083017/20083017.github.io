
## Authentication failed
在 Ubuntu 上执行升级命令时提示以下报错   
```
# do-release-upgrade
Checking for a new Ubuntu release
Get:1 Upgrade tool signature [1,554 B]                                                                                
Get:2 Upgrade tool [1,319 kB]                                                                                         
Fetched 1,320 kB in 0s (0 B/s)                                                                                        
authenticate 'focal.tar.gz' against 'focal.tar.gz.gpg' 
Authentication failed
Authenticating the upgrade failed. There may be a problem with the network or with the server.
```
此问题一般是系统密钥出错导致的，因此重新安装即可解决。   
```
sudo apt install --reinstall ubuntu-keyring
```


##
apt-get update failed because certificate verification failed because handshake failed on nodesource
```
sudo apt install ca-certificates
```
