import React from 'react'
import { render, screen } from '@testing-library/react'
import { fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'

// We'll mock `next/link` to a simple anchor that calls a mock push function
const mockPush = jest.fn()
jest.mock('next/link', () => {
  return ({ href, children }: any) => {
    return (
      <a href={href} data-test-link onClick={(e) => { e.preventDefault(); mockPush(href); }}>
        {children}
      </a>
    )
  }
})

import DashboardLayout from '@/components/Layout/DashboardLayout'
import { Providers, useApp } from '@/app/providers'

function TestChild({ text }: { text: string }) {
  const { systemStatus } = useApp()
  return (
    <div>
      <div data-testid="child">{text}</div>
      <div data-testid="status">{systemStatus}</div>
    </div>
  )
}

describe('Main navigation', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  test('renders expected links and clicking calls router push and preserves app state', async () => {
    
    render(
      <Providers>
        <DashboardLayout>
          <TestChild text="Home page" />
        </DashboardLayout>
      </Providers>
    )

    // Assert navigation links exist with proper hrefs
    const links = [
      ['/dashboard', /Dashboard/i],
      ['/messaging', /Mensajería/i],
      ['/contacts', /Contactos/i],
      ['/templates', /Plantillas/i],
      ['/analytics', /Estadísticas/i],
      ['/settings', /Configuración/i],
    ]

    for (const [href, label] of links) {
      const link = screen.getAllByText(label)[0]
      expect(link).toBeInTheDocument()
      // find the nearest anchor
      const anchor = link.closest('a') as HTMLAnchorElement
      expect(anchor).toHaveAttribute('href', href)
  // click and assert push called
  fireEvent.click(anchor)
      expect(mockPush).toHaveBeenCalledWith(href)
    }

    // State should remain (Providers sets systemStatus to 'online')
    expect(screen.getByTestId('status')).toHaveTextContent('online')
  })
})
