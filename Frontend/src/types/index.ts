// Tipos básicos para la aplicación

// Estados del sistema
export type SystemStatus = 'online' | 'offline' | 'maintenance' | 'error'
export type ConnectionStatus = 'connected' | 'disconnected' | 'connecting' | 'error'
export type MessageStatus = 'pending' | 'sent' | 'delivered' | 'read' | 'failed'

// Interfaces principales
export interface Contact {
  id: string
  phone: string
  name?: string
  last_message?: string
  last_message_time?: string
  status: 'active' | 'inactive' | 'blocked'
  conversation_count: number
  avg_response_time?: number
  created_at: string
  updated_at: string
}

export interface Message {
  id: string
  chat_id: string
  content: string
  sender: 'user' | 'bot' | 'admin'
  message_type: 'text' | 'image' | 'file' | 'audio'
  status: MessageStatus
  timestamp: string
  metadata?: {
    model_used?: string
    response_time?: number
    confidence_score?: number
    is_automated?: boolean
  }
}

export interface Conversation {
  id: string
  contact: Contact
  messages: Message[]
  status: 'active' | 'paused' | 'ended'
  created_at: string
  updated_at: string
  last_activity: string
  metadata?: Record<string, any>
}

// Estadísticas del sistema
export interface SystemStats {
  messages: {
    total_sent: number
    total_received: number
    automated_responses: number
    manual_responses: number
    failed_messages: number
    avg_response_time: number
  }
  conversations: {
    active_chats: number
    completed_today: number
    pending_responses: number
    avg_conversation_length: number
  }
  system: {
    uptime: number
    cpu_usage: number
    memory_usage: number
    disk_usage: number
    last_restart: string
  }
  performance: {
    requests_per_minute: number
    error_rate: number
    avg_processing_time: number
  }
}

// Cola de mensajes
export interface MessageQueue {
  id: string
  chat_id: string
  contact_name?: string
  message: string
  priority: 'low' | 'normal' | 'high' | 'urgent'
  scheduled_time?: string
  retry_count: number
  max_retries: number
  status: 'pending' | 'processing' | 'sent' | 'failed' | 'cancelled'
  created_at: string
  updated_at: string
  error_message?: string
}

// Plantillas de mensajes
export interface MessageTemplate {
  id: string
  name: string
  content: string
  category: string
  variables: string[]
  is_active: boolean
  usage_count: number
  created_at: string
  updated_at: string
}

// Modelos LLM
export interface LLMModel {
  id: string
  name: string
  provider: string
  model_type: 'chat' | 'completion' | 'embedding'
  is_active: boolean
  status: 'available' | 'loading' | 'error' | 'unavailable'
  parameters?: {
    temperature?: number
    max_tokens?: number
    top_p?: number
    frequency_penalty?: number
    presence_penalty?: number
  }
  metadata?: {
    size?: string
    capabilities?: string[]
    cost_per_token?: number
  }
  created_at: string
  updated_at: string
}

// Reglas de automatización
export interface AutomationRule {
  id: string
  name: string
  description?: string
  trigger: {
    type: 'keyword' | 'pattern' | 'time' | 'event'
    value: string
    conditions?: Record<string, any>
  }
  action: {
    type: 'send_message' | 'transfer_agent' | 'set_variable' | 'webhook'
    value: string
    parameters?: Record<string, any>
  }
  is_active: boolean
  priority: number
  usage_count: number
  created_at: string
  updated_at: string
}

// Configuración del sistema
export interface SystemConfig {
  general: {
    app_name: string
    timezone: string
    language: string
    auto_response: boolean
    business_hours: {
      enabled: boolean
      start_time: string
      end_time: string
      days: number[]
    }
  }
  whatsapp: {
    phone_number: string
    webhook_url?: string
    api_timeout: number
    retry_attempts: number
  }
  ai: {
    default_model: string
    fallback_model?: string
    temperature: number
    max_tokens: number
    system_prompt: string
    response_timeout: number
  }
  notifications: {
    email_alerts: boolean
    webhook_alerts: boolean
    alert_threshold: number
  }
}

// Respuestas de API
export interface ApiResponse<T = any> {
  success: boolean
  data?: T
  error?: string
  message?: string
  timestamp: string
}

export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  pagination: {
    page: number
    limit: number
    total: number
    total_pages: number
    has_next: boolean
    has_prev: boolean
  }
}

// Formularios
export interface SendMessageForm {
  contact_id: string
  message: string
  template_id?: string
  variables?: Record<string, string>
  scheduled_time?: string
  priority?: 'low' | 'normal' | 'high' | 'urgent'
}

export interface CreateTemplateForm {
  name: string
  content: string
  category: string
  variables?: string[]
  is_active?: boolean
}

export interface CreateRuleForm {
  name: string
  description?: string
  trigger: {
    type: 'keyword' | 'pattern' | 'time' | 'event'
    value: string
    conditions?: Record<string, any>
  }
  action: {
    type: 'send_message' | 'transfer_agent' | 'set_variable' | 'webhook'
    value: string
    parameters?: Record<string, any>
  }
  is_active?: boolean
  priority?: number
}