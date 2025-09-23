import React from 'react'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import CostManagementDashboard from '@/components/CostManagementDashboard'

// Mock the apiService used by the dashboard
jest.mock('@/lib/api', () => ({
  getCostDashboard: jest.fn(),
  createBudgetLimit: jest.fn()
}))

import apiService from '@/lib/api'

describe('CostManagementDashboard', () => {
  beforeEach(() => {
    jest.resetAllMocks()
  })

  test('renders loading state and then dashboard data', async () => {
    const fakeData = {
      success: true,
      stats: {
        total_cost_usd: 123.4567,
        total_tokens: 1000,
        total_requests: 42,
        average_cost_per_request: 2.938,
        cost_by_service: {},
        cost_by_model: {},
        tokens_by_service: {},
        cost_trend_7d: []
      },
      recent_events: [],
      budgets: [],
      alerts: []
    }

    ;(apiService.getCostDashboard as jest.Mock).mockResolvedValueOnce(fakeData)

    render(<CostManagementDashboard />)

    // Initially show loading
    expect(screen.getByText(/Loading cost data/i)).toBeInTheDocument()

    // Wait for data to be loaded and stats to appear
    await waitFor(() => expect(screen.getByText(/Total Cost/i)).toBeInTheDocument())

    expect(screen.getByText(/\$123.4567/)).toBeInTheDocument()
  // Tokens may be formatted with commas (e.g. "1,000")
  expect(screen.getByText(/1,?000/)).toBeInTheDocument()
    expect(screen.getByText(/42/)).toBeInTheDocument()
  })

  test('shows error state when api fails', async () => {
    ;(apiService.getCostDashboard as jest.Mock).mockRejectedValueOnce(new Error('Network error'))

    render(<CostManagementDashboard />)

    await waitFor(() => expect(screen.getByText(/Unable to load cost data/i)).toBeInTheDocument())
  })

  test('can open create budget modal and submit', async () => {
    const fakeData = {
      success: true,
      stats: {
        total_cost_usd: 0,
        total_tokens: 0,
        total_requests: 0,
        average_cost_per_request: 0,
        cost_by_service: {},
        cost_by_model: {},
        tokens_by_service: {},
        cost_trend_7d: []
      },
      recent_events: [],
      budgets: [],
      alerts: []
    }

    ;(apiService.getCostDashboard as jest.Mock).mockResolvedValue(fakeData)
    ;(apiService.createBudgetLimit as jest.Mock).mockResolvedValue({ success: true })

    render(<CostManagementDashboard />)

    await waitFor(() => expect(screen.getByText(/New Budget/i)).toBeInTheDocument())

    fireEvent.click(screen.getByText(/New Budget/i))

    // Fill required fields in the modal using placeholders
    const nameInput = screen.getByPlaceholderText(/e\.g\., Daily OpenAI Budget/i)
    fireEvent.change(nameInput, { target: { value: 'Test Budget' } })

    const amountInput = screen.getByPlaceholderText(/e\.g\., 10\.00/i)
    fireEvent.change(amountInput, { target: { value: '10.00' } })

    // Click the specific button labeled 'Create Budget' to avoid matching headings
    const createBtn = screen.getByRole('button', { name: /Create Budget/i })
    fireEvent.click(createBtn)

    await waitFor(() => expect(apiService.createBudgetLimit).toHaveBeenCalled())
  })
})
