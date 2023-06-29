
# mysql导出到文件

```
mysql -h   -P  -ub  -p'' -e "use bdim_roam; select id from _tablet_789" > 1.txt
```

### inner join
```
select * from im_msgroaming inner join im_user1 on im_msgroaming.uid1=im_user1.uid1 inner join im_user2 on im_msgroaming.uid2=im_user2.uid2;
```

# mysql 大表批量删除千万级数据
假设表的引擎是 Innodb， MySQL 5.7+   

删除一条记录，首先锁住这条记录，数据原有的被废弃，记录头发生变化，主要是打上了删除标记。也就是原有的数据 deleted_flag 变成 1，代表数据被删除。但是数据没有被清空，在新一行数据大小小于这一行的时候，可能会占用这一行。这样其实就是存储碎片。   
之后，相关数据的索引需要更新，清除这些数据。并且，会产生对应的 binlog 与 redolog 日志。 如果 delete 的数据是大量的数据，则会：   

如果不加 limit 则会由于需要更新大量数据，从而索引失效变成全扫描导致锁表，同时由于修改大量的索引，产生大量的日志，导致这个更新会有很长时间，锁表锁很长时间，期间这个表无法处理线上业务。   
由于产生了大量 binlog 导致主从同步压力变大   
由于标记删除产生了大量的存储碎片。由于 MySQL 是按页加载数据，这些存储碎片不仅大量增加了随机读取的次数，并且让页命中率降低，导致页交换增多。   
由于产生了大量日志，我们可以看到这张表的占用空间大大增高。   

解决方案-1
```
我们很容易想到，在 delete 后加上 limit 限制控制其数量，这个数量让他会走索引，从而不会锁整个表。   
但是，存储碎片，主从同步，占用空间的问题并没有解决。可以在删除完成后，通过如下语句，重建表：   
alter table 你的表 engine=InnoDB, ALGORITHM=INPLACE, LOCK=NONE;   
注意这句话其实就是重建你的表，虽然你的表的引擎已经是 innodb 了，加上后面的, ALGORITHM=INPLACE, LOCK=NONE 可以不用锁表就重建表。
```
解决方案-2
还有一种方案是，新建一张同样结构的表，在原有表上加上触发器：   
```
create trigger person_trigger_update AFTER UPDATE on 原有表 for each row 
begin set @x = "trigger UPDATE";
Replace into 新表 SELECT * from 原有表 where 新表.id = 原有表.id;
END IF;
end;
```

