import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'

// Mock apiService used by component
jest.mock('@/lib/api', () => ({
  getRealTimeStatus: jest.fn(),
  getAllRecommendations: jest.fn(),
  forceStatusUpdate: jest.fn()
}))

// Mock socket.io-client to allow emitting events
jest.mock('socket.io-client', () => {
  const listeners: Record<string, Function[]> = {}
  return {
    io: () => ({
      on: (event: string, cb: Function) => {
        listeners[event] = listeners[event] || []
        listeners[event].push(cb)
      },
      emit: (event: string, data: any) => {
        if (listeners[event]) {
          listeners[event].forEach(cb => cb(data))
        }
      },
      disconnect: () => {}
    }),
    __esModule: true
  }
})

import apiService from '@/lib/api'
import ServiceStatusMonitor from '@/components/ServiceStatusMonitor'

describe('ServiceStatusMonitor realtime', () => {
  beforeEach(() => {
    jest.resetAllMocks()
  })

  test('displays initial status and updates on socket event', async () => {
    const initial = {
      success: true,
      timestamp: new Date().toISOString(),
      monitoring_active: true,
      services: {
        openai: {
          service_name: 'openai',
          status: 'online',
          latency_ms: 120,
          last_check: new Date().toISOString(),
          response_time_trend: [100, 110, 120],
          uptime_percentage: 99.9,
          api_key_configured: true
        }
      },
      summary: {
        overall_status: 'healthy',
        total_services: 1,
        online: 1,
        degraded: 0,
        offline: 0,
        average_latency_ms: 120,
        last_update: new Date().toISOString()
      }
    }

    ;(apiService.getRealTimeStatus as jest.Mock).mockResolvedValueOnce(initial)
    ;(apiService.getAllRecommendations as jest.Mock).mockResolvedValueOnce({ success: true, recommendations: {} })

    render(<ServiceStatusMonitor />)

  // There may be multiple 'Online' labels; assert at least one is present
  await waitFor(() => expect(screen.getAllByText(/Online/).length).toBeGreaterThan(0))

    // Simulate a socket event that sets openai to offline
    const { io } = require('socket.io-client')
    const socket = io()
    socket.emit('status:update', {
      ...initial,
      services: {
        openai: {
          ...initial.services.openai,
          status: 'offline',
          latency_ms: 9999
        }
      },
      summary: { ...initial.summary, online: 0, offline: 1 }
    })

  await waitFor(() => expect(screen.getAllByText(/Offline/).length).toBeGreaterThan(0))
  })
})
