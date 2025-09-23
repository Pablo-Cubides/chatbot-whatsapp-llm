import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'

// Create shared mock functions so both the component (which imports named `apiService`)
// and this test (which imports default) use the same mock implementations.
const mockGetAllowedContacts = jest.fn()
const mockAddAllowedContact = jest.fn()
const mockSendWhatsAppMessage = jest.fn()
const mockListMedia = jest.fn()

jest.mock('@/lib/api', () => ({
  __esModule: true,
  apiService: {
    getAllowedContacts: mockGetAllowedContacts,
    addAllowedContact: mockAddAllowedContact,
    sendWhatsAppMessage: mockSendWhatsAppMessage,
    listMedia: mockListMedia
  },
  // also provide default export used by tests
  default: {
    getAllowedContacts: mockGetAllowedContacts,
    addAllowedContact: mockAddAllowedContact,
    sendWhatsAppMessage: mockSendWhatsAppMessage,
    listMedia: mockListMedia
  }
}))

import apiService from '@/lib/api'
import { ContactsPage } from '@/components/pages/ContactsPage'

describe('ContactsPage form interactions', () => {
  beforeEach(() => {
    jest.resetAllMocks()
    // Ensure media list call doesn't cause undefined responses during mount
    mockListMedia.mockResolvedValue({ status: 'success', files: [] })
  })

  test('adds a contact when form is filled and submitted', async () => {
    ;(apiService.getAllowedContacts as jest.Mock).mockResolvedValueOnce([])
    ;(apiService.addAllowedContact as jest.Mock).mockResolvedValueOnce({ status: 'success' })

    render(<ContactsPage />)

    // Open add form
    fireEvent.click(screen.getByText(/Agregar/i))

    // Fill inputs
    fireEvent.change(screen.getByPlaceholderText(/Nombre del contacto/i), { target: { value: 'Juan Perez' } })
    fireEvent.change(screen.getByPlaceholderText(/Número de teléfono/i), { target: { value: '+549112345678' } })

    // Submit
    fireEvent.click(screen.getByRole('button', { name: /Agregar Contacto/i }))

    await waitFor(() => expect(apiService.addAllowedContact).toHaveBeenCalled())
  })

  test('sends a single message when message is entered and send clicked', async () => {
    const mockContacts = [{ contact_name: 'Cliente', phone_number: '+5491123', chat_id: '123' }]
    ;(apiService.getAllowedContacts as jest.Mock).mockResolvedValueOnce(mockContacts)
    ;(apiService.sendWhatsAppMessage as jest.Mock).mockResolvedValueOnce({ status: 'success' })

  render(<ContactsPage />)

  // Wait for the contact item and its send button to appear
  await waitFor(() => expect(screen.getAllByTitle(/Enviar mensaje/i).length).toBeGreaterThan(0))
  const sendButtons = screen.getAllByTitle(/Enviar mensaje/i)
  fireEvent.click(sendButtons[0])

    // The single message form should appear; fill and send
    await waitFor(() => expect(screen.getByText(/Enviar Mensaje Individual/i)).toBeInTheDocument())

    const textarea = screen.getByPlaceholderText(/Escribe tu mensaje aquí/i)
    fireEvent.change(textarea, { target: { value: 'Hola desde test' } })

  const allSendBtns = screen.getAllByRole('button', { name: /Enviar Mensaje/i })
  // There may be an icon-only send button and the form's submit button. Choose
  // the button that contains visible text 'Enviar Mensaje'.
  const sendBtn = allSendBtns.find(b => (b.textContent || '').match(/Enviar Mensaje/i))
  expect(sendBtn).toBeDefined()
  fireEvent.click(sendBtn!)

    await waitFor(() => expect(apiService.sendWhatsAppMessage).toHaveBeenCalled())
  })
})
