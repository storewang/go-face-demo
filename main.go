package main

import (
	//"github.com/gin-gonic/gin"
	"fmt"
	"log"
	"os/exec"

	"github.com/atotto/clipboard"
	ocr "github.com/ranghetto/go_ocr_space"
)

func main() {
	// 本地需要安装gnome-screenshot: sudo apt install gnome-screenshot
	// K88900046488957
	apiKey := "K88900046488957"
	screenShotFile := "/home/shitou/图片/screenShot/test.png"
	config := ocr.InitConfig(apiKey, "chs", ocr.OCREngine2)
	// 调用gnome-screenshot进行截图
	cmd := exec.Command("gnome-screenshot", "-a", "-f", screenShotFile)
	err := cmd.Run()
	if err != nil {
		fmt.Println(err)
	} else {
		// 调用图片文字识别ocr
		result, err := config.ParseFromLocal(screenShotFile)
		if err != nil {
			fmt.Println(err)
		}
		fmt.Println(result.JustText())
		// 写入粘贴板中
		clipboard.WriteAll(result.JustText())
	}
	//result, err := config.ParseFromUrl("https://www.azquotes.com/picture-quotes/quote-maybe-we-should-all-just-listen-to-records-and-quit-our-jobs-jack-white-81-40-26.jpg")
	//result, err := config.ParseFromLocal("/home/shitou/tttttttttttttttttt.png")
	//if err != nil {
	//	fmt.Println(err)
	//}
	//fmt.Println(result.JustText())

	text, err := clipboard.ReadAll() // 从粘贴板中读取全部内容
	if err != nil {
		log.Fatal(err)
	}
	//clipboard.ReadImage()
	fmt.Println("粘贴板中的数据为：", text)
	//router := gin.Default()
	//router.Use(handlers.CORSMiddleware())
	//router.POST("/v1/chat/completions", handlers.ChatCompletions)
	//router.GET("/v1/models", handlers.CreateMockModelsResponse)
	//router.NoRoute(func(c *gin.Context) {
	//	c.String(http.StatusMethodNotAllowed, "Method Not Allowed")
	//})
	//router.Run(":8866")
}
