import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DatabaseError(Exception):
    """データベース操作に関するエラー"""
    def __init__(self, message, original_error=None):
        super().__init__(message)
        self.original_error = original_error
        logger.error(f"Database Error: {message}")
        if original_error:
            logger.error(f"Original error: {original_error}")

class ValidationError(Exception):
    """バリデーションエラー"""
    def __init__(self, message):
        super().__init__(message)
        logger.warning(f"Validation Error: {message}")

class NotFoundError(Exception):
    """リソースが見つからない場合のエラー"""
    def __init__(self, message):
        super().__init__(message)
        logger.info(f"Not Found: {message}")