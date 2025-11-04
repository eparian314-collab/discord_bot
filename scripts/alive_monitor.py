#!/usr/bin/env python3
"""
Alive Monitor Watchdog for HippoBot.

Monitors bot health metrics and logs warnings if issues detected.
Can be run as a standalone process or integrated into the bot.
"""
from __future__ import annotations

import asyncio
import time
import psutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Add project to path if running standalone
import sys
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from discord_bot.core.engines.base.logging_utils import get_logger

logger = get_logger("alive_monitor")


class AliveMonitor:
    """Monitors bot health and performance."""

    def __init__(
        self,
        check_interval: int = 60,
        latency_threshold_ms: int = 1000,
        memory_threshold_mb: int = 500,
        task_threshold: int = 100,
    ):
        """Initialize alive monitor.
        
        Args:
            check_interval: Seconds between health checks
            latency_threshold_ms: Warning threshold for latency
            memory_threshold_mb: Warning threshold for memory usage
            task_threshold: Warning threshold for active tasks
        """
        self.check_interval = check_interval
        self.latency_threshold_ms = latency_threshold_ms
        self.memory_threshold_mb = memory_threshold_mb
        self.task_threshold = task_threshold
        
        self.process = psutil.Process()
        self.start_time = time.time()
        self.check_count = 0
        self.warning_count = 0
        self.error_count = 0
        
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def get_memory_usage_mb(self) -> float:
        """Get current memory usage in MB."""
        memory_info = self.process.memory_info()
        return memory_info.rss / 1024 / 1024

    def get_active_tasks(self) -> int:
        """Get count of active asyncio tasks."""
        all_tasks = asyncio.all_tasks()
        return len([t for t in all_tasks if not t.done()])

    def get_uptime_seconds(self) -> float:
        """Get uptime in seconds."""
        return time.time() - self.start_time

    async def check_health(self, bot=None) -> dict:
        """Perform health check and return metrics.
        
        Args:
            bot: Optional discord bot instance for latency check
            
        Returns:
            dict: Health metrics
        """
        self.check_count += 1
        
        metrics = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "check_number": self.check_count,
            "uptime_seconds": self.get_uptime_seconds(),
            "memory_mb": self.get_memory_usage_mb(),
            "active_tasks": self.get_active_tasks(),
            "warnings": [],
            "status": "healthy",
        }
        
        # Check bot latency if available
        if bot:
            latency_ms = round(bot.latency * 1000, 2)
            metrics["latency_ms"] = latency_ms
            
            if latency_ms > self.latency_threshold_ms:
                warning = f"High latency: {latency_ms}ms (threshold: {self.latency_threshold_ms}ms)"
                metrics["warnings"].append(warning)
                logger.warning(warning)
                self.warning_count += 1
        
        # Check memory usage
        if metrics["memory_mb"] > self.memory_threshold_mb:
            warning = f"High memory usage: {metrics['memory_mb']:.1f}MB (threshold: {self.memory_threshold_mb}MB)"
            metrics["warnings"].append(warning)
            logger.warning(warning)
            self.warning_count += 1
        
        # Check task count
        if metrics["active_tasks"] > self.task_threshold:
            warning = f"High task count: {metrics['active_tasks']} (threshold: {self.task_threshold})"
            metrics["warnings"].append(warning)
            logger.warning(warning)
            self.warning_count += 1
        
        # Update status
        if len(metrics["warnings"]) > 0:
            metrics["status"] = "degraded"
            if len(metrics["warnings"]) >= 3:
                metrics["status"] = "critical"
                self.error_count += 1
        
        # Log summary
        if metrics["status"] == "healthy":
            logger.debug(
                "Health check #%d: OK (mem: %.1fMB, tasks: %d)",
                self.check_count,
                metrics["memory_mb"],
                metrics["active_tasks"]
            )
        else:
            logger.warning(
                "Health check #%d: %s - %d warnings",
                self.check_count,
                metrics["status"].upper(),
                len(metrics["warnings"])
            )
        
        return metrics

    async def monitor_loop(self, bot=None) -> None:
        """Run continuous monitoring loop.
        
        Args:
            bot: Optional discord bot instance
        """
        logger.info("Starting alive monitor (interval: %ds)", self.check_interval)
        self._running = True
        
        while self._running:
            try:
                await self.check_health(bot)
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                logger.info("Alive monitor cancelled")
                break
            except Exception as e:
                logger.error("Error in monitoring loop: %s", e, exc_info=True)
                self.error_count += 1
                await asyncio.sleep(self.check_interval)
        
        logger.info("Alive monitor stopped")

    def start(self, bot=None) -> asyncio.Task:
        """Start monitoring in background.
        
        Args:
            bot: Optional discord bot instance
            
        Returns:
            asyncio.Task: Monitoring task
        """
        if self._task and not self._task.done():
            logger.warning("Monitor already running")
            return self._task
        
        self._task = asyncio.create_task(self.monitor_loop(bot))
        return self._task

    def stop(self) -> None:
        """Stop monitoring."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()

    def get_stats(self) -> dict:
        """Get monitoring statistics.
        
        Returns:
            dict: Statistics
        """
        return {
            "check_count": self.check_count,
            "warning_count": self.warning_count,
            "error_count": self.error_count,
            "uptime_seconds": self.get_uptime_seconds(),
            "running": self._running,
        }


async def main():
    """Standalone monitoring mode."""
    import signal
    
    monitor = AliveMonitor(check_interval=30)
    
    def signal_handler(sig, frame):
        print("\nShutting down monitor...")
        monitor.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("Starting standalone health monitor...")
    print("Press Ctrl+C to stop")
    
    try:
        await monitor.monitor_loop()
    except KeyboardInterrupt:
        print("\nMonitor stopped by user")
    
    stats = monitor.get_stats()
    print(f"\nFinal Stats:")
    print(f"  Checks: {stats['check_count']}")
    print(f"  Warnings: {stats['warning_count']}")
    print(f"  Errors: {stats['error_count']}")
    print(f"  Uptime: {stats['uptime_seconds']:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
