import React, { useState, useEffect, useCallback } from 'react'
import apiService from '@/lib/api'

interface ServiceStatus {
  service_name: string
  status: 'online' | 'degraded' | 'offline' | 'checking' | 'unknown'
  latency_ms: number
  last_check: string
  error_message?: string
  response_time_trend: number[]
  uptime_percentage: number
  api_key_configured: boolean
  rate_limit_remaining?: number
  rate_limit_reset?: string
}

interface StatusSummary {
  overall_status: 'healthy' | 'degraded' | 'critical'
  total_services: number
  online: number
  degraded: number
  offline: number
  average_latency_ms: number
  last_update: string
}

interface RealtimeStatusData {
  timestamp: string
  monitoring_active: boolean
  services: Record<string, ServiceStatus>
  summary: StatusSummary
}

const ServiceStatusMonitor: React.FC = () => {
  const [statusData, setStatusData] = useState<RealtimeStatusData | null>(null)
  const [recommendations, setRecommendations] = useState<Record<string, string[]>>({})
  const [loading, setLoading] = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [refreshInterval, setRefreshInterval] = useState<NodeJS.Timeout | null>(null)

  const fetchStatus = useCallback(async () => {
    try {
      const response = await apiService.getRealTimeStatus()
      if (response.success) {
        setStatusData(response)
      }
    } catch (error) {
      console.error('Error fetching status:', error)
    }
  }, [])

  const fetchRecommendations = useCallback(async () => {
    try {
      const response = await apiService.getAllRecommendations()
      if (response.success) {
        setRecommendations(response.recommendations)
      }
    } catch (error) {
      console.error('Error fetching recommendations:', error)
    }
  }, [])

  const forceUpdate = async () => {
    setLoading(true)
    try {
      await apiService.forceStatusUpdate()
      setTimeout(() => {
        fetchStatus()
        fetchRecommendations()
      }, 2000) // Esperar 2 segundos para que se complete la verificación
    } catch (error) {
      console.error('Error forcing update:', error)
    } finally {
      setLoading(false)
    }
  }

  const toggleAutoRefresh = () => {
    setAutoRefresh(!autoRefresh)
  }

  useEffect(() => {
    // Carga inicial
    Promise.all([fetchStatus(), fetchRecommendations()]).finally(() => {
      setLoading(false)
    })
  }, [fetchStatus, fetchRecommendations])

  useEffect(() => {
    // Auto-refresh
    if (autoRefresh) {
      const interval = setInterval(() => {
        fetchStatus()
        fetchRecommendations()
      }, 30000) // Cada 30 segundos
      setRefreshInterval(interval)
    } else {
      if (refreshInterval) {
        clearInterval(refreshInterval)
        setRefreshInterval(null)
      }
    }

    return () => {
      if (refreshInterval) {
        clearInterval(refreshInterval)
      }
    }
  }, [autoRefresh, fetchStatus, fetchRecommendations])

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'online':
        return '✅'
      case 'degraded':
        return '⚠️'
      case 'offline':
        return '❌'
      case 'checking':
        return '🔄'
      default:
        return '❓'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'online':
        return '#10b981'
      case 'degraded':
        return '#f59e0b'
      case 'offline':
        return '#ef4444'
      case 'checking':
        return '#3b82f6'
      default:
        return '#6b7280'
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case 'online':
        return 'Online'
      case 'degraded':
        return 'Degraded'
      case 'offline':
        return 'Offline'
      case 'checking':
        return 'Checking...'
      default:
        return 'Unknown'
    }
  }

  const getServiceDisplayName = (serviceName: string) => {
    const names: Record<string, string> = {
      'openai': 'OpenAI GPT',
      'claude': 'Anthropic Claude',
      'gemini': 'Google Gemini',
      'xai': 'X.AI Grok',
      'ollama': 'Ollama Local'
    }
    return names[serviceName] || serviceName
  }

  const formatLatency = (latency: number) => {
    if (latency < 1000) {
      return `${Math.round(latency)}ms`
    }
    return `${(latency / 1000).toFixed(1)}s`
  }

  if (loading) {
    return (
      <div style={{ 
        border: '1px solid #e5e7eb', 
        borderRadius: '8px', 
        padding: '24px',
        backgroundColor: 'white',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
      }}>
        <h2 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px' }}>
          📊 Service Status Monitor
        </h2>
        <div style={{ textAlign: 'center', padding: '32px 0' }}>
          🔄 Loading service status...
        </div>
      </div>
    )
  }

  if (!statusData) {
    return (
      <div style={{ 
        border: '1px solid #e5e7eb', 
        borderRadius: '8px', 
        padding: '24px',
        backgroundColor: 'white',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
      }}>
        <h2 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px' }}>
          📊 Service Status Monitor
        </h2>
        <div style={{ 
          backgroundColor: '#fef3c7', 
          border: '1px solid #f59e0b', 
          borderRadius: '6px', 
          padding: '12px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          ⚠️ Unable to load service status. Please check your connection.
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header with controls */}
      <div style={{ 
        border: '1px solid #e5e7eb', 
        borderRadius: '8px', 
        padding: '24px',
        backgroundColor: 'white',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px' }}>
            📊 Service Status Monitor
            <span style={{
              backgroundColor: statusData.summary.overall_status === 'healthy' ? '#10b981' : '#ef4444',
              color: 'white',
              padding: '4px 8px',
              borderRadius: '4px',
              fontSize: '12px',
              textTransform: 'capitalize'
            }}>
              {statusData.summary.overall_status}
            </span>
          </h2>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={toggleAutoRefresh}
              style={{
                padding: '6px 12px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                backgroundColor: autoRefresh ? '#f0fdf4' : 'white',
                cursor: 'pointer',
                fontSize: '14px',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}
            >
              ⚡ Auto: {autoRefresh ? 'ON' : 'OFF'}
            </button>
            <button
              onClick={forceUpdate}
              disabled={loading}
              style={{
                padding: '6px 12px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                backgroundColor: 'white',
                cursor: loading ? 'not-allowed' : 'pointer',
                fontSize: '14px',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                opacity: loading ? 0.6 : 1
              }}
            >
              🔄 Refresh
            </button>
          </div>
        </div>
        
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', 
          gap: '16px',
          fontSize: '14px'
        }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#10b981' }}>{statusData.summary.online}</div>
            <div style={{ color: '#6b7280' }}>Online</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#f59e0b' }}>{statusData.summary.degraded}</div>
            <div style={{ color: '#6b7280' }}>Degraded</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#ef4444' }}>{statusData.summary.offline}</div>
            <div style={{ color: '#6b7280' }}>Offline</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#3b82f6' }}>
              {formatLatency(statusData.summary.average_latency_ms)}
            </div>
            <div style={{ color: '#6b7280' }}>Avg Latency</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#8b5cf6' }}>{statusData.summary.total_services}</div>
            <div style={{ color: '#6b7280' }}>Total Services</div>
          </div>
        </div>
      </div>

      {/* Individual service status */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', 
        gap: '16px' 
      }}>
        {Object.entries(statusData.services).map(([serviceName, service]) => (
          <div key={serviceName} style={{ 
            border: '1px solid #e5e7eb', 
            borderRadius: '8px', 
            padding: '20px',
            backgroundColor: 'white',
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 'bold' }}>
                {getServiceDisplayName(serviceName)}
              </h3>
              <span style={{ fontSize: '20px' }}>{getStatusIcon(service.status)}</span>
            </div>
            
            <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', flexWrap: 'wrap' }}>
              <span style={{
                backgroundColor: getStatusColor(service.status),
                color: 'white',
                padding: '4px 8px',
                borderRadius: '4px',
                fontSize: '12px',
                fontWeight: 'bold'
              }}>
                {getStatusText(service.status)}
              </span>
              {!service.api_key_configured && serviceName !== 'ollama' && (
                <span style={{
                  backgroundColor: '#f59e0b',
                  color: 'white',
                  padding: '4px 8px',
                  borderRadius: '4px',
                  fontSize: '12px',
                  fontWeight: 'bold'
                }}>
                  ⚙️ No API Key
                </span>
              )}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {/* Latency */}
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '14px' }}>
                <span style={{ color: '#6b7280' }}>Latency:</span>
                <span style={{ fontWeight: 'bold' }}>{formatLatency(service.latency_ms)}</span>
              </div>

              {/* Uptime */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '14px', marginBottom: '4px' }}>
                  <span style={{ color: '#6b7280' }}>Uptime:</span>
                  <span style={{ fontWeight: 'bold' }}>{service.uptime_percentage.toFixed(1)}%</span>
                </div>
                <div style={{ width: '100%', height: '8px', backgroundColor: '#e5e7eb', borderRadius: '4px', overflow: 'hidden' }}>
                  <div style={{
                    width: `${service.uptime_percentage}%`,
                    height: '100%',
                    backgroundColor: getStatusColor(service.status),
                    transition: 'width 0.3s ease'
                  }} />
                </div>
              </div>

              {/* Response time trend */}
              {service.response_time_trend && service.response_time_trend.length > 0 && (
                <div>
                  <div style={{ fontSize: '14px', color: '#6b7280', marginBottom: '4px' }}>
                    📈 Response Trend
                  </div>
                  <div style={{ display: 'flex', alignItems: 'end', gap: '2px', height: '32px' }}>
                    {service.response_time_trend.slice(-10).map((time, index) => {
                      const maxTime = Math.max(...service.response_time_trend)
                      const height = maxTime > 0 ? (time / maxTime) * 100 : 0
                      return (
                        <div
                          key={index}
                          style={{
                            width: '8px',
                            height: `${Math.max(height, 5)}%`,
                            backgroundColor: getStatusColor(service.status),
                            opacity: 0.7,
                            borderRadius: '1px'
                          }}
                          title={`${formatLatency(time)}`}
                        />
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Error message */}
              {service.error_message && (
                <div style={{ 
                  backgroundColor: '#fef2f2', 
                  border: '1px solid #fecaca', 
                  borderRadius: '6px', 
                  padding: '8px',
                  fontSize: '14px',
                  display: 'flex',
                  alignItems: 'start',
                  gap: '6px'
                }}>
                  ⚠️ {service.error_message}
                </div>
              )}

              {/* Recommendations */}
              {recommendations[serviceName] && recommendations[serviceName].length > 0 && (
                <div>
                  <div style={{ fontSize: '14px', fontWeight: 'bold', color: '#374151', marginBottom: '4px' }}>
                    Recommendations:
                  </div>
                  <ul style={{ fontSize: '12px', color: '#6b7280', margin: 0, paddingLeft: '16px' }}>
                    {recommendations[serviceName].map((rec, index) => (
                      <li key={index} style={{ marginBottom: '2px' }}>
                        {rec}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Last check */}
              <div style={{ 
                fontSize: '12px', 
                color: '#9ca3af', 
                paddingTop: '8px', 
                borderTop: '1px solid #e5e7eb' 
              }}>
                Last check: {new Date(service.last_check).toLocaleTimeString()}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Monitoring status */}
      <div style={{ 
        border: '1px solid #e5e7eb', 
        borderRadius: '8px', 
        padding: '16px',
        backgroundColor: 'white',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: statusData.monitoring_active ? '#10b981' : '#ef4444'
            }} />
            <span style={{ color: '#6b7280' }}>
              Monitoring: {statusData.monitoring_active ? 'Active' : 'Inactive'}
            </span>
          </div>
          <span style={{ color: '#9ca3af' }}>
            Last update: {new Date(statusData.timestamp).toLocaleTimeString()}
          </span>
        </div>
      </div>
    </div>
  )
}

export default ServiceStatusMonitor