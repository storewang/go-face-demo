package main

import (
	"encoding/base64"
	"fmt"
	"log"
	"net/http"
	"strings"

	"face_demo/balance"

	"github.com/Kagami/go-face"
	"github.com/SimonWang00/goeureka"
	"github.com/gin-gonic/gin"
)

const dataDir = "testdata"

const (
	modelDir  = dataDir + "/models"
	imagesDir = dataDir + "/images"
)

// 图片中的人名
var labels = []string{
	"萧敬腾",
	"周杰伦",
	"unknow",
	"王力宏",
	"陶喆",
	"林俊杰",
}

func main() {
	log.Println("Face Recoginition...")
	rec, err := face.NewRecognizer(modelDir)
	if err != nil {
		fmt.Println("cannot initialize recongnizer")
	}
	defer rec.Close()

	log.Println("Recognizer initialized")

	// 注册服务
	goeureka.RegisterClient("http://10.254.160.81:8080", "192.168.3.92", "go-test-01", "8088", "43", nil)

	ins, err := goeureka.GetServiceInstances("yuxiaor-server")
	if err != nil {
		fmt.Println("获取服务实例失败")
	}
	log.Println("获取服务实例====>")
	hosts := make([]string, 0)
	for _, svc := range ins {
		log.Println("=>id:", svc.InstanceId)
		log.Println("=>app:", svc.App)
		log.Println("=>host:", svc.HostName)
		log.Println("=>port:", svc.Port)
		log.Println("=>ip:", svc.IpAddr)
		log.Println("status:", svc.Status)
		host := fmt.Sprintf("%s%s%d", svc.IpAddr, ":", svc.Port.Port)

		hosts = append(hosts, host)
	}
	log.Println("获取服务实例<====", hosts)

	lb, err := balance.Build(balance.R2Balancer, hosts)
	if err != nil {
		log.Fatalf("初始化均衡负载器失败: %v", err)
	}

	// 调用该方法，传入路径。返回面部数量和任何错误
	faces, err := rec.RecognizeFile(imagesDir + "/men-faces.jpeg")
	if err != nil {
		log.Fatalf("无法识别: %v", err)
	}
	// 打印人脸数量
	log.Println("图片人脸数量: ", len(faces))

	// 根据样例生成模型数据
	var samples []face.Descriptor
	var peoples []int32
	for i, f := range faces {
		samples = append(samples, f.Descriptor)
		// 每张脸唯一 id
		peoples = append(peoples, int32(i))
	}

	// 传入样例到识别器
	rec.SetSamples(samples, peoples)

	// 初始化http server
	// 1. 创建路由
	r := gin.Default()
	// 2. 绑定路由规则，执行的函数
	r.GET("/", func(ctx *gin.Context) {
		host, _ := lb.Balance("")
		ctx.String(http.StatusOK, "Hello World!"+host)
	})
	r.GET("/info", func(ctx *gin.Context) {
		ctx.String(http.StatusOK, "Hello go-test-01!")
	})

	r.GET("/test", func(ctx *gin.Context) {
		faceName := RecognizePeople(rec, imagesDir+"/linjunjie.jpeg")
		ctx.String(http.StatusOK, faceName)
	})

	r.POST("/ver", func(ctx *gin.Context) {
		var img ImgVo
		if err := ctx.BindJSON(&img); err != nil {
			ctx.String(http.StatusBadRequest, err.Error())
		}
		idx := strings.Index(img.Img, "data:image/jpeg;base64")
		if idx > -1 {
			img.Img = strings.ReplaceAll(img.Img, "data:image/jpeg;base64,", "")
		}
		log.Println("idx:", idx)
		//log.Println("img:", img.Img)

		imgData, error := base64.StdEncoding.DecodeString(img.Img)
		if error != nil {
			ctx.String(http.StatusInternalServerError, err.Error())
		}
		faceName := RecognizePeople4Memory(rec, imgData)
		ctx.String(http.StatusOK, faceName)
	})

	// 3. 监听端口，默认8080
	r.Run(":8088")

	// 识别图片人脸
	//RecognizePeople(rec, imagesDir+"/jay.jpeg")
	//RecognizePeople(rec, imagesDir+"/linjunjie.jpeg")
	//RecognizePeople(rec, imagesDir+"/taozhe.jpeg")

}

func RecognizePeople(rec *face.Recognizer, file string) string {
	people, err := rec.RecognizeSingleFile(file)
	if err != nil {
		log.Fatalf("无法识别: %v", err)
		return "无法识别"
	}
	if people == nil {
		log.Fatalf("图片上不是一张脸")
		return "图片上不是一张脸"
	}
	peopleID := rec.Classify(people.Descriptor)
	if peopleID < 0 {
		log.Fatalf("无法区分")
		return "无法区分"
	}

	fmt.Println(peopleID)
	fmt.Println(labels[peopleID])

	return labels[peopleID]
}

func RecognizePeople4Memory(rec *face.Recognizer, img []byte) string {
	people, err := rec.RecognizeSingle(img)
	if err != nil {
		log.Println("无法识别: %v", err)
		return "无法识别"
	}
	if people == nil {
		log.Println("图片上不是一张脸")
		return "图片上不是一张脸"
	}
	peopleID := rec.Classify(people.Descriptor)
	if peopleID < 0 {
		log.Println("无法区分")
		return "无法区分"
	}

	fmt.Println(peopleID)
	fmt.Println(labels[peopleID])

	return labels[peopleID]
}
