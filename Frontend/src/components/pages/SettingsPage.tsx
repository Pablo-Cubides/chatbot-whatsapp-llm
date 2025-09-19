'use client'

import { useState, useEffect } from 'react'
import { apiService } from '@/lib/api'
import { 
  CogIcon,
  AdjustmentsHorizontalIcon,
  ChatBubbleLeftRightIcon,
  ClockIcon,
  FireIcon,
  HashtagIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ArrowPathIcon
} from '@heroicons/react/24/outline'

interface Settings {
  temperature: number
  max_tokens: number
  reason_after_messages: number
  respond_to_all: boolean
}

export function SettingsPage() {
  const [settings, setSettings] = useState<Settings>({
    temperature: 0.7,
    max_tokens: 512,
    reason_after_messages: 10,
    respond_to_all: false
  })
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [validation, setValidation] = useState<{valid: boolean, message: string}>({valid: true, message: ''})
  const [lastSaved, setLastSaved] = useState<Date | null>(null)

  useEffect(() => {
    loadSettings()
  }, [])

  const loadSettings = async () => {
    setLoading(true)
    try {
      const response = await apiService.getSettings()
      if (response.settings) {
        setSettings(response.settings)
        setValidation(response.validation || {valid: true, message: ''})
      }
    } catch (error) {
      console.error('Error loading settings:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const response = await apiService.saveSettings(settings)
      if (response.status === 'success') {
        setLastSaved(new Date())
        setValidation(response.validation || {valid: true, message: 'Configuración guardada correctamente'})
        alert('Configuración guardada exitosamente')
      } else {
        alert('Error al guardar: ' + response.message)
      }
    } catch (error: any) {
      alert('Error al guardar: ' + error.message)
    } finally {
      setSaving(false)
    }
  }

  const updateSetting = (key: keyof Settings, value: any) => {
    setSettings(prev => ({
      ...prev,
      [key]: value
    }))
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center">
              <CogIcon className="h-8 w-8 text-blue-600 mr-3" />
              Configuración Global
            </h1>
            <p className="text-gray-600 mt-2">
              Configura el comportamiento general del sistema de chatbot
            </p>
          </div>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 flex items-center"
          >
            {saving ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                Guardando...
              </>
            ) : (
              <>
                <CheckCircleIcon className="h-4 w-4 mr-2" />
                Guardar Configuración
              </>
            )}
          </button>
        </div>
      </div>

      {/* Validation Status */}
      {!validation.valid && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center">
            <ExclamationTriangleIcon className="h-5 w-5 text-red-600 mr-2" />
            <div className="text-sm text-red-800">
              <p className="font-medium">Error de validación:</p>
              <p className="mt-1">{validation.message}</p>
            </div>
          </div>
        </div>
      )}

      {/* Last Saved Info */}
      {lastSaved && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex items-center">
            <CheckCircleIcon className="h-5 w-5 text-green-600 mr-2" />
            <div className="text-sm text-green-800">
              <p className="font-medium">Configuración guardada exitosamente</p>
              <p className="mt-1">Último guardado: {lastSaved.toLocaleString()}</p>
            </div>
          </div>
        </div>
      )}

      {/* Global Response Control */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
          <ChatBubbleLeftRightIcon className="h-6 w-6 text-purple-500 mr-2" />
          Control de Respuestas
        </h2>

        <div className="space-y-4">
          <div className={`p-4 rounded-lg border-2 transition-all ${
            settings.respond_to_all 
              ? 'border-green-300 bg-green-50' 
              : 'border-gray-200 bg-gray-50'
          }`}>
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <div className="flex items-center">
                  <h3 className="text-lg font-medium text-gray-900">
                    Responder a Todos los Mensajes
                  </h3>
                  <div className={`ml-3 px-2 py-1 rounded-full text-xs font-medium ${
                    settings.respond_to_all
                      ? 'bg-green-100 text-green-800'
                      : 'bg-gray-100 text-gray-600'
                  }`}>
                    {settings.respond_to_all ? 'ACTIVADO' : 'DESACTIVADO'}
                  </div>
                </div>
                <p className="text-sm text-gray-600 mt-1">
                  {settings.respond_to_all 
                    ? 'El bot responderá automáticamente a TODOS los mensajes recibidos en WhatsApp'
                    : 'El bot solo responderá a contactos específicos configurados en la lista de permitidos'
                  }
                </p>
              </div>
              
              <label className="relative inline-flex items-center cursor-pointer ml-4">
                <input
                  type="checkbox"
                  checked={settings.respond_to_all}
                  onChange={(e) => updateSetting('respond_to_all', e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-14 h-7 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-6 after:w-6 after:transition-all peer-checked:bg-green-600"></div>
              </label>
            </div>

            {settings.respond_to_all && (
              <div className="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                <div className="flex items-center">
                  <ExclamationTriangleIcon className="h-5 w-5 text-yellow-600 mr-2" />
                  <div className="text-sm text-yellow-800">
                    <p className="font-medium">⚠️ Advertencia importante</p>
                    <p className="mt-1">
                      Con esta opción activada, el bot responderá a CUALQUIER mensaje recibido. 
                      Asegúrate de que esto es lo que deseas antes de activarlo.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* AI Model Parameters */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
          <AdjustmentsHorizontalIcon className="h-6 w-6 text-blue-500 mr-2" />
          Parámetros del Modelo IA
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Temperature */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <FireIcon className="h-4 w-4 inline mr-1" />
              Creatividad (Temperature)
            </label>
            <input
              type="range"
              min="0"
              max="2"
              step="0.1"
              value={settings.temperature}
              onChange={(e) => updateSetting('temperature', parseFloat(e.target.value))}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer slider"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>Conservador (0.0)</span>
              <span className="font-medium text-blue-600">{settings.temperature}</span>
              <span>Creativo (2.0)</span>
            </div>
            <p className="text-xs text-gray-600 mt-2">
              Controla qué tan creativas o conservadoras son las respuestas del bot
            </p>
          </div>

          {/* Max Tokens */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <HashtagIcon className="h-4 w-4 inline mr-1" />
              Longitud Máxima (Tokens)
            </label>
            <input
              type="number"
              min="50"
              max="4000"
              step="50"
              value={settings.max_tokens}
              onChange={(e) => updateSetting('max_tokens', parseInt(e.target.value))}
              className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <p className="text-xs text-gray-600 mt-2">
              Máximo número de tokens (palabras aproximadas) en las respuestas
            </p>
          </div>

          {/* Reason After Messages */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <ClockIcon className="h-4 w-4 inline mr-1" />
              Reasoning cada N mensajes
            </label>
            <input
              type="number"
              min="1"
              max="100"
              value={settings.reason_after_messages}
              onChange={(e) => updateSetting('reason_after_messages', parseInt(e.target.value))}
              className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <p className="text-xs text-gray-600 mt-2">
              Frecuencia con la que el modelo de reasoning analiza la conversación
            </p>
          </div>
        </div>
      </div>

      {/* Information Panel */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-center">
          <InformationCircleIcon className="h-5 w-5 text-blue-600 mr-2" />
          <div className="text-sm text-blue-800">
            <p className="font-medium">Información sobre la configuración:</p>
            <ul className="mt-1 list-disc list-inside space-y-1">
              <li><strong>Temperature:</strong> 0.0 = respuestas muy consistentes, 2.0 = respuestas muy creativas</li>
              <li><strong>Max Tokens:</strong> Controla la longitud de las respuestas (1 token ≈ 0.75 palabras)</li>
              <li><strong>Reasoning:</strong> Análisis profundo para mejorar la calidad de las conversaciones</li>
              <li><strong>Respond to All:</strong> Control global de a quién responde el bot automáticamente</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <div className="flex items-center justify-between">
          <button
            onClick={loadSettings}
            disabled={loading}
            className="px-4 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 flex items-center"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                Cargando...
              </>
            ) : (
              <>
                <ArrowPathIcon className="h-4 w-4 mr-2" />
                Recargar Configuración
              </>
            )}
          </button>

          <div className="text-sm text-gray-500">
            {validation.valid ? (
              <span className="text-green-600">✓ Configuración válida</span>
            ) : (
              <span className="text-red-600">✗ Configuración inválida</span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}