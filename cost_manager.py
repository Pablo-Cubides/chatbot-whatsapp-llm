"""
Sistema avanzado de gestión de costos y control de presupuestos para LLM
Incluye seguimiento en tiempo real, alertas, análisis y reportes detallados
"""
import json
import sqlite3
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple, Any, Callable
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

@dataclass
class CostEvent:
    """Evento individual de costo"""
    id: Optional[int] = None
    timestamp: str = ""
    service: str = ""
    model: str = ""
    operation_type: str = ""  # chat, completion, embedding, etc.
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    input_cost_usd: Decimal = Decimal('0.00')
    output_cost_usd: Decimal = Decimal('0.00')
    total_cost_usd: Decimal = Decimal('0.00')
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        if self.metadata is None:
            self.metadata = {}
        # Asegurar que los costos sean Decimal
        self.input_cost_usd = Decimal(str(self.input_cost_usd))
        self.output_cost_usd = Decimal(str(self.output_cost_usd))
        self.total_cost_usd = Decimal(str(self.total_cost_usd))

@dataclass
class BudgetLimit:
    """Límite de presupuesto"""
    id: Optional[int] = None
    name: str = ""
    limit_type: str = "daily"  # daily, weekly, monthly, total
    amount_usd: Decimal = Decimal('0.00')
    current_spent_usd: Decimal = Decimal('0.00')
    alert_threshold_percent: int = 80
    services: Optional[List[str]] = None  # None = all services
    users: Optional[List[str]] = None     # None = all users
    created_at: str = ""
    updated_at: str = ""
    active: bool = True

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()
        if self.services is None:
            self.services = []
        if self.users is None:
            self.users = []
        self.amount_usd = Decimal(str(self.amount_usd))
        self.current_spent_usd = Decimal(str(self.current_spent_usd))

@dataclass
class CostAlert:
    """Alerta de costo"""
    id: Optional[int] = None
    timestamp: str = ""
    level: AlertLevel = AlertLevel.INFO
    title: str = ""
    message: str = ""
    budget_id: Optional[int] = None
    service: Optional[str] = None
    current_amount_usd: Decimal = Decimal('0.00')
    threshold_amount_usd: Decimal = Decimal('0.00')
    acknowledged: bool = False
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        if self.metadata is None:
            self.metadata = {}
        self.current_amount_usd = Decimal(str(self.current_amount_usd))
        self.threshold_amount_usd = Decimal(str(self.threshold_amount_usd))

@dataclass
class UsageStats:
    """Estadísticas de uso"""
    total_cost_usd: Decimal = Decimal('0.00')
    total_tokens: int = 0
    total_requests: int = 0
    average_cost_per_request: Decimal = Decimal('0.00')
    cost_by_service: Optional[Dict[str, Decimal]] = None
    cost_by_model: Optional[Dict[str, Decimal]] = None
    cost_by_hour: Optional[Dict[str, Decimal]] = None
    cost_by_day: Optional[Dict[str, Decimal]] = None
    tokens_by_service: Optional[Dict[str, int]] = None
    most_expensive_request: Optional[CostEvent] = None
    cost_trend_7d: Optional[List[Decimal]] = None

    def __post_init__(self):
        if self.cost_by_service is None:
            self.cost_by_service = {}
        if self.cost_by_model is None:
            self.cost_by_model = {}
        if self.cost_by_hour is None:
            self.cost_by_hour = {}
        if self.cost_by_day is None:
            self.cost_by_day = {}
        if self.tokens_by_service is None:
            self.tokens_by_service = {}
        if self.cost_trend_7d is None:
            self.cost_trend_7d = []

