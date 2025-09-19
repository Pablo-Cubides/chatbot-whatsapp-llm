import React, { useState, useEffect, useCallback } from 'react'
import apiService from '@/lib/api'

interface CostEvent {
  id: number
  timestamp: string
  service: string
  model: string
  operation_type: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  input_cost_usd: number
  output_cost_usd: number
  total_cost_usd: number
  user_id?: string
  conversation_id?: string
  session_id?: string
  metadata?: Record<string, any>
}

interface BudgetLimit {
  id: number
  name: string
  limit_type: string
  amount_usd: number
  current_spent_usd: number
  alert_threshold_percent: number
  services: string[]
  users: string[]
  created_at: string
  updated_at: string
  active: boolean
}

interface CostAlert {
  id: number
  timestamp: string
  level: 'info' | 'warning' | 'critical' | 'emergency'
  title: string
  message: string
  budget_id?: number
  service?: string
  current_amount_usd: number
  threshold_amount_usd: number
  acknowledged: boolean
  metadata?: Record<string, any>
}

interface UsageStats {
  total_cost_usd: number
  total_tokens: number
  total_requests: number
  average_cost_per_request: number
  cost_by_service: Record<string, number>
  cost_by_model: Record<string, number>
  tokens_by_service: Record<string, number>
  most_expensive_request?: CostEvent
  cost_trend_7d: number[]
}

interface CostDashboardData {
  stats: UsageStats
  recent_events: CostEvent[]
  budgets: BudgetLimit[]
  alerts: CostAlert[]
  success: boolean
}

