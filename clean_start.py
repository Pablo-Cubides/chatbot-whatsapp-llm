#!/usr/bin/env python3
"""
Script de inicio limpio para el chatbot WhatsApp
- Mata todos los procesos relacionados (LM Studio, Chrome, Python automator)
- Libera puertos
- Inicia el panel administrativo en estado limpio
"""

import os
import sys
import time
import subprocess
import socket
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

def kill_processes_by_name(process_names):
    """Mata procesos por nombre usando taskkill de Windows, excluyendo el proceso actual"""
    killed_count = 0
    current_pid = os.getpid()  # PID del proceso actual
    
    for process_name in process_names:
        try:
            # Para procesos Python, excluir el PID actual
            if "python" in process_name.lower():
                # Primero obtener lista de PIDs de Python
                result = subprocess.run(
                    f'tasklist /fi "imagename eq {process_name}" /fo csv',
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.stdout:
                    lines = result.stdout.strip().split('\n')[1:]  # Skip header
                    for line in lines:
                        if line:
                            parts = line.split(',')
                            if len(parts) >= 2:
                                pid_str = parts[1].strip('"')
                                try:
                                    pid = int(pid_str)
                                    if pid != current_pid:  # No matar el proceso actual
                                        subprocess.run(f'taskkill /f /pid {pid} 2>nul', shell=True, timeout=5)
                                        killed_count += 1
                                        log.info(f"✅ Matado proceso Python PID {pid}")
                                except (ValueError, Exception):
                                    pass
            else:
                # Para otros procesos, matar normalmente
                result = subprocess.run(
                    f'taskkill /f /im "{process_name}" 2>nul',
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if "SUCCESS" in result.stdout:
                    lines = result.stdout.count("SUCCESS")
                    killed_count += lines
                    log.info(f"✅ Matados {lines} procesos de {process_name}")
        except (subprocess.TimeoutExpired, Exception) as e:
            log.debug(f"Error matando {process_name}: {e}")
    return killed_count

def kill_processes_by_port(ports):
    """Mata procesos que usan puertos específicos"""
    killed_count = 0
    for port in ports:
        try:
            # Usar netstat para encontrar PID que usa el puerto
            result = subprocess.run(
                f'netstat -ano | findstr ":{port}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.stdout:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        try:
                            subprocess.run(f'taskkill /f /pid {pid} 2>nul', shell=True, timeout=5)
                            killed_count += 1
                            log.info(f"✅ Matado proceso PID {pid} en puerto {port}")
                        except Exception:
                            pass
        except Exception as e:
            log.debug(f"Error liberando puerto {port}: {e}")
    return killed_count

def check_port_free(port):
    """Verifica si un puerto está libre"""
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=1):
            return False  # Puerto ocupado
    except OSError:
        return True  # Puerto libre

def nuclear_cleanup():
    """Limpieza nuclear de todos los procesos relacionados"""
    log.info("🧹 INICIANDO LIMPIEZA NUCLEAR...")
    
    total_killed = 0
    
    # 1. Matar procesos por nombre
    log.info("📝 Matando procesos por nombre...")
    process_names = [
        "LM Studio.exe",
        "lms.exe", 
        "lmstudio.exe",
        "chrome.exe",
        "chromium.exe", 
        "msedge.exe",
        "python.exe",
        "pythonw.exe",
        "python3.exe",
        "python3.13.exe"
    ]
    
    killed = kill_processes_by_name(process_names)
    total_killed += killed
    
    # 2. Esperar un poco para que terminen
    if killed > 0:
        log.info("⏳ Esperando 3 segundos para que terminen los procesos...")
        time.sleep(3)
    
    # 3. Matar procesos por puertos específicos
    log.info("🔌 Liberando puertos...")
    ports_to_free = [1234, 8000, 8001, 8002, 8003]
    port_kills = kill_processes_by_port(ports_to_free)
    total_killed += port_kills
    
    # 4. Verificar que los puertos estén libres
    log.info("🔍 Verificando estado de puertos...")
    for port in [1234, 8003]:  # Puertos críticos
        if check_port_free(port):
            log.info(f"✅ Puerto {port}: LIBRE")
        else:
            log.warning(f"⚠️ Puerto {port}: AÚN OCUPADO")
    
    log.info(f"🎯 LIMPIEZA COMPLETADA - {total_killed} procesos eliminados")
    return total_killed

def start_admin_panel():
    """Inicia el panel administrativo"""
    log.info("🚀 INICIANDO PANEL ADMINISTRATIVO...")
    
    # Verificar que estamos en el directorio correcto
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Comando para iniciar el panel
    cmd = [
        sys.executable, 
        "-m", "uvicorn", 
        "admin_panel:app", 
        "--host", "127.0.0.1", 
        "--port", "8003"
    ]
    
    try:
        log.info("🎮 Ejecutando panel en puerto 8003...")
        log.info("🌐 Panel disponible en: http://127.0.0.1:8003")
        log.info("📱 Interfaz web en: http://127.0.0.1:8003/index.html")
        log.info("🛑 Para detener: Ctrl+C")
        
        # Ejecutar el comando
        subprocess.run(cmd)
        
    except KeyboardInterrupt:
        log.info("\n🛑 Panel detenido por el usuario")
    except Exception as e:
        log.error(f"❌ Error iniciando panel: {e}")
        return False
    
    return True

def main():
    """Función principal"""
    print("=" * 60)
    print("🚀 CHATBOT WHATSAPP - INICIO LIMPIO")
    print("=" * 60)
    
    try:
        # Paso 1: Limpieza nuclear
        nuclear_cleanup()
        
        # Paso 2: Pequeña pausa de seguridad
        log.info("⏳ Pausa de seguridad de 2 segundos...")
        time.sleep(2)
        
        # Paso 3: Iniciar panel administrativo
        start_admin_panel()
        
    except KeyboardInterrupt:
        log.info("\n🛑 Operación cancelada por el usuario")
    except Exception as e:
        log.error(f"❌ Error en el proceso: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()