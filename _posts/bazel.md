

```
bazel build :protoc :protobuf --enable_bzlmod

依赖图
bazel mod graph --output graph --enable_bzlmod

 bazel build -c opt --copt '-fPIC' :protoc :protobuf --enable_bzlmod 
```
