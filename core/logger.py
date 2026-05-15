import os
import sys
import time
import functools
import structlog
import logging
from datetime import datetime
from config import settings

def configure_logger():
    """Configura o structlog baseado no ambiente (dev vs production)."""
    
    # Detecta se está em produção
    is_prod = os.getenv("ENV", "development").lower() == "production"
    
    # Processadores básicos
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.format_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if is_prod:
        # Formato JSON para produção (VPS/Logs centralizados)
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Formato colorido e legível para desenvolvimento local
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

# Inicializa na importação
configure_logger()
logger = structlog.get_logger()

# --- DECORATOR DE MONITORAMENTO ---

def monitored_job(name: str):
    """Decorator para monitorar execução, erros e performance de jobs do scheduler."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            from core.database import DatabaseManager
            from src.telegram_bot import send_telegram_message
            
            db = DatabaseManager()
            start_time = time.time()
            log = logger.bind(job_name=name)
            
            log.info("job_started", status="running")
            
            try:
                # Executa o job (pode ser async ou sync)
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                duration_ms = int((time.time() - start_time) * 1000)
                db.log_job_run(name, "success", duration_ms)
                log.info("job_finished", status="success", duration_ms=duration_ms)
                return result
                
            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                error_msg = str(e)
                db.log_job_run(name, "failed", duration_ms, error=error_msg)
                
                log.error("job_failed", status="failed", duration_ms=duration_ms, error=error_msg)
                
                # Alerta Telegram para o Admin
                alert_text = (
                    f"❌ *JOB FAILED: {name}*\n"
                    f"⏱ Duração: {duration_ms}ms\n"
                    f"🚨 Erro: `{error_msg[:100]}`"
                )
                import asyncio
                asyncio.create_task(send_telegram_message(alert_text))
                
                raise e
        return wrapper
    return decorator

# Helper para importar asyncio sem circular dependency no monitored_job
import asyncio
