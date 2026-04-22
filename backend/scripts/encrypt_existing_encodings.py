"""一次性脚本：加密现有的明文特征向量文件
使用BiometricCrypto对 encodings 目录中的 .npy 文件进行加密处理
使用方法: python scripts/encrypt_existing_encodings.py [--dry-run]
"""
import argparse
from pathlib import Path
import sys
import numpy as np
import logging

from app.utils.crypto import biometric_crypto

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main(dry_run: bool = False) -> int:
    enc_dir = Path("./data/faces/encodings")
    if not enc_dir.exists():
        logger.error("encodings_directory_not_found", path=str(enc_dir))
        return 1

    files = sorted(enc_dir.glob("*.npy"))
    if not files:
        logger.info("no_encoding_files_found", directory=str(enc_dir))
        return 0

    count = 0
    for f in files:
        try:
            with open(f, "rb") as fh:
                data = fh.read()
            # Encrypt the raw bytes
            encrypted = biometric_crypto.encrypt(data)
            if not dry_run:
                with open(f, "wb") as fw:
                    fw.write(encrypted)
            count += 1
            logger.info("encrypted_file", file=str(f), size=len(data))
        except Exception as e:
            logger.exception("failed_encrypt_file", file=str(f), error=str(e))
            continue

    logger.info("encryption_summary", files encrypted=count, total_files=len(files))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Encrypt existing encodings using BiometricCrypto")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", help="Do not write changes to disk")
    args = parser.parse_args()
    sys.exit(main(dry_run=args.dry_run))
