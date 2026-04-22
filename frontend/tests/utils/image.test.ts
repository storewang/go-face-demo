/**
 * image.test.ts — 图像处理工具测试
 */
import { describe, it, expect } from 'vitest'
import { base64ToFile, fileToBase64 } from '@/utils/image'

describe('base64ToFile', () => {
  it('应将 base64 字符串转换为 File 对象', () => {
    const base64 = 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AVN//2Q=='
    const file = base64ToFile(base64, 'test.jpg')

    expect(file).toBeInstanceOf(File)
    expect(file.name).toBe('test.jpg')
    expect(file.type).toBe('image/jpeg')
    expect(file.size).toBeGreaterThan(0)
  })

  it('应处理 PNG 格式', () => {
    const base64 = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
    const file = base64ToFile(base64, 'pixel.png')
    expect(file.type).toBe('image/png')
  })
})

describe('fileToBase64', () => {
  it('应将 File 转换为 base64 字符串', async () => {
    const file = new File(['hello'], 'test.txt', { type: 'text/plain' })
    const result = await fileToBase64(file)

    expect(result).toContain('data:text/plain;base64,')
    expect(typeof result).toBe('string')
  })

  it('应处理二进制文件', async () => {
    const uint8 = new Uint8Array([0x89, 0x50, 0x4e, 0x47])
    const file = new File([uint8], 'test.png', { type: 'image/png' })
    const result = await fileToBase64(file)

    expect(result).toContain('data:image/png;base64,')
  })
})
