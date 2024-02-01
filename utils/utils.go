package utils

import (
	"encoding/json"
	"fmt"
	"go-demo/config"
	"io/ioutil"
	"math/rand"
	"net/http"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

var authorizations = make(map[string]Authorization)

type Authorization struct {
	Token     string `json:"token"`
	ExpiresAt int64  `json:"expires_at"`
}

func GetAuthorization(c *gin.Context) bool {
	copilotToken := strings.TrimPrefix(c.GetHeader("Authorization"), "Bearer ")
	if copilotToken == "" {
		c.JSON(http.StatusUnauthorized, gin.H{
			"message": "Unauthorized",
		})
		return false
	}
	println("token: ", copilotToken)
	// Obtain the Authorization from the GitHub Copilot Plugin Token.
	return getAuthorizationFromToken(c, copilotToken)
}

func setAuthorizationToCache(copilotToken string, authorization Authorization) {
	authorizations[copilotToken] = authorization
}

func getAuthorizationFromCache(copilotToken string) *Authorization {
	extraTime := rand.Intn(600) + 300
	if authorization, ok := authorizations[copilotToken]; ok {
		if authorization.ExpiresAt > time.Now().Unix()+int64(extraTime) {
			return &authorization
		}
	}
	return &Authorization{}
}

func getAuthorizationFromToken(c *gin.Context, copilotToken string) bool {
	authorization := getAuthorizationFromCache(copilotToken)
	if authorization.Token == "" {
		getAuthorizationUrl := "https://api.github.com/copilot_internal/v2/token"
		client := &http.Client{}
		req, _ := http.NewRequest("GET", getAuthorizationUrl, nil)
		req.Header.Set("Authorization", "token "+copilotToken)
		response, err := client.Do(req)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error(), "code": response.StatusCode})
			return false
		}
		if response.StatusCode != 200 {
			body, _ := ioutil.ReadAll(response.Body)
			c.JSON(response.StatusCode, gin.H{"error": string(body), "code": response.StatusCode})
			return false
		}
		println("123")
		defer response.Body.Close()

		body, _ := ioutil.ReadAll(response.Body)

		newAuthorization := &Authorization{}
		if err = json.Unmarshal(body, &newAuthorization); err != nil {
			fmt.Println("err", err)
		}
		authorization.Token = newAuthorization.Token
		setAuthorizationToCache(copilotToken, *newAuthorization)
	}
	config.Authorization = authorization.Token
	return true
}