class CostDatabase:
    """Base de datos para gestión de costos"""
    
    def __init__(self, db_path: str = "cost_tracking.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Inicializar base de datos"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Tabla de eventos de costo
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cost_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    service TEXT NOT NULL,
                    model TEXT NOT NULL,
                    operation_type TEXT NOT NULL,
                    input_tokens INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    input_cost_usd TEXT NOT NULL,
                    output_cost_usd TEXT NOT NULL,
                    total_cost_usd TEXT NOT NULL,
                    user_id TEXT,
                    conversation_id TEXT,
                    session_id TEXT,
                    metadata TEXT
                )
            ''')
            
            # Tabla de límites de presupuesto
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS budget_limits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    limit_type TEXT NOT NULL,
                    amount_usd TEXT NOT NULL,
                    current_spent_usd TEXT DEFAULT '0.00',
                    alert_threshold_percent INTEGER DEFAULT 80,
                    services TEXT,
                    users TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    active BOOLEAN DEFAULT 1
                )
            ''')
            
            # Tabla de alertas
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cost_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    budget_id INTEGER,
                    service TEXT,
                    current_amount_usd TEXT NOT NULL,
                    threshold_amount_usd TEXT NOT NULL,
                    acknowledged BOOLEAN DEFAULT 0,
                    metadata TEXT,
                    FOREIGN KEY (budget_id) REFERENCES budget_limits (id)
                )
            ''')
            
            # Índices para optimización
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_cost_events_timestamp ON cost_events(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_cost_events_service ON cost_events(service)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_cost_events_user ON cost_events(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON cost_alerts(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_level ON cost_alerts(level)')
            
            conn.commit()

    def save_cost_event(self, event: CostEvent) -> Optional[int]:
        """Guardar evento de costo"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO cost_events (
                    timestamp, service, model, operation_type,
                    input_tokens, output_tokens, total_tokens,
                    input_cost_usd, output_cost_usd, total_cost_usd,
                    user_id, conversation_id, session_id, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                event.timestamp, event.service, event.model, event.operation_type,
                event.input_tokens, event.output_tokens, event.total_tokens,
                str(event.input_cost_usd), str(event.output_cost_usd), str(event.total_cost_usd),
                event.user_id, event.conversation_id, event.session_id,
                json.dumps(event.metadata) if event.metadata else None
            ))
            return cursor.lastrowid

    def save_budget_limit(self, budget: BudgetLimit) -> Optional[int]:
        """Guardar límite de presupuesto"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO budget_limits (
                    name, limit_type, amount_usd, current_spent_usd,
                    alert_threshold_percent, services, users,
                    created_at, updated_at, active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                budget.name, budget.limit_type, str(budget.amount_usd), str(budget.current_spent_usd),
                budget.alert_threshold_percent, json.dumps(budget.services), json.dumps(budget.users),
                budget.created_at, budget.updated_at, budget.active
            ))
            return cursor.lastrowid

    def save_alert(self, alert: CostAlert) -> Optional[int]:
        """Guardar alerta"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO cost_alerts (
                    timestamp, level, title, message, budget_id, service,
                    current_amount_usd, threshold_amount_usd, acknowledged, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                alert.timestamp, alert.level.value, alert.title, alert.message,
                alert.budget_id, alert.service, str(alert.current_amount_usd),
                str(alert.threshold_amount_usd), alert.acknowledged,
                json.dumps(alert.metadata) if alert.metadata else None
            ))
            return cursor.lastrowid

    def get_cost_events(self, start_date: Optional[str] = None, end_date: Optional[str] = None,
                       service: Optional[str] = None, user_id: Optional[str] = None) -> List[CostEvent]:
        """Obtener eventos de costo con filtros"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM cost_events WHERE 1=1"
            params = []
            
            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date)
            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date)
            if service:
                query += " AND service = ?"
                params.append(service)
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            
            query += " ORDER BY timestamp DESC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            events = []
            for row in rows:
                events.append(CostEvent(
                    id=row[0], timestamp=row[1], service=row[2], model=row[3],
                    operation_type=row[4], input_tokens=row[5], output_tokens=row[6],
                    total_tokens=row[7], input_cost_usd=Decimal(row[8]),
                    output_cost_usd=Decimal(row[9]), total_cost_usd=Decimal(row[10]),
                    user_id=row[11], conversation_id=row[12], session_id=row[13],
                    metadata=json.loads(row[14]) if row[14] else {}
                ))
            
            return events

    def get_budget_limits(self, active_only: bool = True) -> List[BudgetLimit]:
        """Obtener límites de presupuesto"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM budget_limits"
            if active_only:
                query += " WHERE active = 1"
            query += " ORDER BY created_at DESC"
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            budgets = []
            for row in rows:
                budgets.append(BudgetLimit(
                    id=row[0], name=row[1], limit_type=row[2],
                    amount_usd=Decimal(row[3]), current_spent_usd=Decimal(row[4]),
                    alert_threshold_percent=row[5],
                    services=json.loads(row[6]) if row[6] else [],
                    users=json.loads(row[7]) if row[7] else [],
                    created_at=row[8], updated_at=row[9], active=bool(row[10])
                ))
            
            return budgets

    def get_alerts(self, acknowledged: Optional[bool] = None, 
                   level: Optional[AlertLevel] = None) -> List[CostAlert]:
        """Obtener alertas"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM cost_alerts WHERE 1=1"
            params = []
            
            if acknowledged is not None:
                query += " AND acknowledged = ?"
                params.append(acknowledged)
            if level:
                query += " AND level = ?"
                params.append(level.value)
            
            query += " ORDER BY timestamp DESC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            alerts = []
            for row in rows:
                alerts.append(CostAlert(
                    id=row[0], timestamp=row[1], level=AlertLevel(row[2]),
                    title=row[3], message=row[4], budget_id=row[5], service=row[6],
                    current_amount_usd=Decimal(row[7]), threshold_amount_usd=Decimal(row[8]),
                    acknowledged=bool(row[9]),
                    metadata=json.loads(row[10]) if row[10] else {}
                ))
            
            return alerts

class CostTracker:
    """Rastreador principal de costos"""
    
    def __init__(self, db_path: str = "cost_tracking.db"):
        self.db = CostDatabase(db_path)
        self.pricing_models = self._load_pricing_models()
        self.alert_callbacks: List[Callable[[CostAlert], None]] = []
        self._monitoring_active = False
        self._monitoring_thread = None
        self._lock = threading.Lock()

    def _load_pricing_models(self) -> Dict[str, Dict[str, Dict[str, Decimal]]]:
        """Cargar modelos de precios"""
        return {
            "openai": {
                "gpt-4": {
                    "input": Decimal("0.03"),  # $0.03 per 1K tokens
                    "output": Decimal("0.06")  # $0.06 per 1K tokens
                },
                "gpt-4-turbo": {
                    "input": Decimal("0.01"),
                    "output": Decimal("0.03")
                },
                "gpt-3.5-turbo": {
                    "input": Decimal("0.0015"),
                    "output": Decimal("0.002")
                }
            },
            "claude": {
                "claude-3-opus": {
                    "input": Decimal("0.015"),
                    "output": Decimal("0.075")
                },
                "claude-3-sonnet": {
                    "input": Decimal("0.003"),
                    "output": Decimal("0.015")
                },
                "claude-3-haiku": {
                    "input": Decimal("0.00025"),
                    "output": Decimal("0.00125")
                }
            },
            "gemini": {
                "gemini-pro": {
                    "input": Decimal("0.00025"),
                    "output": Decimal("0.0005")
                },
                "gemini-pro-vision": {
                    "input": Decimal("0.00025"),
                    "output": Decimal("0.0005")
                }
            },
            "xai": {
                "grok-beta": {
                    "input": Decimal("0.002"),
                    "output": Decimal("0.01")
                }
            }
        }

    def calculate_cost(self, service: str, model: str, input_tokens: int, 
                      output_tokens: int) -> Tuple[Decimal, Decimal, Decimal]:
        """Calcular costo de un request"""
        if service not in self.pricing_models:
            return Decimal('0.00'), Decimal('0.00'), Decimal('0.00')
        
        if model not in self.pricing_models[service]:
            return Decimal('0.00'), Decimal('0.00'), Decimal('0.00')
        
        pricing = self.pricing_models[service][model]
        
        # Calcular costo por 1K tokens
        input_cost = (Decimal(str(input_tokens)) / Decimal('1000')) * pricing["input"]
        output_cost = (Decimal(str(output_tokens)) / Decimal('1000')) * pricing["output"]
        total_cost = input_cost + output_cost
        
        # Redondear a 4 decimales
        input_cost = input_cost.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        output_cost = output_cost.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        total_cost = total_cost.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        
        return input_cost, output_cost, total_cost

    def track_usage(self, service: str, model: str, operation_type: str,
                   input_tokens: int, output_tokens: int, user_id: Optional[str] = None,
                   conversation_id: Optional[str] = None, session_id: Optional[str] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> CostEvent:
        """Rastrear uso y calcular costo"""
        
        input_cost, output_cost, total_cost = self.calculate_cost(
            service, model, input_tokens, output_tokens
        )
        
        event = CostEvent(
            service=service,
            model=model,
            operation_type=operation_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            input_cost_usd=input_cost,
            output_cost_usd=output_cost,
            total_cost_usd=total_cost,
            user_id=user_id,
            conversation_id=conversation_id,
            session_id=session_id,
            metadata=metadata or {}
        )
        
        # Guardar evento
        event.id = self.db.save_cost_event(event)
        
        # Verificar límites de presupuesto
        self._check_budget_limits(event)
        
        logger.info(f"Tracked usage: {service}/{model} - ${total_cost} (tokens: {input_tokens}+{output_tokens})")
        
        return event

    def _check_budget_limits(self, event: CostEvent):
        """Verificar límites de presupuesto y generar alertas"""
        budgets = self.db.get_budget_limits(active_only=True)
        
        for budget in budgets:
            # Verificar si el evento aplica a este presupuesto
            if budget.services and event.service not in budget.services:
                continue
            if budget.users and event.user_id and event.user_id not in budget.users:
                continue
            
            # Calcular gasto actual en el período
            start_date = self._get_period_start(budget.limit_type)
            current_spent = self._calculate_period_spending(
                start_date, budget.services, budget.users
            )
            
            # Actualizar presupuesto
            budget.current_spent_usd = current_spent
            
            # Verificar alertas
            usage_percent = (current_spent / budget.amount_usd * 100) if budget.amount_usd > 0 else 0
            
            if usage_percent >= budget.alert_threshold_percent:
                alert_level = AlertLevel.WARNING
                if usage_percent >= 100:
                    alert_level = AlertLevel.CRITICAL
                elif usage_percent >= 90:
                    alert_level = AlertLevel.WARNING
                
                alert = CostAlert(
                    level=alert_level,
                    title=f"Budget Alert: {budget.name}",
                    message=f"Budget usage at {usage_percent:.1f}% (${current_spent}/${budget.amount_usd})",
                    budget_id=budget.id,
                    service=event.service,
                    current_amount_usd=current_spent,
                    threshold_amount_usd=budget.amount_usd * Decimal(str(budget.alert_threshold_percent)) / Decimal('100')
                )
                
                alert.id = self.db.save_alert(alert)
                self._trigger_alert(alert)

    def _get_period_start(self, limit_type: str) -> str:
        """Obtener fecha de inicio del período"""
        now = datetime.now()
        
        if limit_type == "daily":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif limit_type == "weekly":
            days_since_monday = now.weekday()
            start = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif limit_type == "monthly":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:  # total
            start = datetime(2020, 1, 1)  # Fecha muy antigua
        
        return start.isoformat()

    def _calculate_period_spending(self, start_date: str, services: Optional[List[str]] = None,
                                 users: Optional[List[str]] = None) -> Decimal:
        """Calcular gasto en un período"""
        events = self.db.get_cost_events(start_date=start_date)
        
        total = Decimal('0.00')
        for event in events:
            if services and event.service not in services:
                continue
            if users and event.user_id and event.user_id not in users:
                continue
            total += event.total_cost_usd
        
        return total

    def _trigger_alert(self, alert: CostAlert):
        """Disparar alertas"""
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

    def add_alert_callback(self, callback: Callable[[CostAlert], None]):
        """Agregar callback para alertas"""
        self.alert_callbacks.append(callback)

    def create_budget_limit(self, name: str, limit_type: str, amount_usd: Decimal,
                           alert_threshold_percent: int = 80, services: Optional[List[str]] = None,
                           users: Optional[List[str]] = None) -> BudgetLimit:
        """Crear límite de presupuesto"""
        budget = BudgetLimit(
            name=name,
            limit_type=limit_type,
            amount_usd=amount_usd,
            alert_threshold_percent=alert_threshold_percent,
            services=services or [],
            users=users or []
        )
        
        budget.id = self.db.save_budget_limit(budget)
        logger.info(f"Created budget limit: {name} - ${amount_usd} ({limit_type})")
        
        return budget

    def get_usage_stats(self, start_date: Optional[str] = None, 
                       end_date: Optional[str] = None,
                       service: Optional[str] = None) -> UsageStats:
        """Obtener estadísticas de uso"""
        events = self.db.get_cost_events(start_date, end_date, service)
        
        if not events:
            return UsageStats()
        
        # Calcular estadísticas básicas
        total_cost = sum(event.total_cost_usd for event in events)
        total_tokens = sum(event.total_tokens for event in events)
        total_requests = len(events)
        avg_cost = total_cost / Decimal(str(total_requests)) if total_requests > 0 else Decimal('0.00')
        
        # Agrupar por servicio
        cost_by_service = {}
        tokens_by_service = {}
        for event in events:
            cost_by_service[event.service] = cost_by_service.get(event.service, Decimal('0.00')) + event.total_cost_usd
            tokens_by_service[event.service] = tokens_by_service.get(event.service, 0) + event.total_tokens
        
        # Agrupar por modelo
        cost_by_model = {}
        for event in events:
            model_key = f"{event.service}/{event.model}"
            cost_by_model[model_key] = cost_by_model.get(model_key, Decimal('0.00')) + event.total_cost_usd
        
        # Encontrar request más caro
        most_expensive = max(events, key=lambda e: e.total_cost_usd) if events else None
        
        # Tendencia de 7 días
        cost_trend = self._calculate_daily_trend(7)
        
        return UsageStats(
            total_cost_usd=Decimal(str(total_cost)),
            total_tokens=total_tokens,
            total_requests=total_requests,
            average_cost_per_request=avg_cost,
            cost_by_service=cost_by_service,
            cost_by_model=cost_by_model,
            tokens_by_service=tokens_by_service,
            most_expensive_request=most_expensive,
            cost_trend_7d=cost_trend
        )

    def _calculate_daily_trend(self, days: int) -> List[Decimal]:
        """Calcular tendencia diaria de costos"""
        trend = []
        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            start_date = date.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            end_date = date.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()
            
            events = self.db.get_cost_events(start_date, end_date)
            daily_cost = sum(event.total_cost_usd for event in events)
            trend.append(daily_cost)
        
        return list(reversed(trend))  # Orden cronológico

    def start_monitoring(self):
        """Iniciar monitoreo de presupuestos"""
        if self._monitoring_active:
            return
        
        self._monitoring_active = True
        self._monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitoring_thread.start()
        logger.info("Cost monitoring started")

    def stop_monitoring(self):
        """Detener monitoreo"""
        self._monitoring_active = False
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5)
        logger.info("Cost monitoring stopped")

    def _monitoring_loop(self):
        """Loop de monitoreo"""
        while self._monitoring_active:
            try:
                # Verificar presupuestos cada 5 minutos
                self._periodic_budget_check()
                
                # Dormir 5 minutos
                for _ in range(300):  # 5 minutos en segundos
                    if not self._monitoring_active:
                        break
                    import time
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                import time
                time.sleep(60)  # Esperar 1 minuto antes de reintentar

    def _periodic_budget_check(self):
        """Verificación periódica de presupuestos"""
        budgets = self.db.get_budget_limits(active_only=True)
        
        for budget in budgets:
            start_date = self._get_period_start(budget.limit_type)
            current_spent = self._calculate_period_spending(
                start_date, budget.services, budget.users
            )
            
            # Verificar si necesita alertas
            usage_percent = (current_spent / budget.amount_usd * 100) if budget.amount_usd > 0 else 0
            
            # Solo alertar una vez por período por presupuesto
            if usage_percent >= budget.alert_threshold_percent:
                recent_alerts = self.db.get_alerts()
                budget_has_recent_alert = any(
                    alert.budget_id == budget.id and 
                    alert.timestamp > start_date
                    for alert in recent_alerts
                )
                
                if not budget_has_recent_alert:
                    alert_level = AlertLevel.CRITICAL if usage_percent >= 100 else AlertLevel.WARNING
                    
                    alert = CostAlert(
                        level=alert_level,
                        title=f"Budget Alert: {budget.name}",
                        message=f"Budget usage at {usage_percent:.1f}% (${current_spent}/${budget.amount_usd})",
                        budget_id=budget.id,
                        current_amount_usd=current_spent,
                        threshold_amount_usd=budget.amount_usd
                    )
                    
                    alert.id = self.db.save_alert(alert)
                    self._trigger_alert(alert)

# Instancia global del rastreador de costos
cost_tracker = CostTracker()

# Funciones de conveniencia
def track_llm_usage(service: str, model: str, input_tokens: int, output_tokens: int,
                   user_id: Optional[str] = None, conversation_id: Optional[str] = None,
                   session_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> CostEvent:
    """Función de conveniencia para rastrear uso de LLM"""
    return cost_tracker.track_usage(
        service=service,
        model=model,
        operation_type="chat_completion",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        user_id=user_id,
        conversation_id=conversation_id,
        session_id=session_id,
        metadata=metadata
    )

def get_current_costs(period: str = "daily", service: Optional[str] = None) -> UsageStats:
    """Obtener costos actuales"""
    start_date = cost_tracker._get_period_start(period)
    return cost_tracker.get_usage_stats(start_date=start_date, service=service)

def create_daily_budget(name: str, amount: Decimal, services: Optional[List[str]] = None) -> BudgetLimit:
    """Crear presupuesto diario"""
    return cost_tracker.create_budget_limit(
        name=name,
        limit_type="daily",
        amount_usd=amount,
        services=services
    )

def create_monthly_budget(name: str, amount: Decimal, services: Optional[List[str]] = None) -> BudgetLimit:
    """Crear presupuesto mensual"""
    return cost_tracker.create_budget_limit(
        name=name,
        limit_type="monthly",
        amount_usd=amount,
        services=services
    )