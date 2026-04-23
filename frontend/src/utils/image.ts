export function base64ToFile(base64: string, filename: string): File {
  const arr = base64.split(',')
  const mime = arr[0].match(/:(.*?);/)?.[1] || 'image/jpeg'
  const bstr = atob(arr[1])
  const len = bstr.length
  const u8arr = new Uint8Array(len)

  for (let i = 0; i < len; i++) {
    u8arr[i] = bstr.charCodeAt(i)
  }

  return new File([u8arr], filename, { type: mime })
}

export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}
