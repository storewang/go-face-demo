package server

import (
	"log"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
)

func HandleChart(c *gin.Context) {
	msg := c.DefaultQuery("msg", "hello")
	msgChan := make(chan string, 10)
	errChan := make(chan error, 10)
	msgReply := ""
	// 接入chatGPT处理文本消息
	go GeminiCompletions(msg, msgChan, errChan)

	// 处理
	select {
	case msgReply = <-msgChan:
	case errReply := <-errChan:
		log.Printf("get reply message error:%v\n", errReply)
		msgReply = "小安开小差了，请你稍后再次请求~"
	case <-time.After(time.Second * 4):
		msgReply = "网络交通堵塞~请你5s后复制粘贴上次问题再次询问获取答案，在这之前请不要重复提问哦~谢谢理解"
	}
	c.String(http.StatusOK, msgReply)
}