const CostManagementDashboard: React.FC = () => {
  const [dashboardData, setDashboardData] = useState<CostDashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedPeriod, setSelectedPeriod] = useState<'daily' | 'weekly' | 'monthly'>('daily')
  const [showCreateBudget, setShowCreateBudget] = useState(false)
  const [newBudget, setNewBudget] = useState({
    name: '',
    limit_type: 'daily' as const,
    amount_usd: '',
    alert_threshold_percent: 80,
    services: [] as string[]
  })

  const fetchDashboardData = useCallback(async () => {
    try {
      const response = await apiService.getCostDashboard(selectedPeriod)
      if (response.success) {
        setDashboardData(response)
      }
    } catch (error) {
      console.error('Error fetching dashboard data:', error)
    } finally {
      setLoading(false)
    }
  }, [selectedPeriod])

  const createBudget = async () => {
    try {
      await apiService.createBudgetLimit({
        name: newBudget.name,
        limit_type: newBudget.limit_type,
        amount_usd: parseFloat(newBudget.amount_usd),
        alert_threshold_percent: newBudget.alert_threshold_percent,
        services: newBudget.services.length > 0 ? newBudget.services : undefined
      })
      
      setShowCreateBudget(false)
      setNewBudget({
        name: '',
        limit_type: 'daily',
        amount_usd: '',
        alert_threshold_percent: 80,
        services: []
      })
      fetchDashboardData()
    } catch (error) {
      console.error('Error creating budget:', error)
    }
  }

  const acknowledgeAlert = async (alertId: number) => {
    try {
      await apiService.acknowledgeAlert(alertId)
      fetchDashboardData()
    } catch (error) {
      console.error('Error acknowledging alert:', error)
    }
  }

  useEffect(() => {
    fetchDashboardData()
  }, [fetchDashboardData])

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 4
    }).format(amount)
  }

  const formatNumber = (num: number) => {
    return new Intl.NumberFormat('en-US').format(num)
  }

  const getAlertIcon = (level: string) => {
    switch (level) {
      case 'emergency':
        return '🚨'
      case 'critical':
        return '❌'
      case 'warning':
        return '⚠️'
      default:
        return 'ℹ️'
    }
  }

  const getAlertColor = (level: string) => {
    switch (level) {
      case 'emergency':
        return '#dc2626'
      case 'critical':
        return '#ef4444'
      case 'warning':
        return '#f59e0b'
      default:
        return '#3b82f6'
    }
  }

  const getServiceDisplayName = (service: string) => {
    const names: Record<string, string> = {
      'openai': 'OpenAI',
      'claude': 'Claude',
      'gemini': 'Gemini',
      'xai': 'X.AI',
      'ollama': 'Ollama'
    }
    return names[service] || service
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
          💰 Cost Management Dashboard
        </h2>
        <div style={{ textAlign: 'center', padding: '32px 0' }}>
          🔄 Loading cost data...
        </div>
      </div>
    )
  }

  if (!dashboardData) {
    return (
      <div style={{ 
        border: '1px solid #e5e7eb', 
        borderRadius: '8px', 
        padding: '24px',
        backgroundColor: 'white',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
      }}>
        <h2 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px' }}>
          💰 Cost Management Dashboard
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
          ⚠️ Unable to load cost data. Please check your connection.
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
            💰 Cost Management Dashboard
          </h2>
          <div style={{ display: 'flex', gap: '8px' }}>
            <select
              value={selectedPeriod}
              onChange={(e) => setSelectedPeriod(e.target.value as any)}
              style={{
                padding: '6px 12px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                backgroundColor: 'white',
                fontSize: '14px'
              }}
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
            <button
              onClick={() => setShowCreateBudget(true)}
              style={{
                padding: '6px 12px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                backgroundColor: '#f0fdf4',
                cursor: 'pointer',
                fontSize: '14px',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}
            >
              ➕ New Budget
            </button>
            <button
              onClick={fetchDashboardData}
              style={{
                padding: '6px 12px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                backgroundColor: 'white',
                cursor: 'pointer',
                fontSize: '14px',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}
            >
              🔄 Refresh
            </button>
          </div>
        </div>
        
        {/* Quick stats */}
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', 
          gap: '16px',
          fontSize: '14px'
        }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#ef4444' }}>
              {formatCurrency(dashboardData.stats.total_cost_usd)}
            </div>
            <div style={{ color: '#6b7280' }}>Total Cost</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#3b82f6' }}>
              {formatNumber(dashboardData.stats.total_tokens)}
            </div>
            <div style={{ color: '#6b7280' }}>Total Tokens</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#10b981' }}>
              {formatNumber(dashboardData.stats.total_requests)}
            </div>
            <div style={{ color: '#6b7280' }}>Requests</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#8b5cf6' }}>
              {formatCurrency(dashboardData.stats.average_cost_per_request)}
            </div>
            <div style={{ color: '#6b7280' }}>Avg/Request</div>
          </div>
        </div>
      </div>

      {/* Alerts section */}
      {dashboardData.alerts.length > 0 && (
        <div style={{ 
          border: '1px solid #e5e7eb', 
          borderRadius: '8px', 
          padding: '20px',
          backgroundColor: 'white',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
        }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '16px', fontWeight: 'bold' }}>
            🚨 Active Alerts ({dashboardData.alerts.filter(a => !a.acknowledged).length})
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {dashboardData.alerts.filter(alert => !alert.acknowledged).map(alert => (
              <div key={alert.id} style={{ 
                border: `1px solid ${getAlertColor(alert.level)}`, 
                borderRadius: '6px', 
                padding: '12px',
                backgroundColor: `${getAlertColor(alert.level)}08`,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '20px' }}>{getAlertIcon(alert.level)}</span>
                  <div>
                    <div style={{ fontWeight: 'bold', color: getAlertColor(alert.level) }}>
                      {alert.title}
                    </div>
                    <div style={{ fontSize: '14px', color: '#6b7280' }}>
                      {alert.message}
                    </div>
                    <div style={{ fontSize: '12px', color: '#9ca3af' }}>
                      {new Date(alert.timestamp).toLocaleString()}
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => acknowledgeAlert(alert.id)}
                  style={{
                    padding: '4px 8px',
                    border: '1px solid #d1d5db',
                    borderRadius: '4px',
                    backgroundColor: 'white',
                    cursor: 'pointer',
                    fontSize: '12px'
                  }}
                >
                  ✓ Acknowledge
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Budget limits and cost breakdown */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        {/* Budget limits */}
        <div style={{ 
          border: '1px solid #e5e7eb', 
          borderRadius: '8px', 
          padding: '20px',
          backgroundColor: 'white',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
        }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '16px', fontWeight: 'bold' }}>
            📊 Budget Limits
          </h3>
          {dashboardData.budgets.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '24px 0', color: '#6b7280' }}>
              No budget limits configured
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {dashboardData.budgets.map(budget => {
                const usagePercent = budget.amount_usd > 0 ? 
                  (budget.current_spent_usd / budget.amount_usd) * 100 : 0
                const isOverBudget = usagePercent > 100
                const isNearLimit = usagePercent > budget.alert_threshold_percent
                
                return (
                  <div key={budget.id} style={{ 
                    border: '1px solid #e5e7eb', 
                    borderRadius: '6px', 
                    padding: '12px'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <div style={{ fontWeight: 'bold' }}>{budget.name}</div>
                      <div style={{ 
                        fontSize: '12px',
                        padding: '2px 6px',
                        borderRadius: '4px',
                        backgroundColor: '#f3f4f6',
                        textTransform: 'capitalize'
                      }}>
                        {budget.limit_type}
                      </div>
                    </div>
                    <div style={{ fontSize: '14px', marginBottom: '8px' }}>
                      {formatCurrency(budget.current_spent_usd)} / {formatCurrency(budget.amount_usd)}
                      <span style={{ 
                        color: isOverBudget ? '#ef4444' : isNearLimit ? '#f59e0b' : '#10b981',
                        marginLeft: '8px',
                        fontWeight: 'bold'
                      }}>
                        ({usagePercent.toFixed(1)}%)
                      </span>
                    </div>
                    <div style={{ width: '100%', height: '8px', backgroundColor: '#e5e7eb', borderRadius: '4px', overflow: 'hidden' }}>
                      <div style={{
                        width: `${Math.min(usagePercent, 100)}%`,
                        height: '100%',
                        backgroundColor: isOverBudget ? '#ef4444' : isNearLimit ? '#f59e0b' : '#10b981',
                        transition: 'width 0.3s ease'
                      }} />
                    </div>
                    {budget.services.length > 0 && (
                      <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '4px' }}>
                        Services: {budget.services.join(', ')}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Cost by service */}
        <div style={{ 
          border: '1px solid #e5e7eb', 
          borderRadius: '8px', 
          padding: '20px',
          backgroundColor: 'white',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
        }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '16px', fontWeight: 'bold' }}>
            🏢 Cost by Service
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {Object.entries(dashboardData.stats.cost_by_service).map(([service, cost]) => {
              const percentage = dashboardData.stats.total_cost_usd > 0 ? 
                (cost / dashboardData.stats.total_cost_usd) * 100 : 0
              
              return (
                <div key={service} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <div style={{ fontWeight: 'bold' }}>{getServiceDisplayName(service)}</div>
                    <div style={{ fontSize: '12px', color: '#6b7280' }}>
                      ({percentage.toFixed(1)}%)
                    </div>
                  </div>
                  <div style={{ fontWeight: 'bold' }}>{formatCurrency(cost)}</div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Cost trend chart (simplified) */}
      {dashboardData.stats.cost_trend_7d.length > 0 && (
        <div style={{ 
          border: '1px solid #e5e7eb', 
          borderRadius: '8px', 
          padding: '20px',
          backgroundColor: 'white',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
        }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '16px', fontWeight: 'bold' }}>
            📈 Cost Trend (Last 7 Days)
          </h3>
          <div style={{ display: 'flex', alignItems: 'end', gap: '4px', height: '100px' }}>
            {dashboardData.stats.cost_trend_7d.map((cost, index) => {
              const maxCost = Math.max(...dashboardData.stats.cost_trend_7d)
              const height = maxCost > 0 ? (cost / maxCost) * 100 : 0
              
              return (
                <div key={index} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  <div
                    style={{
                      width: '100%',
                      height: `${Math.max(height, 2)}%`,
                      backgroundColor: '#3b82f6',
                      borderRadius: '2px 2px 0 0',
                      marginBottom: '4px'
                    }}
                    title={`Day ${index + 1}: ${formatCurrency(cost)}`}
                  />
                  <div style={{ fontSize: '10px', color: '#6b7280' }}>
                    D{index + 1}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Recent transactions */}
      <div style={{ 
        border: '1px solid #e5e7eb', 
        borderRadius: '8px', 
        padding: '20px',
        backgroundColor: 'white',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
      }}>
        <h3 style={{ margin: '0 0 16px 0', fontSize: '16px', fontWeight: 'bold' }}>
          📝 Recent Transactions
        </h3>
        {dashboardData.recent_events.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '24px 0', color: '#6b7280' }}>
            No recent transactions
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {dashboardData.recent_events.slice(0, 10).map(event => (
              <div key={event.id} style={{ 
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '8px',
                backgroundColor: '#f9fafb',
                borderRadius: '4px'
              }}>
                <div>
                  <div style={{ fontWeight: 'bold', fontSize: '14px' }}>
                    {getServiceDisplayName(event.service)} - {event.model}
                  </div>
                  <div style={{ fontSize: '12px', color: '#6b7280' }}>
                    {formatNumber(event.total_tokens)} tokens • {new Date(event.timestamp).toLocaleString()}
                  </div>
                </div>
                <div style={{ fontWeight: 'bold', color: '#ef4444' }}>
                  {formatCurrency(event.total_cost_usd)}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create budget modal */}
      {showCreateBudget && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: 'white',
            padding: '24px',
            borderRadius: '8px',
            width: '400px',
            maxHeight: '80vh',
            overflow: 'auto'
          }}>
            <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: 'bold' }}>
              Create New Budget Limit
            </h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '4px', fontWeight: 'bold' }}>Name</label>
                <input
                  type="text"
                  value={newBudget.name}
                  onChange={(e) => setNewBudget({ ...newBudget, name: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '8px',
                    border: '1px solid #d1d5db',
                    borderRadius: '4px'
                  }}
                  placeholder="e.g., Daily OpenAI Budget"
                />
              </div>
              
              <div>
                <label style={{ display: 'block', marginBottom: '4px', fontWeight: 'bold' }}>Period</label>
                <select
                  value={newBudget.limit_type}
                  onChange={(e) => setNewBudget({ ...newBudget, limit_type: e.target.value as any })}
                  style={{
                    width: '100%',
                    padding: '8px',
                    border: '1px solid #d1d5db',
                    borderRadius: '4px'
                  }}
                >
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                  <option value="total">Total</option>
                </select>
              </div>
              
              <div>
                <label style={{ display: 'block', marginBottom: '4px', fontWeight: 'bold' }}>Amount (USD)</label>
                <input
                  type="number"
                  step="0.01"
                  value={newBudget.amount_usd}
                  onChange={(e) => setNewBudget({ ...newBudget, amount_usd: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '8px',
                    border: '1px solid #d1d5db',
                    borderRadius: '4px'
                  }}
                  placeholder="e.g., 10.00"
                />
              </div>
              
              <div>
                <label style={{ display: 'block', marginBottom: '4px', fontWeight: 'bold' }}>Alert Threshold (%)</label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={newBudget.alert_threshold_percent}
                  onChange={(e) => setNewBudget({ ...newBudget, alert_threshold_percent: parseInt(e.target.value) })}
                  style={{
                    width: '100%',
                    padding: '8px',
                    border: '1px solid #d1d5db',
                    borderRadius: '4px'
                  }}
                />
              </div>
            </div>
            
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '20px' }}>
              <button
                onClick={() => setShowCreateBudget(false)}
                style={{
                  padding: '8px 16px',
                  border: '1px solid #d1d5db',
                  borderRadius: '4px',
                  backgroundColor: 'white',
                  cursor: 'pointer'
                }}
              >
                Cancel
              </button>
              <button
                onClick={createBudget}
                disabled={!newBudget.name || !newBudget.amount_usd}
                style={{
                  padding: '8px 16px',
                  border: '1px solid #10b981',
                  borderRadius: '4px',
                  backgroundColor: '#10b981',
                  color: 'white',
                  cursor: newBudget.name && newBudget.amount_usd ? 'pointer' : 'not-allowed',
                  opacity: newBudget.name && newBudget.amount_usd ? 1 : 0.6
                }}
              >
                Create Budget
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default CostManagementDashboard