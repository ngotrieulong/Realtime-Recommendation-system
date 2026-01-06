import logging
import sys
import json
from typing import Any

class JSONFormatter(logging.Formatter):
    """
    Formatter that outputs JSON strings after parsing the LogRecord.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra attributes set via "extra" kwarg
        if hasattr(record, "request_id"):
            log_obj["request_id"] = record.request_id # type: ignore
            
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_obj)

def setup_logging():
    """
    Configure root logger to output JSON to stdout.
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    handler = logging.StreamHandler(sys.stdout)
    formatter = JSONFormatter()
    handler.setFormatter(formatter)
    
    # Remove existing handlers to avoid duplicates (e.g. from Uvicorn)
    logger.handlers = []
    logger.addHandler(handler)
    
    # Configure Uvicorn access logs to use our JSON format too if desired
    # For now, we mainly control application logs.
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.access").propagate = True
