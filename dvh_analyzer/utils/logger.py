"""
Logging system for DICOM processing tools using loguru.
"""
import os
import sys
from loguru import logger

class G4RTLogger:
    
    def __init__(self, name="DICOM", log_dir=None):
        """
        Initialize logger with name and optional log directory
        
        Args:
            name (str): Name for the logger
            log_dir (str): Directory for log files (defaults to ./logs in cwd)
        """
        self.name = name
        
        if log_dir is None:
            log_dir = os.path.join(os.getcwd(), "logs") 

        os.makedirs(log_dir, exist_ok=True)
        
        logger.remove()  
        
        format_str_console = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
        format_str_console += "<cyan>{extra[name]}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>"
        
        logger.add(
            sys.stderr,
            format=format_str_console,
            level="INFO" 
        )
        
        log_file_path = os.path.join(log_dir, f"{name.lower()}.log")
        format_str_file = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[name]}:{function}:{line} | {message}"
        
        logger.add(
            log_file_path,
            format=format_str_file,
            rotation="10 MB",    
            retention="1 week",  
            compression="zip",   
            level="DEBUG",       
            enqueue=True         
        )
        
        self.logger = logger.bind(name=self.name)
    
    def get_logger(self):
        """Get the configured logger instance."""
        return self.logger
    
    def set_level(self, level_console="INFO", level_file="DEBUG"):
        """
        Set logging levels for console and file handlers.
        Note: This method reconfigures all handlers.
        
        Args:
            level_console (str): Log level for console (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            level_file (str): Log level for file (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        logger.remove() 

        format_str_console = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
        format_str_console += "<cyan>{extra[name]}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>"
        logger.add(
            sys.stderr,
            format=format_str_console,
            level=level_console.upper()
        )
        
        current_log_dir = self.log_dir if hasattr(self, 'log_dir') and self.log_dir else os.path.join(os.getcwd(), "logs")
        os.makedirs(current_log_dir, exist_ok=True)
        log_file_path = os.path.join(current_log_dir, f"{self.name.lower()}.log")
        
        format_str_file = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[name]}:{function}:{line} | {message}"
        logger.add(
            log_file_path,
            format=format_str_file,
            rotation="10 MB",
            retention="1 week",
            compression="zip",
            level=level_file.upper(),
            enqueue=True
        )
        
        self.logger = logger.bind(name=self.name)
        self.logger.info(f"Log levels reconfigured. Console: {level_console.upper()}, File: {level_file.upper()}")
        
        return self.logger

if __name__ == "__main__":
    app_logger_instance = G4RTLogger(name="MyDicomApp").get_logger()
    
    app_logger_instance.debug("To jest wiadomość debugowa.")
    app_logger_instance.info("To jest wiadomość informacyjna.")
    app_logger_instance.warning("To jest ostrzeżenie.")
    app_logger_instance.error("To jest błąd.")
    app_logger_instance.critical("To jest błąd krytyczny.")
