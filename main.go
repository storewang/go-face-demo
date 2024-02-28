package main

import (
	"github.com/gin-gonic/gin"
	"github.com/sunanxiang/charlotter/cache"
	"github.com/sunanxiang/charlotter/server"
)

func main() {
	router := gin.New()
	router.POST("/wx/mp/callback", server.HandleWechat)
	router.GET("/wx/mp/callback", server.Verify)
	router.GET("/test", server.HandleChart)

	cache.Init()
	// 运行服务器
	router.Run(":8080")
}
