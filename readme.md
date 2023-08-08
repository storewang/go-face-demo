

### 静态图像人脸识别
我们用到的就是 go-face 这个库。该库利用 dlib 去实现人脸识别，一个很受欢迎的机器学习工具集，它可以说是人脸识别中使用最多的软件包之一。在产学界有广泛应用，涵盖了机器人学，嵌入式设备，移动设备等等。在它官网的文档中提到在 Wild 基准测试中识别标记面部的准确度达到惊人的 99.4%，这也说明为什么它能得到广泛的应用。
在我们开始码代码之前，首先需要安装 dlib。

```shell
sudo apt-get install libdlib-dev libblas-dev liblapack-dev libjpeg-turbo8-dev
```

### 遇到的问题
> 编译时遇到: /usr/bin/ld: cannot find -lcblas

需要安装libatlas-base-dev包:
```shell
sudo apt-get install libatlas-base-dev
```