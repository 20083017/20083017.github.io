
### 软连接
```
New-Item -ItemType SymbolicLink `
		 -Path D:\ `
		 -Name nvim `
		 -Target C:\ProgramData\scoop\apps\neovim\current\bin\nvim.exe

```

### 重启powershell 生效环境变量
```
Start-Process powershell -ArgumentList "-NoExit"
```

### vcpkg 安装

gitkraken

nodejs

git

cmake

ninja

### vcpkg 配置

```
﻿{
  "environments": [
    {
      "environment": "VS_14_x86",
      "VC14INSTALLDIR": "C:\\Program Files (x86)\\Microsoft Visual Studio 14.0\\VC",
      "WINDOWSKITS": "C:\\Program Files (x86)\\Windows Kits",
      "WINDOWSKITS_VERSION": "10.0.17134.0",
      "PATH": "${env.PATH};${env.VC14INSTALLDIR}bin;${env.WINDOWSKITS}\\10\\bin\\x86",
      "INCLUDE": "${env.VC14INSTALLDIR}\\INCLUDE;${env.VC14INSTALLDIR}\\ATLMFC\\INCLUDE;${env.WINDOWSKITS}\\10\\include\\${env.WINDOWSKITS_VERSION}\\ucrt;${env.WINDOWSKITS}\\NETFXSDK\\4.6.1\\include\\um;${env.WINDOWSKITS}\\10\\include\\${env.WINDOWSKITS_VERSION}\\shared;${env.WINDOWSKITS}\\10\\include\\${env.WINDOWSKITS_VERSION}\\um;${env.WINDOWSKITS}\\10\\include\\${env.WINDOWSKITS_VERSION}\\winrt;",
      "LIB": "${env.VC14INSTALLDIR}\\LIB;${env.VC14INSTALLDIR}\\ATLMFC\\LIB;${env.WINDOWSKITS}\\10\\lib\\${env.WINDOWSKITS_VERSION}\\ucrt\\x86;${env.WINDOWSKITS}\\NETFXSDK\\4.6.1\\lib\\um\\x86;${env.WINDOWSKITS}\\10\\lib\\${env.WINDOWSKITS_VERSION}\\um\\x86;",
      "LIBPATH": "C:\\windows\\Microsoft.NET\\Framework\\v4.0.30319;${env.VC14INSTALLDIR}\\LIB;${env.VC14INSTALLDIR}\\ATLMFC\\LIB;${env.WINDOWSKITS}\\10\\UnionMetadata;${env.WINDOWSKITS}\\10\\References;C:\\Program Files (x86)\\Microsoft SDKs\\Windows Kits\\10\\ExtensionSDKs\\Microsoft.VCLibs\\14.0\\References\\CommonConfiguration\\neutral;"
    }
  ],
  "configurations": [
    {
      "name": "x86-Debug",
      "generator": "Ninja",
      "configurationType": "Debug",
      "inheritEnvironments": [ "VS_14_x86" ],
      "buildRoot": "${env.USERPROFILE}\\CMakeBuilds\\${workspaceHash}\\build\\${name}",
      "installRoot": "${env.USERPROFILE}\\CMakeBuilds\\${workspaceHash}\\install\\${name}",
      "cmakeCommandArgs": "",
      "buildCommandArgs": "-v",
      "ctestCommandArgs": ""

    }
  ]
}
```


