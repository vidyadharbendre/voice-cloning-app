"""
Background Tasks Module
Handles asynchronous background tasks for cleanup, monitoring, and maintenance
"""
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Callable, Any
import shutil

logger = logging.getLogger(__name__)


class BackgroundTasks:
    """Manager for background tasks"""
    
    def __init__(self):
        self.tasks = []
        self.running = False
        
    async def start(self):
        """Start all background tasks"""
        if self.running:
            logger.warning("Background tasks already running")
            return
            
        self.running = True
        logger.info("Starting background tasks")
        
        # Start cleanup task
        cleanup_task = asyncio.create_task(self.periodic_cleanup())
        self.tasks.append(cleanup_task)
        
        # Start health check task
        health_task = asyncio.create_task(self.periodic_health_check())
        self.tasks.append(health_task)
        
        logger.info(f"Started {len(self.tasks)} background tasks")
        
    async def stop(self):
        """Stop all background tasks"""
        if not self.running:
            return
            
        logger.info("Stopping background tasks")
        self.running = False
        
        for task in self.tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
                
        self.tasks.clear()
        logger.info("Background tasks stopped")
        
    async def periodic_cleanup(self, interval: int = 3600):
        """
        Periodically clean up old files
        
        Args:
            interval: Cleanup interval in seconds (default: 1 hour)
        """
        logger.info(f"Starting periodic cleanup (interval: {interval}s)")
        
        while self.running:
            try:
                await asyncio.sleep(interval)
                
                if not self.running:
                    break
                    
                logger.info("Running scheduled cleanup")
                await self.cleanup_old_files()
                
            except asyncio.CancelledError:
                logger.info("Cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}", exc_info=True)
                # Continue running despite errors
                
    async def cleanup_old_files(
        self, 
        max_age_hours: int = 24,
        directories: Optional[list] = None
    ):
        """
        Clean up files older than max_age_hours
        
        Args:
            max_age_hours: Maximum age of files to keep (in hours)
            directories: List of directories to clean (default: temp and output dirs)
        """
        if directories is None:
            directories = ["temp", "output", "uploads"]
            
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        total_deleted = 0
        total_size = 0
        
        for dir_name in directories:
            dir_path = Path(dir_name)
            
            if not dir_path.exists():
                logger.debug(f"Directory {dir_name} does not exist, skipping")
                continue
                
            try:
                for file_path in dir_path.rglob("*"):
                    if not file_path.is_file():
                        continue
                        
                    # Check file age
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    
                    if file_mtime < cutoff_time:
                        try:
                            file_size = file_path.stat().st_size
                            file_path.unlink()
                            total_deleted += 1
                            total_size += file_size
                            logger.debug(f"Deleted old file: {file_path}")
                        except Exception as e:
                            logger.warning(f"Failed to delete {file_path}: {e}")
                            
            except Exception as e:
                logger.error(f"Error cleaning directory {dir_name}: {e}")
                
        if total_deleted > 0:
            size_mb = total_size / (1024 * 1024)
            logger.info(
                f"Cleanup completed: deleted {total_deleted} files, "
                f"freed {size_mb:.2f} MB"
            )
        else:
            logger.debug("Cleanup completed: no old files found")
            
    async def periodic_health_check(self, interval: int = 300):
        """
        Periodically check system health
        
        Args:
            interval: Health check interval in seconds (default: 5 minutes)
        """
        logger.info(f"Starting periodic health check (interval: {interval}s)")
        
        while self.running:
            try:
                await asyncio.sleep(interval)
                
                if not self.running:
                    break
                    
                await self.check_system_health()
                
            except asyncio.CancelledError:
                logger.info("Health check task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in health check task: {e}", exc_info=True)
                
    async def check_system_health(self):
        """Check system health metrics"""
        try:
            import psutil
            
            # Check CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Check memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Check disk usage
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            # Log warnings if thresholds exceeded
            if cpu_percent > 90:
                logger.warning(f"High CPU usage: {cpu_percent}%")
                
            if memory_percent > 90:
                logger.warning(f"High memory usage: {memory_percent}%")
                
            if disk_percent > 90:
                logger.warning(f"High disk usage: {disk_percent}%")
                
            logger.debug(
                f"System health - CPU: {cpu_percent}%, "
                f"Memory: {memory_percent}%, "
                f"Disk: {disk_percent}%"
            )
            
        except ImportError:
            logger.debug("psutil not available, skipping health check")
        except Exception as e:
            logger.error(f"Error checking system health: {e}")
            
    async def run_task(
        self, 
        func: Callable, 
        *args, 
        delay: int = 0,
        **kwargs
    ):
        """
        Run a function as a background task
        
        Args:
            func: Function to run
            *args: Positional arguments for the function
            delay: Delay before running (in seconds)
            **kwargs: Keyword arguments for the function
        """
        async def _task():
            try:
                if delay > 0:
                    await asyncio.sleep(delay)
                    
                if asyncio.iscoroutinefunction(func):
                    await func(*args, **kwargs)
                else:
                    func(*args, **kwargs)
                    
            except Exception as e:
                logger.error(f"Error in background task: {e}", exc_info=True)
                
        task = asyncio.create_task(_task())
        return task
        
    async def schedule_file_deletion(
        self, 
        file_path: Path, 
        delay: int = 3600
    ):
        """
        Schedule a file for deletion after a delay
        
        Args:
            file_path: Path to file to delete
            delay: Delay before deletion (in seconds, default: 1 hour)
        """
        logger.info(f"Scheduled deletion of {file_path} in {delay}s")
        
        async def _delete():
            try:
                await asyncio.sleep(delay)
                
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Deleted scheduled file: {file_path}")
                else:
                    logger.debug(f"Scheduled file already deleted: {file_path}")
                    
            except Exception as e:
                logger.error(f"Error deleting scheduled file {file_path}: {e}")
                
        task = asyncio.create_task(_delete())
        return task


# Global instance
background_tasks = BackgroundTasks()


# Convenience functions
async def cleanup_old_files(*args, **kwargs):
    """Clean up old files"""
    await background_tasks.cleanup_old_files(*args, **kwargs)


async def schedule_file_deletion(file_path: Path, delay: int = 3600):
    """Schedule a file for deletion"""
    await background_tasks.schedule_file_deletion(file_path, delay)


def start_background_tasks():
    """Start background tasks (sync wrapper)"""
    asyncio.create_task(background_tasks.start())


async def stop_background_tasks():
    """Stop background tasks"""
    await background_tasks.stop()