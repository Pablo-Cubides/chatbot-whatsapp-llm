'use client'

import { useState, useEffect } from 'react'
import { apiService } from '@/lib/api'
import { 
  ChartBarIcon,
  ClockIcon,
  ChatBubbleLeftRightIcon,
  UserGroupIcon,
  CpuChipIcon,
  CheckCircleIcon,
  XCircleIcon,
  ArrowTrendingUpIcon,
  CalendarDaysIcon
} from '@heroicons/react/24/outline'
import { Line, Bar, Doughnut } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
} from 'chart.js'

// Registrar componentes de Chart.js
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement
)

export function StatsPage() {
  const [analytics, setAnalytics] = useState<any>({})
  const [systemStats, setSystemStats] = useState<any>({})
  const [events, setEvents] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [realTimeEnabled, setRealTimeEnabled] = useState(true)
  const [lastEventUpdate, setLastEventUpdate] = useState<Date>(new Date())

  useEffect(() => {
    loadStatistics()
    
    // Actualizar cada 30 segundos (o 5 segundos si real-time está habilitado)
    const interval = setInterval(loadStatistics, realTimeEnabled ? 5000 : 30000)

    // Configurar polling más frecuente para eventos en tiempo real
    let eventsInterval: NodeJS.Timeout | null = null
    
    if (realTimeEnabled) {
      try {
        // Polling más frecuente para eventos en tiempo real
        eventsInterval = setInterval(async () => {
          try {
            const eventsData = await apiService.getEvents()
            if (eventsData?.events) {
              setEvents(eventsData.events)
              setLastEventUpdate(new Date())
            }
          } catch (error) {
            console.error('Error fetching real-time events:', error)
          }
        }, 2000) // Actualizar eventos cada 2 segundos

      } catch (error) {
        console.error('Error setting up real-time events:', error)
      }
    }

    return () => {
      clearInterval(interval)
      if (eventsInterval) {
        clearInterval(eventsInterval)
      }
    }
  }, [realTimeEnabled])

  const loadStatistics = async () => {
    setLoading(true)
    try {
      const [analyticsData, statusData, eventsData] = await Promise.all([
        apiService.getAnalytics(),
        apiService.getSystemStatus(),
        apiService.getEvents()
      ])
      
      setAnalytics(analyticsData || {})
      setSystemStats(statusData || {})
      setEvents(eventsData?.events || [])
    } catch (error) {
      console.error('Error loading statistics:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / (24 * 3600))
    const hours = Math.floor((seconds % (24 * 3600)) / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    
    if (days > 0) return `${days}d ${hours}h ${minutes}m`
    if (hours > 0) return `${hours}h ${minutes}m`
    return `${minutes}m`
  }

  // Datos para gráficos
  const messagesTrendData = {
    labels: analytics.conversations_by_day?.map((item: any) => item.date) || [],
    datasets: [
      {
        label: 'Mensajes por día',
        data: analytics.conversations_by_day?.map((item: any) => item.count) || [],
        borderColor: 'rgb(59, 130, 246)',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        tension: 0.4,
      },
    ],
  }

  const topUsersData = {
    labels: analytics.top_users?.map((user: any) => user.user) || [],
    datasets: [
      {
        label: 'Mensajes',
        data: analytics.top_users?.map((user: any) => user.messages) || [],
        backgroundColor: [
          'rgba(59, 130, 246, 0.8)',
          'rgba(16, 185, 129, 0.8)',
          'rgba(245, 101, 101, 0.8)',
          'rgba(251, 191, 36, 0.8)',
          'rgba(139, 92, 246, 0.8)',
        ],
      },
    ],
  }

  const systemStatusData = {
    labels: ['CPU', 'Memoria', 'Disco'],
    datasets: [
      {
        data: [
          systemStats.system?.cpu_usage || 0,
          systemStats.system?.memory_usage || 0,
          systemStats.system?.disk_usage || 0,
        ],
        backgroundColor: [
          systemStats.system?.cpu_usage > 80 ? 'rgba(245, 101, 101, 0.8)' : 'rgba(16, 185, 129, 0.8)',
          systemStats.system?.memory_usage > 80 ? 'rgba(245, 101, 101, 0.8)' : 'rgba(59, 130, 246, 0.8)',
          systemStats.system?.disk_usage > 80 ? 'rgba(245, 101, 101, 0.8)' : 'rgba(251, 191, 36, 0.8)',
        ],
      },
    ],
  }

  const chartOptions = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top' as const,
      },
    },
    scales: {
      y: {
        beginAtZero: true,
      },
    },
  }

  const doughnutOptions = {
    responsive: true,
    plugins: {
      legend: {
        position: 'bottom' as const,
      },
    },
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-2 flex items-center">
          <ChartBarIcon className="h-7 w-7 mr-3 text-blue-500" />
          Estadísticas y Monitoreo
        </h1>
        <p className="text-gray-600">Métricas de rendimiento, uso del sistema y análisis de conversaciones</p>
      </div>

      {/* Métricas principales */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white rounded-lg shadow-lg p-6">
          <div className="flex items-center">
            <div className="p-3 rounded-full bg-blue-100">
              <ChatBubbleLeftRightIcon className="h-8 w-8 text-blue-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Mensajes Enviados</p>
              <p className="text-2xl font-bold text-gray-900">
                {analytics.total_messages || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-lg p-6">
          <div className="flex items-center">
            <div className="p-3 rounded-full bg-green-100">
              <UserGroupIcon className="h-8 w-8 text-green-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Usuarios Activos</p>
              <p className="text-2xl font-bold text-gray-900">
                {analytics.total_users || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-lg p-6">
          <div className="flex items-center">
            <div className="p-3 rounded-full bg-purple-100">
              <ClockIcon className="h-8 w-8 text-purple-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Tiempo Activo</p>
              <p className="text-2xl font-bold text-gray-900">
                {formatUptime(systemStats.system?.uptime || 0)}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-lg p-6">
          <div className="flex items-center">
            <div className="p-3 rounded-full bg-yellow-100">
              <ArrowTrendingUpIcon className="h-8 w-8 text-yellow-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Tasa de Éxito</p>
              <p className="text-2xl font-bold text-gray-900">
                {((1 - (systemStats.performance?.error_rate || 0)) * 100).toFixed(1)}%
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Gráficos */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Tendencia de mensajes */}
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Mensajes por Día</h3>
          {analytics.conversations_by_day?.length > 0 ? (
            <Line data={messagesTrendData} options={chartOptions} />
          ) : (
            <div className="h-64 flex flex-col items-center justify-center text-gray-500 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
              <ChatBubbleLeftRightIcon className="h-16 w-16 text-gray-400 mb-4" />
              <p className="text-lg font-medium text-gray-600 mb-2">Sin datos de mensajes</p>
              <p className="text-sm text-center text-gray-500 max-w-xs">
                Los datos de mensajes aparecerán aquí una vez que el bot comience a procesar conversaciones
              </p>
            </div>
          )}
        </div>

        {/* Top usuarios */}
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Usuarios Más Activos</h3>
          {analytics.top_users?.length > 0 ? (
            <Bar data={topUsersData} options={chartOptions} />
          ) : (
            <div className="h-64 flex flex-col items-center justify-center text-gray-500 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
              <UserGroupIcon className="h-16 w-16 text-gray-400 mb-4" />
              <p className="text-lg font-medium text-gray-600 mb-2">Sin actividad de usuarios</p>
              <p className="text-sm text-center text-gray-500 max-w-xs">
                Las estadísticas de usuarios aparecerán cuando empiecen las conversaciones
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Estado del sistema */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Métricas de rendimiento */}
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Rendimiento del Sistema</h3>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-sm">
                <span>CPU</span>
                <span>{systemStats.system?.cpu_usage || 0}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className={`h-2 rounded-full ${
                    (systemStats.system?.cpu_usage || 0) > 80 ? 'bg-red-500' : 'bg-green-500'
                  }`}
                  style={{ width: `${systemStats.system?.cpu_usage || 0}%` }}
                ></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-sm">
                <span>Memoria</span>
                <span>{systemStats.system?.memory_usage || 0} MB</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className={`h-2 rounded-full ${
                    (systemStats.system?.memory_usage || 0) > 1000 ? 'bg-red-500' : 'bg-blue-500'
                  }`}
                  style={{ width: `${Math.min((systemStats.system?.memory_usage || 0) / 20, 100)}%` }}
                ></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-sm">
                <span>Requests/min</span>
                <span>{systemStats.performance?.requests_per_minute || 0}</span>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-sm">
                <span>Tiempo de respuesta</span>
                <span>{systemStats.performance?.avg_processing_time || 0}s</span>
              </div>
            </div>
          </div>
        </div>

        {/* Estado de servicios */}
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Estado de Servicios</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <span className="text-sm font-medium">WhatsApp</span>
              <div className="flex items-center">
                {systemStats.services?.whatsapp === 'connected' ? (
                  <>
                    <CheckCircleIcon className="h-5 w-5 text-green-500 mr-2" />
                    <span className="text-sm text-green-600">Conectado</span>
                  </>
                ) : (
                  <>
                    <XCircleIcon className="h-5 w-5 text-red-500 mr-2" />
                    <span className="text-sm text-red-600">Desconectado</span>
                  </>
                )}
              </div>
            </div>

            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <span className="text-sm font-medium">LM Studio</span>
              <div className="flex items-center">
                {systemStats.services?.lm_studio === 'running' ? (
                  <>
                    <CheckCircleIcon className="h-5 w-5 text-green-500 mr-2" />
                    <span className="text-sm text-green-600">Ejecutándose</span>
                  </>
                ) : (
                  <>
                    <XCircleIcon className="h-5 w-5 text-red-500 mr-2" />
                    <span className="text-sm text-red-600">Detenido</span>
                  </>
                )}
              </div>
            </div>

            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <span className="text-sm font-medium">Base de Datos</span>
              <div className="flex items-center">
                {systemStats.services?.database === 'active' ? (
                  <>
                    <CheckCircleIcon className="h-5 w-5 text-green-500 mr-2" />
                    <span className="text-sm text-green-600">Activa</span>
                  </>
                ) : (
                  <>
                    <XCircleIcon className="h-5 w-5 text-red-500 mr-2" />
                    <span className="text-sm text-red-600">Inactiva</span>
                  </>
                )}
              </div>
            </div>

            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <span className="text-sm font-medium">API Server</span>
              <div className="flex items-center">
                {systemStats.services?.api_server === 'active' ? (
                  <>
                    <CheckCircleIcon className="h-5 w-5 text-green-500 mr-2" />
                    <span className="text-sm text-green-600">Activo</span>
                  </>
                ) : (
                  <>
                    <XCircleIcon className="h-5 w-5 text-red-500 mr-2" />
                    <span className="text-sm text-red-600">Inactivo</span>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Eventos recientes */}
        <div className="bg-white rounded-lg shadow-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Eventos Recientes</h3>
            <div className="flex items-center space-x-3">
              <div className="flex items-center space-x-2">
                <div className={`w-2 h-2 rounded-full ${realTimeEnabled ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`}></div>
                <span className="text-xs text-gray-500">
                  {realTimeEnabled ? 'Tiempo Real' : 'Manual'}
                </span>
              </div>
              <button
                onClick={() => setRealTimeEnabled(!realTimeEnabled)}
                className={`px-3 py-1 text-xs rounded-full transition-colors ${
                  realTimeEnabled 
                    ? 'bg-green-100 text-green-700 hover:bg-green-200' 
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {realTimeEnabled ? 'Desactivar' : 'Activar'} Tiempo Real
              </button>
              <span className="text-xs text-gray-400">
                Última actualización: {lastEventUpdate.toLocaleTimeString()}
              </span>
            </div>
          </div>
          <div className="space-y-3 max-h-64 overflow-y-auto">
            {events.length > 0 ? (
              events.map((event, index) => {
                const getEventIcon = (type: string) => {
                  switch (type) {
                    case 'message':
                      return <ChatBubbleLeftRightIcon className="h-4 w-4 text-blue-500" />
                    case 'system':
                      return <CpuChipIcon className="h-4 w-4 text-green-500" />
                    case 'connection':
                      return <CheckCircleIcon className="h-4 w-4 text-emerald-500" />
                    default:
                      return <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                  }
                }

                const getEventBgColor = (type: string) => {
                  switch (type) {
                    case 'message':
                      return 'bg-blue-50 border-l-blue-300'
                    case 'system':
                      return 'bg-green-50 border-l-green-300'
                    case 'connection':
                      return 'bg-emerald-50 border-l-emerald-300'
                    default:
                      return 'bg-gray-50 border-l-gray-300'
                  }
                }

                return (
                  <div key={index} className={`flex items-start space-x-3 p-3 rounded-lg border-l-4 transition-colors ${getEventBgColor(event.type)}`}>
                    <div className="flex-shrink-0 mt-0.5">
                      {getEventIcon(event.type)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium text-gray-900">{event.message}</p>
                        <span className="text-xs text-gray-400 uppercase tracking-wider">
                          {event.type}
                        </span>
                      </div>
                      {event.details && (
                        <p className="text-xs text-gray-600 mt-1">{event.details}</p>
                      )}
                      <p className="text-xs text-gray-500 mt-1">
                        {new Date(event.timestamp).toLocaleString('es-ES', {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                          second: '2-digit'
                        })}
                      </p>
                    </div>
                  </div>
                )
              })
            ) : (
              <div className="text-center text-gray-500 py-4">
                No hay eventos recientes
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Métricas de conversaciones */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Métricas de Conversaciones</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600">
              {systemStats.conversations?.active_chats || 0}
            </div>
            <div className="text-sm text-gray-500">Chats Activos</div>
          </div>

          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">
              {systemStats.messages?.automated_responses || 0}
            </div>
            <div className="text-sm text-gray-500">Respuestas Automáticas</div>
          </div>

          <div className="text-center">
            <div className="text-2xl font-bold text-purple-600">
              {systemStats.messages?.avg_response_time || 0}s
            </div>
            <div className="text-sm text-gray-500">Tiempo Promedio</div>
          </div>

          <div className="text-center">
            <div className="text-2xl font-bold text-yellow-600">
              {systemStats.conversations?.avg_conversation_length || 0}
            </div>
            <div className="text-sm text-gray-500">Mensajes por Chat</div>
          </div>
        </div>
      </div>
    </div>
  )
}