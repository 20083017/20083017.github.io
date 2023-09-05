```
#!/bin/bash  
  
# 要采集的进程名称  
process_name="com.xiaomi.mi_connect_service"  
  
# 存储数据的数组  
data=()  
  
# 采集次数  
iterations=10  
  
# 采集间隔（秒）  
interval=3 
  
# 存储时间的数组  
timestamps=()  
  
# 采集meminfo  
function collect_meminfo() {  
    # 采集当前时间戳  
    timestamp=$(date +%s)  
    timestamps+=($timestamp)  
  
    # 采集特定进程的meminfo  
    #meminfo=$(adb shell dumpsys meminfo $process_name) 
    echo $meminfo 
    free=$(adb shell dumpsys meminfo $process_name | grep -i 'Dalvik Heap' | awk '{print $3}') 
    echo "free is ${free}}" 
    data+=($free)  
}  
  
# 绘制曲线  
function plot_curve() {  
    # 生成临时数据文件  
    temp_data_file=$(mktemp)  
    echo "Generating temporary data file: $temp_data_file"  
    echo -e "\n" >> $temp_data_file  
  
    # 将数据写入临时文件  
    for value in "${data[@]}"; do  
        echo "$value" >> $temp_data_file  
        echo -n "$value " >> $temp_data_file  
        echo -e "\n" >> $temp_data_file  
    done  
  
    # 生成绘图命令  
    plot_cmd="plot '$temp_data_file' with lines title 'Memory Usage'"  
    echo "Generating plot command: $plot_cmd"  
  
    # 执行绘图命令  
    gnuplot -persist <<< "$plot_cmd"  
  
    # 删除临时数据文件  
    rm $temp_data_file  
}  
  
# 循环采集数据并绘制曲线  
function collect_and_plot() {  
    echo "Collecting and plotting memory info for process: $process_name"  
    echo "Number of iterations: $iterations"  
    echo "Collection interval (seconds): $interval"  
    echo "Starting collection..."  
  
    for ((i=1; i<=$iterations; i++)); do  
        echo "Iteration $i..."  
        collect_meminfo 
        for element in "${data[@]}"  
        do  
          echo "$element"  
        done	
        plot_curve  
        sleep $interval  
    done  
}  
  
# 执行主函数  
collect_and_plot

```
