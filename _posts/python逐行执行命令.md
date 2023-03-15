```
#!/usr/bin/python3

import os
import re


f = open("shell_sql.txt")

line = f.readline()

uid_list = []

while line:
    #line = line.rstrip()
    #line = line.lstrip()
    #if line is not None:
    #    uid_list.append(int(line))
        #print(int(line))
    #line = f.readline()
    #print(int(line))
    os.system(line)
    line = f.readline()
f.close()
```
