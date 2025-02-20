package grcode

import (
	"fmt"
	"image/png"
	"os"

	"github.com/boombuler/barcode"
	"github.com/boombuler/barcode/qr"
	"github.com/tuotoo/qrcode"
)

type QrcodeTool struct {
	Content  string
	Qrcode   string
	FileName string
}

func (q *QrcodeTool) Encode(w int, h int) error {
	// 创建barcode
	qrCode, err := qr.Encode(q.Content, qr.M, qr.Auto)
	if err != nil {
		return err
	}
	// 设置图片像素大小
	qrCode, err = barcode.Scale(qrCode, w, h)
	if err != nil {
		return err
	}
	// 创建一个要输出数据的文件
	file, _ := os.Create(q.FileName)
	defer file.Close()
	// 将二维码编码为png图片
	png.Encode(file, qrCode)

	q.Qrcode = file.Name()
	return nil
}

func (q *QrcodeTool) Decode() error {
	fi, err := os.Open(q.Qrcode)
	if err != nil {
		fmt.Println(err)
		return err
	}
	defer fi.Close()

	qrmatrix, err := qrcode.Decode(fi)
	if err != nil {
		fmt.Println(err)
		return err
	}

	q.Content = qrmatrix.Content
	return nil
}
