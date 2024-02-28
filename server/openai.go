package server

import (
	"context"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"strings"
	"time"

	"github.com/google/generative-ai-go/genai"
	"github.com/sashabaranov/go-openai"
	"github.com/sunanxiang/charlotter/cache"
	"github.com/sunanxiang/charlotter/config"
	"google.golang.org/api/option"
)

const qyapi string = "http://api.qingyunke.com/api.php?key=free&appid=0&msg="
const geminiApi string = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"

type qyapiResp struct {
	Code int    `json:"result"`
	Msg  string `json:"content"`
}

func Completions1(question string, msgChan chan string, errChan chan error) {
	resp, err := http.Get(qyapi + question)
	if err != nil {
		log.Printf("ChatCompletion error: %v", err)
		errChan <- err
		return
	}
	defer resp.Body.Close()
	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		log.Printf("读取Body失败 error: %v", err)
		errChan <- err
		return
	}
	log.Println(resp)
	var s qyapiResp
	err = json.Unmarshal(body, &s)

	if err != nil {
		log.Printf("json.Unmarshal error: %v", err)
		errChan <- err
		return
	}
	log.Println(s.Msg)
	//err = cache.GlobalCache.Replace(question, s.Msg, time.Minute*5)
	// if err != nil {
	// 	log.Printf("cache add error: %v", err)
	// 	errChan <- err
	// 	return
	// }
	msgChan <- s.Msg
}

func GeminiCompletions(question string, msgChan chan string, errChan chan error) {
	println("token:", config.GeminiToken)
	ctx := context.Background()
	client, err := genai.NewClient(ctx, option.WithAPIKey(config.GeminiToken))
	if err != nil {
		log.Printf("ChatCompletion error: %v", err)
		errChan <- err
	}
	defer client.Close()

	model := client.GenerativeModel("gemini-pro")
	resp, err := model.GenerateContent(ctx, genai.Text(question))
	if err != nil {
		log.Printf("ChatCompletion error: %v", err)
		errChan <- err
	}
	if len(resp.Candidates) != 1 {
		log.Printf("resp.Candidates.len: ", len(resp.Candidates))
		errChan <- err
	}
	parts := resp.Candidates[0].Content.Parts
	if len(parts) != 1 {
		log.Printf("resp.Candidates[0].Parts.len: ", len(parts))
		errChan <- err
	}

	var b strings.Builder
	fmt.Fprintf(&b, "%v", parts[0])
	log.Printf("response: ", b.String())
	// add response to cache
	err = cache.GlobalCache.Replace(question, b.String(), time.Minute*5)
	if err != nil {
		log.Printf("cache add error: %v", err)
	}

	msgChan <- b.String()
}

func Completions(question string, msgChan chan string, errChan chan error) {
	println("token:", config.OpenAiToken)
	client := openai.NewClient(config.OpenAiToken)
	resp, err := client.CreateChatCompletion(
		context.Background(),
		openai.ChatCompletionRequest{
			Model: openai.GPT3Dot5Turbo,
			Messages: []openai.ChatCompletionMessage{
				{
					Role:    openai.ChatMessageRoleUser,
					Content: question,
				},
			},
		},
	)

	if err != nil {
		log.Printf("ChatCompletion error: %v", err)
		errChan <- err
		return
	}

	err = cache.GlobalCache.Replace(question, resp.Choices[0].Message.Content, time.Minute*5)
	if err != nil {
		log.Printf("cache add error: %v", err)
	}

	msgChan <- resp.Choices[0].Message.Content
}
