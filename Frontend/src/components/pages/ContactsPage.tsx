'use client'

import { useState, useEffect } from 'react'
import { apiService } from '@/lib/api'
import { 
  UsersIcon,
  PlusIcon,
  PaperAirplaneIcon,
  TrashIcon,
  MagnifyingGlassIcon,
  UserGroupIcon,
  ChatBubbleLeftRightIcon,
  ClockIcon,
  SparklesIcon,
  ArrowPathIcon,
  PhotoIcon,
  DocumentIcon,
  XMarkIcon
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'

export function ContactsPage() {
  const [contacts, setContacts] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [showAddForm, setShowAddForm] = useState(false)
  const [showBulkMessage, setShowBulkMessage] = useState(false)
  const [selectedContacts, setSelectedContacts] = useState<string[]>([])
  
  // Estados para composición con IA
  const [showAICompose, setShowAICompose] = useState(false)
  const [aiComposing, setAiComposing] = useState(false)
  const [aiMessage, setAiMessage] = useState({
    contactId: '',
    objective: '',
    context: '',
    generatedMessage: ''
  })

  // Estados para multimedia
  const [showMediaUpload, setShowMediaUpload] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState<any[]>([])
  const [selectedMedia, setSelectedMedia] = useState<any>(null)
  const [uploading, setUploading] = useState(false)
  
  // Formulario para agregar contacto
  const [newContact, setNewContact] = useState({
    name: '',
    phone: '',
    chatId: ''
  })

  // Formulario para mensaje individual
  const [singleMessage, setSingleMessage] = useState({
    contactId: '',
    message: ''
  })

  // Formulario para mensaje masivo
  const [bulkMessage, setBulkMessage] = useState({
    message: '',
    intervalSeconds: 5,
    objective: '',
    useAI: false,
    template: '',
    personalizePerContact: false
  })

  useEffect(() => {
    loadContacts()
    loadMediaFiles()
  }, [])

  const loadMediaFiles = async () => {
    try {
      const response = await apiService.listMedia()
      if (response.status === 'success') {
        setUploadedFiles(response.files || [])
      }
    } catch (error) {
      console.error('Error loading media files:', error)
    }
  }

  const loadContacts = async () => {
    setLoading(true)
    try {
      const contactsData = await apiService.getAllowedContacts()
      setContacts(contactsData || [])
    } catch (error) {
      console.error('Error loading contacts:', error)
      toast.error('Error al cargar contactos')
    } finally {
      setLoading(false)
    }
  }

  const handleAddContact = async () => {
    if (!newContact.name || !newContact.phone) {
      toast.error('Nombre y teléfono son requeridos')
      return
    }

    try {
      const chatId = newContact.chatId || newContact.phone
      await apiService.addAllowedContact({
        chat_id: chatId,
        perfil: newContact.name,
        context: '',
        objective: ''
      })
      toast.success('Contacto agregado exitosamente')
      setNewContact({ name: '', phone: '', chatId: '' })
      setShowAddForm(false)
      loadContacts()
    } catch (error) {
      toast.error('Error al agregar contacto')
    }
  }

  const handleRemoveContact = async (chatId: string) => {
    if (!confirm('¿Estás seguro de que quieres eliminar este contacto?')) {
      return
    }

    try {
      await apiService.removeAllowedContact(chatId)
      toast.success('Contacto eliminado exitosamente')
      loadContacts()
    } catch (error) {
      toast.error('Error al eliminar contacto')
    }
  }

  const handleSendSingleMessage = async () => {
    if (!singleMessage.contactId || !singleMessage.message) {
      toast.error('Selecciona un contacto y escribe un mensaje')
      return
    }

    try {
      const contact = contacts.find(c => c.chat_id === singleMessage.contactId)
      await apiService.sendWhatsAppMessage(contact?.chat_id || singleMessage.contactId, singleMessage.message)
      toast.success('Mensaje enviado exitosamente')
      setSingleMessage({ contactId: '', message: '' })
    } catch (error) {
      toast.error('Error al enviar mensaje')
    }
  }

  const handleComposeWithAI = async () => {
    if (!aiMessage.contactId || !aiMessage.objective) {
      toast.error('Selecciona un contacto y define el objetivo')
      return
    }

    setAiComposing(true)
    try {
      const response = await apiService.composeMessage(
        aiMessage.contactId,
        aiMessage.objective,
        aiMessage.context
      )
      
      if (response.status === 'success') {
        setAiMessage(prev => ({ ...prev, generatedMessage: response.message }))
        toast.success('Mensaje generado exitosamente')
      } else {
        toast.error('Error al generar mensaje: ' + response.message)
      }
    } catch (error) {
      toast.error('Error al componer mensaje con IA')
    } finally {
      setAiComposing(false)
    }
  }

  const handleSendAIMessage = async () => {
    if (!aiMessage.contactId || !aiMessage.generatedMessage) {
      toast.error('No hay mensaje generado para enviar')
      return
    }

    try {
      await apiService.sendWhatsAppMessage(aiMessage.contactId, aiMessage.generatedMessage)
      toast.success('Mensaje enviado exitosamente')
      setAiMessage({ contactId: '', objective: '', context: '', generatedMessage: '' })
      setShowAICompose(false)
    } catch (error) {
      toast.error('Error al enviar mensaje')
    }
  }

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    setUploading(true)
    try {
      const response = await apiService.uploadMedia(file)
      if (response.status === 'success') {
        toast.success('Archivo subido exitosamente')
        loadMediaFiles() // Reload media list
      } else {
        toast.error('Error al subir archivo')
      }
    } catch (error) {
      toast.error('Error al subir archivo')
    } finally {
      setUploading(false)
      // Reset input
      if (event.target) {
        event.target.value = ''
      }
    }
  }

  const handleDeleteMedia = async (mediaType: string, filename: string) => {
    if (!confirm('¿Estás seguro de que quieres eliminar este archivo?')) {
      return
    }

    try {
      await apiService.deleteMedia(mediaType, filename)
      toast.success('Archivo eliminado exitosamente')
      loadMediaFiles()
      if (selectedMedia?.filename === filename) {
        setSelectedMedia(null)
      }
    } catch (error) {
      toast.error('Error al eliminar archivo')
    }
  }

  const handleSendWithMedia = async (contactId: string, message: string) => {
    if (!selectedMedia) {
      toast.error('Selecciona un archivo multimedia')
      return
    }

    try {
      await apiService.sendMediaMessage(
        contactId,
        message,
        selectedMedia.media_type,
        selectedMedia.filename
      )
      toast.success('Mensaje con multimedia enviado exitosamente')
      setSelectedMedia(null)
    } catch (error) {
      toast.error('Error al enviar mensaje con multimedia')
    }
  }

  const handleSendBulkMessage = async () => {
    if (selectedContacts.length === 0) {
      toast.error('Selecciona al menos un contacto')
      return
    }

    if (!bulkMessage.useAI && !bulkMessage.message) {
      toast.error('Escribe un mensaje o activa la personalización con IA')
      return
    }

    if (bulkMessage.useAI && (!bulkMessage.objective || !bulkMessage.template)) {
      toast.error('Define el objetivo y la plantilla para la personalización con IA')
      return
    }

    try {
      toast.success(`Iniciando envío a ${selectedContacts.length} contactos...`)
      let successCount = 0
      let errorCount = 0

      // Enviar mensajes uno por uno con intervalo
      for (const chatId of selectedContacts) {
        try {
          let messageToSend = bulkMessage.message

          // Si usa IA y personalización por contacto, generar mensaje personalizado
          if (bulkMessage.useAI && bulkMessage.personalizePerContact) {
            const contact = contacts.find(c => c.chat_id === chatId)
            const contactContext = contact ? `Contacto: ${contact.contact_name || 'Sin nombre'}` : ''
            
            try {
              const response = await apiService.composeMessage(
                chatId,
                bulkMessage.objective,
                `${bulkMessage.template}\n\nContexto del contacto: ${contactContext}`
              )
              
              if (response.status === 'success') {
                messageToSend = response.message
              } else {
                // Fallback a plantilla si falla la IA
                messageToSend = bulkMessage.template.replace('{nombre}', contact?.contact_name || 'Cliente')
              }
            } catch (error) {
              console.error(`Error generando mensaje personalizado para ${chatId}:`, error)
              // Fallback a plantilla
              messageToSend = bulkMessage.template.replace('{nombre}', contact?.contact_name || 'Cliente')
            }
          } else if (bulkMessage.useAI) {
            // Si usa IA pero no personalización, usar la plantilla base
            messageToSend = bulkMessage.template
          }

          await apiService.sendWhatsAppMessage(chatId, messageToSend)
          successCount++
          
          // Mostrar progreso
          toast.success(`Enviado ${successCount}/${selectedContacts.length}`, { duration: 1000 })
          
          // Esperar intervalo entre mensajes
          if (successCount < selectedContacts.length) {
            await new Promise(resolve => setTimeout(resolve, bulkMessage.intervalSeconds * 1000))
          }
        } catch (error) {
          console.error(`Error enviando mensaje a ${chatId}:`, error)
          errorCount++
        }
      }
      
      // Resumen final
      if (errorCount === 0) {
        toast.success(`✅ Todos los mensajes enviados exitosamente (${successCount}/${selectedContacts.length})`)
      } else {
        toast.error(`⚠️ Enviados: ${successCount}, Errores: ${errorCount}`)
      }
      
      setBulkMessage({ message: '', intervalSeconds: 5, objective: '', useAI: false, template: '', personalizePerContact: false })
      setSelectedContacts([])
      setShowBulkMessage(false)
    } catch (error) {
      toast.error('Error al enviar mensajes masivos')
    }
  }

  const filteredContacts = contacts.filter(contact =>
    contact.contact_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    contact.phone_number?.includes(searchTerm) ||
    contact.chat_id?.includes(searchTerm)
  )

  const toggleContactSelection = (chatId: string) => {
    setSelectedContacts(prev =>
      prev.includes(chatId)
        ? prev.filter(id => id !== chatId)
        : [...prev, chatId]
    )
  }

  const selectAllContacts = () => {
    if (selectedContacts.length === filteredContacts.length) {
      setSelectedContacts([])
    } else {
      setSelectedContacts(filteredContacts.map(c => c.chat_id))
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-2 flex items-center">
          <UsersIcon className="h-7 w-7 mr-3 text-blue-500" />
          Gestión de Contactos
        </h1>
        <p className="text-gray-600">Administra contactos, envía mensajes individuales y campañas masivas</p>
      </div>

      {/* Barra de acciones */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <div className="flex flex-col sm:flex-row gap-4">
          {/* Búsqueda */}
          <div className="flex-1 relative">
            <MagnifyingGlassIcon className="h-5 w-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Buscar contactos..."
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Botones de acción */}
          <div className="flex gap-2">
            <button
              onClick={() => setShowAddForm(!showAddForm)}
              className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-all duration-200 flex items-center"
            >
              <PlusIcon className="h-4 w-4 mr-1" />
              Agregar
            </button>
            
            <button
              onClick={() => setShowAICompose(!showAICompose)}
              className="px-4 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600 transition-all duration-200 flex items-center"
            >
              <SparklesIcon className="h-4 w-4 mr-1" />
              Componer con IA
            </button>

            <button
              onClick={() => setShowMediaUpload(!showMediaUpload)}
              className="px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition-all duration-200 flex items-center"
            >
              <PhotoIcon className="h-4 w-4 mr-1" />
              Multimedia
            </button>
            
            <button
              onClick={() => setShowBulkMessage(!showBulkMessage)}
              className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition-all duration-200 flex items-center"
            >
              <UserGroupIcon className="h-4 w-4 mr-1" />
              Mensaje Masivo
            </button>
          </div>
        </div>
      </div>

      {/* Formulario para agregar contacto */}
      {showAddForm && (
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Agregar Nuevo Contacto</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <input
              type="text"
              value={newContact.name}
              onChange={(e) => setNewContact(prev => ({ ...prev, name: e.target.value }))}
              placeholder="Nombre del contacto"
              className="p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <input
              type="text"
              value={newContact.phone}
              onChange={(e) => setNewContact(prev => ({ ...prev, phone: e.target.value }))}
              placeholder="Número de teléfono"
              className="p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <input
              type="text"
              value={newContact.chatId}
              onChange={(e) => setNewContact(prev => ({ ...prev, chatId: e.target.value }))}
              placeholder="Chat ID (opcional)"
              className="p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <div className="flex gap-2 mt-4">
            <button
              onClick={handleAddContact}
              className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-all duration-200"
            >
              Agregar Contacto
            </button>
            <button
              onClick={() => setShowAddForm(false)}
              className="px-4 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600 transition-all duration-200"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      {/* Formulario para composición con IA */}
      {showAICompose && (
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <SparklesIcon className="h-5 w-5 mr-2 text-purple-500" />
            Componer Mensaje con IA
          </h3>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Seleccionar Contacto
              </label>
              <select
                value={aiMessage.contactId}
                onChange={(e) => setAiMessage(prev => ({ ...prev, contactId: e.target.value }))}
                className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              >
                <option value="">Selecciona un contacto...</option>
                {contacts.map(contact => (
                  <option key={contact.chat_id} value={contact.chat_id}>
                    {contact.contact_name} ({contact.phone_number})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Objetivo del Mensaje
              </label>
              <input
                type="text"
                value={aiMessage.objective}
                onChange={(e) => setAiMessage(prev => ({ ...prev, objective: e.target.value }))}
                placeholder="ej: Agendar una cita médica, Promocionar un producto, Seguimiento de venta..."
                className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Contexto Adicional (opcional)
              </label>
              <textarea
                value={aiMessage.context}
                onChange={(e) => setAiMessage(prev => ({ ...prev, context: e.target.value }))}
                rows={3}
                placeholder="Información adicional que ayude a personalizar el mensaje..."
                className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              />
            </div>

            {/* Mensaje generado */}
            {aiMessage.generatedMessage && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Mensaje Generado
                </label>
                <div className="relative">
                  <textarea
                    value={aiMessage.generatedMessage}
                    onChange={(e) => setAiMessage(prev => ({ ...prev, generatedMessage: e.target.value }))}
                    rows={4}
                    className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent bg-purple-50"
                  />
                  <button
                    onClick={handleComposeWithAI}
                    disabled={aiComposing}
                    className="absolute top-2 right-2 p-1 text-purple-500 hover:bg-purple-100 rounded transition-colors"
                    title="Regenerar mensaje"
                  >
                    <ArrowPathIcon className={`h-4 w-4 ${aiComposing ? 'animate-spin' : ''}`} />
                  </button>
                </div>
              </div>
            )}

            <div className="flex gap-2 pt-4">
              {!aiMessage.generatedMessage ? (
                <button
                  onClick={handleComposeWithAI}
                  disabled={!aiMessage.contactId || !aiMessage.objective || aiComposing}
                  className="px-4 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 flex items-center"
                >
                  {aiComposing ? (
                    <>
                      <ArrowPathIcon className="h-4 w-4 mr-2 animate-spin" />
                      Generando...
                    </>
                  ) : (
                    <>
                      <SparklesIcon className="h-4 w-4 mr-2" />
                      Generar Mensaje
                    </>
                  )}
                </button>
              ) : (
                <button
                  onClick={handleSendAIMessage}
                  className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition-all duration-200 flex items-center"
                >
                  <PaperAirplaneIcon className="h-4 w-4 mr-2" />
                  Enviar Mensaje
                </button>
              )}
              
              <button
                onClick={() => {
                  setShowAICompose(false)
                  setAiMessage({ contactId: '', objective: '', context: '', generatedMessage: '' })
                }}
                className="px-4 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600 transition-all duration-200"
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Formulario para mensaje masivo */}
      {showBulkMessage && (
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Campaña de Mensaje Masivo</h3>
          
          <div className="space-y-6">
            {/* Control de AI */}
            <div className="border border-blue-200 rounded-lg p-4 bg-blue-50">
              <div className="flex items-center mb-3">
                <input
                  type="checkbox"
                  id="useAI"
                  checked={bulkMessage.useAI}
                  onChange={(e) => setBulkMessage(prev => ({ ...prev, useAI: e.target.checked }))}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <label htmlFor="useAI" className="ml-2 text-sm font-medium text-blue-900">
                  🤖 Usar AI para personalizar mensajes
                </label>
              </div>
              
              {bulkMessage.useAI && (
                <div className="space-y-3 mt-3">
                  <div>
                    <label className="block text-sm font-medium text-blue-700 mb-1">
                      Plantilla base (usa variables como {"{nombre}"}, {"{empresa}"}, etc.)
                    </label>
                    <textarea
                      value={bulkMessage.template}
                      onChange={(e) => setBulkMessage(prev => ({ ...prev, template: e.target.value }))}
                      rows={3}
                      placeholder="Hola {nombre}, espero que estés bien. Quería contactarte para..."
                      className="w-full p-2 border border-blue-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-blue-700 mb-1">
                      Objetivo del mensaje
                    </label>
                    <input
                      type="text"
                      value={bulkMessage.objective}
                      onChange={(e) => setBulkMessage(prev => ({ ...prev, objective: e.target.value }))}
                      placeholder="Ej: Promocionar servicio de citas médicas, seguimiento postventa, etc."
                      className="w-full p-2 border border-blue-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                    />
                  </div>
                  
                  <div className="flex items-center">
                    <input
                      type="checkbox"
                      id="personalizePerContact"
                      checked={bulkMessage.personalizePerContact}
                      onChange={(e) => setBulkMessage(prev => ({ ...prev, personalizePerContact: e.target.checked }))}
                      className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                    />
                    <label htmlFor="personalizePerContact" className="ml-2 text-sm text-blue-700">
                      Personalizar cada mensaje individualmente (más lento pero más efectivo)
                    </label>
                  </div>
                </div>
              )}
            </div>

            {/* Mensaje manual (solo si AI está desactivado) */}
            {!bulkMessage.useAI && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Mensaje
                </label>
                <textarea
                  value={bulkMessage.message}
                  onChange={(e) => setBulkMessage(prev => ({ ...prev, message: e.target.value }))}
                  rows={4}
                  placeholder="Escribe tu mensaje aquí..."
                  className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Intervalo entre mensajes (segundos)
                </label>
                <input
                  type="number"
                  value={bulkMessage.intervalSeconds}
                  onChange={(e) => setBulkMessage(prev => ({ ...prev, intervalSeconds: parseInt(e.target.value) }))}
                  min="1"
                  max="60"
                  className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Contactos seleccionados: {selectedContacts.length}
                </label>
                <div className="p-3 bg-gray-50 rounded-lg text-sm text-gray-600">
                  {selectedContacts.length === 0 
                    ? 'Selecciona contactos de la lista'
                    : `${selectedContacts.length} contacto(s) seleccionado(s)`
                  }
                </div>
              </div>
            </div>

            <div className="flex gap-2">
              <button
                onClick={handleSendBulkMessage}
                disabled={
                  selectedContacts.length === 0 || 
                  (bulkMessage.useAI ? !bulkMessage.template || !bulkMessage.objective : !bulkMessage.message)
                }
                className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 flex items-center"
              >
                <PaperAirplaneIcon className="h-4 w-4 mr-1" />
                {bulkMessage.useAI ? '🤖 Enviar con AI' : 'Enviar Campaña'}
              </button>
              <button
                onClick={() => setShowBulkMessage(false)}
                className="px-4 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600 transition-all duration-200"
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Lista de contactos */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">
            Lista de Contactos ({filteredContacts.length})
          </h3>
          
          {filteredContacts.length > 0 && (
            <button
              onClick={selectAllContacts}
              className="text-sm text-blue-500 hover:text-blue-600"
            >
              {selectedContacts.length === filteredContacts.length ? 'Deseleccionar todos' : 'Seleccionar todos'}
            </button>
          )}
        </div>

        {loading ? (
          <div className="text-center py-8">
            <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-gray-600">Cargando contactos...</p>
          </div>
        ) : filteredContacts.length === 0 ? (
          <div className="text-center py-8">
            <UsersIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600">No hay contactos disponibles</p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredContacts.map((contact) => (
              <div
                key={contact.chat_id}
                className={`p-4 border rounded-lg transition-all duration-200 ${
                  selectedContacts.includes(contact.chat_id)
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <input
                      type="checkbox"
                      checked={selectedContacts.includes(contact.chat_id)}
                      onChange={() => toggleContactSelection(contact.chat_id)}
                      className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                    />
                    
                    <div>
                      <div className="font-medium text-gray-900">{contact.contact_name}</div>
                      <div className="text-sm text-gray-500">{contact.phone_number}</div>
                      <div className="text-xs text-gray-400">ID: {contact.chat_id}</div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => {
                        setAiMessage(prev => ({ ...prev, contactId: contact.chat_id }))
                        setShowAICompose(true)
                      }}
                      className="p-2 text-purple-500 hover:bg-purple-100 rounded-lg transition-all duration-200"
                      title="Componer con IA"
                    >
                      <SparklesIcon className="h-4 w-4" />
                    </button>
                    
                    <button
                      onClick={() => setSingleMessage(prev => ({ ...prev, contactId: contact.chat_id }))}
                      className="p-2 text-blue-500 hover:bg-blue-100 rounded-lg transition-all duration-200"
                      title="Enviar mensaje"
                    >
                      <ChatBubbleLeftRightIcon className="h-4 w-4" />
                    </button>
                    
                    <button
                      onClick={() => handleRemoveContact(contact.chat_id)}
                      className="p-2 text-red-500 hover:bg-red-100 rounded-lg transition-all duration-200"
                      title="Eliminar contacto"
                    >
                      <TrashIcon className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Formulario de mensaje individual */}
      {singleMessage.contactId && (
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Enviar Mensaje Individual
          </h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Contacto seleccionado
              </label>
              <div className="p-3 bg-gray-50 rounded-lg">
                {contacts.find(c => c.chat_id === singleMessage.contactId)?.contact_name || 'Contacto no encontrado'}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Mensaje
              </label>
              <textarea
                value={singleMessage.message}
                onChange={(e) => setSingleMessage(prev => ({ ...prev, message: e.target.value }))}
                rows={4}
                placeholder="Escribe tu mensaje aquí..."
                className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div className="flex gap-2">
              <button
                onClick={handleSendSingleMessage}
                disabled={!singleMessage.message}
                className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 flex items-center"
              >
                <PaperAirplaneIcon className="h-4 w-4 mr-1" />
                Enviar Mensaje
              </button>
              <button
                onClick={() => setSingleMessage({ contactId: '', message: '' })}
                className="px-4 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600 transition-all duration-200"
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}