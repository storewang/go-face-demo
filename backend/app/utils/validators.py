import imghdr
import re
from pathlib import Path
from typing import Optional


# 最大文件大小: 5MB
MAX_FILE_SIZE = 5 * 1024 * 1024

# 最小图片尺寸
MIN_WIDTH = 100
MIN_HEIGHT = 100

# 允许的图片类型
ALLOWED_IMAGE_TYPES = {"jpeg", "png"}


def validate_image(file_bytes: bytes, filename: str) -> str:
    """
    校验上传的图片文件
    
    检查项:
    - 文件大小不超过5MB
    - 真实图片类型为JPEG或PNG
    - 图片尺寸至少100x100
    
    Args:
        file_bytes: 文件字节内容
        filename: 原始文件名
        
    Returns:
        空字符串表示校验通过，否则返回错误信息
    """
    if len(file_bytes) > MAX_FILE_SIZE:
        return f"文件大小超过限制(最大5MB): {len(file_bytes) / 1024 / 1024:.2f}MB"

    actual_type = imghdr.what(None, file_bytes)
    if actual_type is None:
        return "无法识别图片格式，请上传JPEG或PNG格式图片"

    if actual_type not in ALLOWED_IMAGE_TYPES:
        return f"不支持的图片格式: {actual_type}，仅支持JPEG和PNG"

    try:
        import numpy as np
        import cv2
        nparr = np.frombuffer(file_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return "无法解码图片文件"

        height, width = img.shape[:2]
        if width < MIN_WIDTH or height < MIN_HEIGHT:
            return f"图片尺寸过小(最小{MIN_WIDTH}x{MIN_HEIGHT}): {width}x{height}"
    except Exception:
        return "图片处理失败"

    return ""


def sanitize_filename(filename: str) -> str:
    """
    清理文件名，防止路径穿越攻击
    
    处理:
    - 移除目录遍历字符(.., /, \\)
    - 移除非安全字符
    - 限制文件名长度
    
    Args:
        filename: 原始文件名
        
    Returns:
        清理后的安全文件名
    """
    if not filename:
        return "unnamed"

    # 移除路径分隔符和目录遍历字符
    filename = re.sub(r'[\\/]+', '', filename)
    filename = re.sub(r'\.\.+', '', filename)
    
    # 只保留字母、数字、点、下划线、短横线
    filename = re.sub(r'[^\w\-.]', '_', filename)
    
    # 限制长度，防止过长文件名
    max_length = 100
    if len(filename) > max_length:
        name, ext = Path(filename).stem, Path(filename).suffix
        filename = name[:max_length - len(ext)] + ext

    # 确保文件名不以点开头(防止隐藏文件)
    if filename.startswith('.'):
        filename = '_' + filename[1:]

    return filename or "unnamed"
