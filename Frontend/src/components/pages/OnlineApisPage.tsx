'use client'

import { useState, useEffect } from 'react'
import { apiService } from '@/lib/api'
import { 
  CpuChipIcon,
  KeyIcon,
  CheckCircleIcon,
  XCircleIcon,
  PlayIcon,
  WifiIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon
} from '@heroicons/react/24/outline'

interface ApiProvider {
  api_key: string
  base_url: string
  enabled: boolean
  models: string[]
  api_key_masked?: string
  has_api_key?: boolean
}

interface ApiConfig {
  [key: string]: ApiProvider
}

export function OnlineApisPage() {
  const [config, setConfig] = useState<ApiConfig>({})
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testResults, setTestResults] = useState<{[key: string]: any}>({})
  const [testing, setTesting] = useState<{[key: string]: boolean}>({})

  useEffect(() => {
    loadConfig()
  }, [])

  const loadConfig = async () => {
    setLoading(true)
    try {
      const response = await apiService.getOnlineApisConfig()
      if (response.status === 'success') {
        setConfig(response.config || {})
      }
    } catch (error) {
      console.error('Error loading online APIs config:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const response = await apiService.saveOnlineApisConfig(config)
      if (response.status === 'success') {
        alert('Configuración guardada exitosamente')
        loadConfig() // Reload to get updated data
      } else {
        alert('Error al guardar: ' + response.message)
      }
    } catch (error: any) {
      alert('Error al guardar: ' + error.message)
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async (provider: string) => {
    setTesting(prev => ({ ...prev, [provider]: true }))
    try {
      const response = await apiService.testOnlineApi(provider)
      setTestResults(prev => ({ ...prev, [provider]: response }))
    } catch (error: any) {
      setTestResults(prev => ({ 
        ...prev, 
        [provider]: { 
          status: 'error', 
          message: error.message || 'Error de conexión' 
        } 
      }))
    } finally {
      setTesting(prev => ({ ...prev, [provider]: false }))
    }
  }

  const updateConfig = (provider: string, field: string, value: any) => {
    setConfig(prev => ({
      ...prev,
      [provider]: {
        ...prev[provider],
        [field]: value
      }
    }))
  }

  const getProviderIcon = (provider: string) => {
    switch (provider) {
      case 'openai':
        return '🤖'
      case 'anthropic':
        return '🧠'
      case 'google':
        return '💎'
      default:
        return '🔌'
    }
  }

  const getProviderName = (provider: string) => {
    switch (provider) {
      case 'openai':
        return 'OpenAI (ChatGPT)'
      case 'anthropic':
        return 'Anthropic (Claude)'
      case 'google':
        return 'Google (Gemini)'
      default:
        return provider.charAt(0).toUpperCase() + provider.slice(1)
    }
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
              <WifiIcon className="h-8 w-8 text-blue-600 mr-3" />
              APIs Online
            </h1>
            <p className="text-gray-600 mt-2">
              Configura y gestiona las conexiones a servicios de IA externos
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

      {/* Information Banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-center">
          <InformationCircleIcon className="h-5 w-5 text-blue-600 mr-2" />
          <div className="text-sm text-blue-800">
            <p className="font-medium">Información importante:</p>
            <ul className="mt-1 list-disc list-inside space-y-1">
              <li>Las claves API se almacenan de forma segura localmente</li>
              <li>Solo se muestran los últimos 4 caracteres por seguridad</li>
              <li>Puedes habilitar múltiples proveedores simultáneamente</li>
              <li>Usa el botón "Probar" para verificar la conectividad</li>
            </ul>
          </div>
        </div>
      </div>

      {/* API Providers */}
      <div className="grid grid-cols-1 gap-6">
        {Object.entries(config).map(([provider, settings]) => (
          <div key={provider} className="bg-white rounded-lg shadow-lg p-6 border-l-4 border-gray-300">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center">
                <span className="text-2xl mr-3">{getProviderIcon(provider)}</span>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">
                    {getProviderName(provider)}
                  </h3>
                  <p className="text-sm text-gray-500">
                    {settings.models?.length || 0} modelos disponibles
                  </p>
                </div>
              </div>
              
              <div className="flex items-center space-x-2">
                {testResults[provider] && (
                  <div className={`flex items-center text-sm px-2 py-1 rounded ${
                    testResults[provider].status === 'success'
                      ? 'bg-green-100 text-green-700'
                      : 'bg-red-100 text-red-700'
                  }`}>
                    {testResults[provider].status === 'success' ? (
                      <CheckCircleIcon className="h-4 w-4 mr-1" />
                    ) : (
                      <XCircleIcon className="h-4 w-4 mr-1" />
                    )}
                    {testResults[provider].message}
                  </div>
                )}
                
                <button
                  onClick={() => handleTest(provider)}
                  disabled={testing[provider] || !settings.has_api_key}
                  className="px-3 py-1 bg-purple-500 text-white rounded hover:bg-purple-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 flex items-center text-sm"
                >
                  {testing[provider] ? (
                    <>
                      <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-white mr-1"></div>
                      Probando...
                    </>
                  ) : (
                    <>
                      <PlayIcon className="h-3 w-3 mr-1" />
                      Probar
                    </>
                  )}
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="space-y-4">
                {/* Enable Toggle */}
                <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <span className="text-sm font-medium text-gray-700">Habilitado</span>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={settings.enabled}
                      onChange={(e) => updateConfig(provider, 'enabled', e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                  </label>
                </div>

                {/* API Key */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <KeyIcon className="h-4 w-4 inline mr-1" />
                    Clave API
                  </label>
                  <input
                    type="password"
                    value={settings.api_key_masked || ''}
                    onChange={(e) => updateConfig(provider, 'api_key', e.target.value)}
                    placeholder="Ingresa tu clave API"
                    className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  {settings.has_api_key && (
                    <p className="text-xs text-green-600 mt-1">
                      ✓ Clave API configurada
                    </p>
                  )}
                </div>

                {/* Base URL */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    URL Base
                  </label>
                  <input
                    type="text"
                    value={settings.base_url}
                    onChange={(e) => updateConfig(provider, 'base_url', e.target.value)}
                    className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
              </div>

              <div>
                {/* Available Models */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <CpuChipIcon className="h-4 w-4 inline mr-1" />
                    Modelos Disponibles
                  </label>
                  <div className="space-y-2 max-h-32 overflow-y-auto p-3 bg-gray-50 rounded-lg">
                    {settings.models && settings.models.length > 0 ? (
                      settings.models.map((model, index) => (
                        <div key={index} className="flex items-center text-sm">
                          <div className="w-2 h-2 bg-blue-500 rounded-full mr-2"></div>
                          <span>{model}</span>
                        </div>
                      ))
                    ) : (
                      <div className="text-sm text-gray-500 text-center py-2">
                        No hay modelos configurados
                      </div>
                    )}
                  </div>
                </div>

                {/* Status Indicator */}
                <div className="mt-4">
                  <div className={`p-3 rounded-lg border ${
                    settings.enabled && settings.has_api_key
                      ? 'border-green-200 bg-green-50'
                      : 'border-yellow-200 bg-yellow-50'
                  }`}>
                    <div className="flex items-center">
                      {settings.enabled && settings.has_api_key ? (
                        <>
                          <CheckCircleIcon className="h-5 w-5 text-green-500 mr-2" />
                          <span className="text-sm text-green-700 font-medium">
                            Configurado y listo
                          </span>
                        </>
                      ) : (
                        <>
                          <ExclamationTriangleIcon className="h-5 w-5 text-yellow-500 mr-2" />
                          <span className="text-sm text-yellow-700 font-medium">
                            {!settings.enabled 
                              ? 'Deshabilitado' 
                              : 'Falta clave API'
                            }
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {Object.keys(config).length === 0 && (
        <div className="bg-white rounded-lg shadow-lg p-12 text-center">
          <WifiIcon className="h-16 w-16 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            No hay configuración de APIs
          </h3>
          <p className="text-gray-500">
            La configuración de APIs online se cargará automáticamente cuando esté disponible.
          </p>
        </div>
      )}
    </div>
  )
}