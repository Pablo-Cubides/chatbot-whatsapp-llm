'use client'

import { useState, useEffect } from 'react'
import { apiService } from '@/lib/api'
import { 
  CogIcon,
  KeyIcon,
  CloudIcon,
  AdjustmentsHorizontalIcon,
  DocumentTextIcon,
  BookmarkIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  XCircleIcon,
  PlayIcon,
  WifiIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  CpuChipIcon
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'

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

export function ConfigPage() {
  const [settings, setSettings] = useState<any>({})
  const [prompts, setPrompts] = useState<any>({})
  const [docsContent, setDocsContent] = useState({
    perfil: '',
    ejemplo_chat: '',
    ultimo_contexto: ''
  })
  const [apiKeys, setApiKeys] = useState({
    openai: '',
    claude: '',
    gemini: ''
  })
  const [modelConfig, setModelConfig] = useState({
    temperature: 0.7,
    max_tokens: 1000,
    top_p: 1.0
  })
  const [docsLoading, setDocsLoading] = useState(true)
  const [loading, setLoading] = useState(false)
  const [saveLoading, setSaveLoading] = useState(false)

  // Estados para configuración de APIs online
  const [onlineApisConfig, setOnlineApisConfig] = useState<ApiConfig>({})
  const [onlineApisLoading, setOnlineApisLoading] = useState(false)
  const [onlineApisSaving, setOnlineApisSaving] = useState(false)
  const [testResults, setTestResults] = useState<{[key: string]: any}>({})
  const [testing, setTesting] = useState<{[key: string]: boolean}>({})

  useEffect(() => {
    loadConfiguration()
    loadDocsContent()
    loadOnlineApisConfig()
  }, [])

  const loadDocsContent = async () => {
    setDocsLoading(true)
    try {
      // Cargar contenido de los archivos de documentación
      const docsData = await apiService.getDocsContent()
      if (docsData) {
        setDocsContent(docsData)
      }
    } catch (error) {
      console.error('Error loading docs content:', error)
      // Si no se pueden cargar los docs, usar valores por defecto vacíos
      setDocsContent({
        perfil: '',
        ejemplo_chat: '',
        ultimo_contexto: ''
      })
    } finally {
      setDocsLoading(false)
    }
  }

  const loadConfiguration = async () => {
    setLoading(true)
    try {
      const [settingsData, promptsData] = await Promise.all([
        apiService.getSettings(),
        apiService.getPrompts()
      ])
      
      setSettings(settingsData || {})
      setPrompts(promptsData || {})
      
      // Cargar configuración de modelo desde settings
      if (settingsData) {
        setModelConfig({
          temperature: settingsData.temperature || 0.7,
          max_tokens: settingsData.max_tokens || 1000,
          top_p: settingsData.top_p || 1.0
        })
        
        // Cargar API keys desde settings
        if (settingsData.api_keys) {
          setApiKeys({
            openai: settingsData.api_keys.openai || '',
            claude: settingsData.api_keys.claude || '',
            gemini: settingsData.api_keys.gemini || ''
          })
        }
      }
    } catch (error) {
      console.error('Error loading configuration:', error)
      toast.error('Error al cargar configuración')
    } finally {
      setLoading(false)
    }
  }

  const loadOnlineApisConfig = async () => {
    setOnlineApisLoading(true)
    try {
      const response = await apiService.getOnlineApisConfig()
      if (response.status === 'success') {
        setOnlineApisConfig(response.config || {})
      }
    } catch (error) {
      console.error('Error loading online APIs config:', error)
    } finally {
      setOnlineApisLoading(false)
    }
  }

  const handleSaveOnlineApisConfig = async () => {
    setOnlineApisSaving(true)
    try {
      const response = await apiService.saveOnlineApisConfig(onlineApisConfig)
      if (response.status === 'success') {
        toast.success('Configuración de APIs guardada exitosamente')
        loadOnlineApisConfig() // Reload to get updated data
      } else {
        toast.error('Error al guardar: ' + response.message)
      }
    } catch (error: any) {
      toast.error('Error al guardar: ' + error.message)
    } finally {
      setOnlineApisSaving(false)
    }
  }

  const handleTestOnlineApi = async (provider: string) => {
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

  const updateOnlineApisConfig = (provider: string, field: string, value: any) => {
    setOnlineApisConfig(prev => ({
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

  const handleSaveSettings = async () => {
    setSaveLoading(true)
    try {
      await apiService.saveSettings({
        ...settings,
        ...modelConfig,
        api_keys: apiKeys
      })
      toast.success('Configuración guardada exitosamente')
    } catch (error) {
      toast.error('Error al guardar configuración')
    } finally {
      setSaveLoading(false)
    }
  }

  const handleSavePrompts = async () => {
    setSaveLoading(true)
    try {
      await apiService.savePrompts(prompts)
      toast.success('Prompts guardados exitosamente')
    } catch (error) {
      toast.error('Error al guardar prompts')
    } finally {
      setSaveLoading(false)
    }
  }

  const handleResetToDefaults = () => {
    setModelConfig({
      temperature: 0.7,
      max_tokens: 1000,
      top_p: 1.0
    })
    setApiKeys({
      openai: '',
      claude: '',
      gemini: ''
    })
    toast.success('Configuración restablecida a valores por defecto')
  }

  const handleSaveDocs = async (fileName: string, content: string) => {
    try {
      await apiService.saveFile(fileName, content)
      toast.success(`Archivo ${fileName} guardado exitosamente`)
      // Reload docs content to reflect changes
      loadDocsContent()
    } catch (error) {
      toast.error(`Error al guardar ${fileName}`)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="w-8 h-8 mx-auto mb-4 border-4 border-blue-500 rounded-full border-t-transparent animate-spin"></div>
          <p className="text-gray-600">Cargando configuración...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="p-6 bg-white rounded-lg shadow-lg">
        <h1 className="flex items-center mb-2 text-2xl font-bold text-gray-900">
          <CogIcon className="mr-3 text-blue-500 h-7 w-7" />
          Configuración del Sistema
        </h1>
        <p className="text-gray-600">Configura API keys, parámetros de modelos y prompts del sistema</p>
      </div>

      {/* Online APIs Configuration */}
      <div className="p-6 bg-white rounded-lg shadow-lg">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="flex items-center text-xl font-semibold text-gray-900">
              <WifiIcon className="w-6 h-6 mr-2 text-blue-500" />
              APIs Online
            </h2>
            <p className="mt-1 text-gray-600">
              Configura y gestiona las conexiones a servicios de IA externos
            </p>
          </div>
          <button
            onClick={handleSaveOnlineApisConfig}
            disabled={onlineApisSaving}
            className="flex items-center px-6 py-2 text-white transition-all duration-200 bg-blue-500 rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {onlineApisSaving ? (
              <>
                <div className="w-4 h-4 mr-2 border-b-2 border-white rounded-full animate-spin"></div>
                Guardando...
              </>
            ) : (
              <>
                <CheckCircleIcon className="w-4 h-4 mr-2" />
                Guardar Configuración
              </>
            )}
          </button>
        </div>

        {/* Information Banner */}
        <div className="p-4 mb-6 border border-blue-200 rounded-lg bg-blue-50">
          <div className="flex items-center">
            <InformationCircleIcon className="w-5 h-5 mr-2 text-blue-600" />
            <div className="text-sm text-blue-800">
              <p className="font-medium">Información importante:</p>
              <ul className="mt-1 space-y-1 list-disc list-inside">
                <li>Las claves API se almacenan de forma segura localmente</li>
                <li>Solo se muestran los últimos 4 caracteres por seguridad</li>
                <li>Puedes habilitar múltiples proveedores simultáneamente</li>
                <li>Usa el botón "Probar" para verificar la conectividad</li>
              </ul>
            </div>
          </div>
        </div>

        {onlineApisLoading ? (
          <div className="flex items-center justify-center h-32">
            <div className="w-8 h-8 border-b-2 border-blue-500 rounded-full animate-spin"></div>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6">
            {Object.entries(onlineApisConfig).map(([provider, settings]) => (
              <div key={provider} className="p-6 bg-white border-l-4 border-blue-300 rounded-lg shadow-sm">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center">
                    <span className="mr-3 text-2xl">{getProviderIcon(provider)}</span>
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
                          <CheckCircleIcon className="w-4 h-4 mr-1" />
                        ) : (
                          <XCircleIcon className="w-4 h-4 mr-1" />
                        )}
                        {testResults[provider].message}
                      </div>
                    )}
                    
                    <button
                      onClick={() => handleTestOnlineApi(provider)}
                      disabled={testing[provider] || !settings.has_api_key}
                      className="flex items-center px-3 py-1 text-sm text-white transition-all duration-200 bg-purple-500 rounded hover:bg-purple-600 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {testing[provider] ? (
                        <>
                          <div className="w-3 h-3 mr-1 border-b-2 border-white rounded-full animate-spin"></div>
                          Probando...
                        </>
                      ) : (
                        <>
                          <PlayIcon className="w-3 h-3 mr-1" />
                          Probar
                        </>
                      )}
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <div className="space-y-4">
                    {/* Enable Toggle */}
                    <div className="flex items-center justify-between p-3 rounded-lg bg-gray-50">
                      <span className="text-sm font-medium text-gray-700">Habilitado</span>
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={settings.enabled}
                          onChange={(e) => updateOnlineApisConfig(provider, 'enabled', e.target.checked)}
                          className="sr-only peer"
                        />
                        <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                      </label>
                    </div>

                    {/* API Key */}
                    <div>
                      <label className="block mb-2 text-sm font-medium text-gray-700">
                        <KeyIcon className="inline w-4 h-4 mr-1" />
                        Clave API
                      </label>
                      <input
                        type="password"
                        value={settings.api_key_masked || ''}
                        onChange={(e) => updateOnlineApisConfig(provider, 'api_key', e.target.value)}
                        placeholder="Ingresa tu clave API"
                        className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      />
                      {settings.has_api_key && (
                        <p className="mt-1 text-xs text-green-600">
                          ✓ Clave API configurada
                        </p>
                      )}
                    </div>

                    {/* Base URL */}
                    <div>
                      <label className="block mb-2 text-sm font-medium text-gray-700">
                        URL Base
                      </label>
                      <input
                        type="text"
                        value={settings.base_url}
                        onChange={(e) => updateOnlineApisConfig(provider, 'base_url', e.target.value)}
                        className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      />
                    </div>
                  </div>

                  <div>
                    {/* Available Models */}
                    <div>
                      <label className="block mb-2 text-sm font-medium text-gray-700">
                        <CpuChipIcon className="inline w-4 h-4 mr-1" />
                        Modelos Disponibles
                      </label>
                      <div className="p-3 space-y-2 overflow-y-auto rounded-lg max-h-32 bg-gray-50">
                        {settings.models && settings.models.length > 0 ? (
                          settings.models.map((model, index) => (
                            <div key={index} className="flex items-center text-sm">
                              <div className="w-2 h-2 mr-2 bg-blue-500 rounded-full"></div>
                              <span>{model}</span>
                            </div>
                          ))
                        ) : (
                          <div className="py-2 text-sm text-center text-gray-500">
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
                              <CheckCircleIcon className="w-5 h-5 mr-2 text-green-500" />
                              <span className="text-sm font-medium text-green-700">
                                Configurado y listo
                              </span>
                            </>
                          ) : (
                            <>
                              <ExclamationTriangleIcon className="w-5 h-5 mr-2 text-yellow-500" />
                              <span className="text-sm font-medium text-yellow-700">
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
        )}

        {Object.keys(onlineApisConfig).length === 0 && !onlineApisLoading && (
          <div className="p-12 text-center bg-white border-2 border-gray-300 border-dashed rounded-lg">
            <WifiIcon className="w-16 h-16 mx-auto mb-4 text-gray-400" />
            <h3 className="mb-2 text-lg font-medium text-gray-900">
              No hay configuración de APIs
            </h3>
            <p className="text-gray-500">
              La configuración de APIs online se cargará automáticamente cuando esté disponible.
            </p>
          </div>
        )}
      </div>

      {/* Model Configuration */}
      <div className="p-6 bg-white rounded-lg shadow-lg">
        <h2 className="flex items-center mb-4 text-xl font-semibold text-gray-900">
          <AdjustmentsHorizontalIcon className="w-6 h-6 mr-2 text-purple-500" />
          Configuración de Modelos
        </h2>
        
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          <div>
            <label className="block mb-2 text-sm font-medium text-gray-700">
              Temperatura: <span className="font-bold text-blue-600">{modelConfig.temperature}</span>
              <span className="ml-1 text-xs text-gray-500">(0.0 - 2.0)</span>
            </label>
            <input
              type="range"
              min="0"
              max="2"
              step="0.1"
              value={modelConfig.temperature}
              onChange={(e) => setModelConfig((prev: any) => ({ ...prev, temperature: parseFloat(e.target.value) }))}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer slider"
              style={{
                background: `linear-gradient(to right, #3B82F6 0%, #3B82F6 ${(modelConfig.temperature / 2) * 100}%, #D1D5DB ${(modelConfig.temperature / 2) * 100}%, #D1D5DB 100%)`
              }}
            />
            <div className="flex justify-between mt-1 text-xs text-gray-500">
              <span>Preciso</span>
              <span>Creativo</span>
            </div>
          </div>

          <div>
            <label className="block mb-2 text-sm font-medium text-gray-700">
              Max Tokens: <span className="font-bold text-green-600">{modelConfig.max_tokens}</span>
              <span className="ml-1 text-xs text-gray-500">(50 - 4000)</span>
            </label>
            <input
              type="range"
              min="50"
              max="4000"
              step="50"
              value={modelConfig.max_tokens}
              onChange={(e) => setModelConfig((prev: any) => ({ ...prev, max_tokens: parseInt(e.target.value) }))}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer slider"
              style={{
                background: `linear-gradient(to right, #10B981 0%, #10B981 ${((modelConfig.max_tokens - 50) / 3950) * 100}%, #D1D5DB ${((modelConfig.max_tokens - 50) / 3950) * 100}%, #D1D5DB 100%)`
              }}
            />
            <div className="flex justify-between mt-1 text-xs text-gray-500">
              <span>50</span>
              <span>4000</span>
            </div>
          </div>

          <div>
            <label className="block mb-2 text-sm font-medium text-gray-700">
              Top P: <span className="font-bold text-purple-600">{modelConfig.top_p}</span>
              <span className="ml-1 text-xs text-gray-500">(0.0 - 1.0)</span>
            </label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={modelConfig.top_p}
              onChange={(e) => setModelConfig((prev: any) => ({ ...prev, top_p: parseFloat(e.target.value) }))}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer slider"
              style={{
                background: `linear-gradient(to right, #8B5CF6 0%, #8B5CF6 ${modelConfig.top_p * 100}%, #D1D5DB ${modelConfig.top_p * 100}%, #D1D5DB 100%)`
              }}
            />
            <div className="flex justify-between mt-1 text-xs text-gray-500">
              <span>Determinístico</span>
              <span>Diverso</span>
            </div>
          </div>
        </div>

        {/* Configuración adicional */}
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div>
            <label className="block mb-2 text-sm font-medium text-gray-700">
              Reasoning cada X mensajes
              <span className="ml-1 text-xs text-gray-500">(1 - 50)</span>
            </label>
            <input
              type="number"
              min="1"
              max="50"
              value={settings.reason_after_messages || 10}
              onChange={(e) => setSettings((prev: any) => ({ ...prev, reason_after_messages: parseInt(e.target.value) }))}
              className="w-full p-3 text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          <div className="flex items-center">
            <input
              type="checkbox"
              id="respond-to-all"
              checked={settings.respond_to_all || false}
              onChange={(e) => setSettings((prev: any) => ({ ...prev, respond_to_all: e.target.checked }))}
              className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
            />
            <label htmlFor="respond-to-all" className="block ml-2 text-sm text-gray-900">
              <span className="font-medium">Responder a TODOS los mensajes</span>
              <span className="block text-xs text-gray-500">No solo a contactos de la lista</span>
            </label>
          </div>
        </div>
      </div>

      {/* Prompts Configuration */}
      <div className="p-6 bg-white rounded-lg shadow-lg">
        <h2 className="flex items-center mb-4 text-xl font-semibold text-gray-900">
          <DocumentTextIcon className="w-6 h-6 mr-2 text-indigo-500" />
          Configuración de Prompts y Documentación
        </h2>
        
        <div className="space-y-6">
          {/* Perfil del Asistente */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-700">
                🤖 Perfil del Asistente
              </label>
              <div className="flex items-center space-x-2">
                <span className="px-2 py-1 text-xs text-gray-500 bg-blue-100 rounded">
                  Docs/Perfil.txt
                </span>
                <button
                  onClick={() => handleSaveDocs('perfil', docsContent.perfil)}
                  className="px-3 py-1 text-xs text-white transition-colors bg-blue-500 rounded hover:bg-blue-600"
                >
                  💾 Guardar
                </button>
              </div>
            </div>
            <p className="mb-2 text-xs text-gray-600">
              Define la personalidad, especialidades y comportamiento del chatbot médico
            </p>
            <textarea
              value={docsLoading ? '' : docsContent.perfil}
              onChange={(e) => setDocsContent((prev: any) => ({ ...prev, perfil: e.target.value }))}
              rows={8}
              className="w-full p-3 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder={docsLoading ? "Cargando contenido del perfil..." : "Escribe el perfil del asistente..."}
              disabled={docsLoading}
            />
          </div>

          {/* Ejemplos de Conversación */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-700">
                💬 Ejemplos de Conversaciones
              </label>
              <div className="flex items-center space-x-2">
                <span className="px-2 py-1 text-xs text-gray-500 bg-green-100 rounded">
                  Docs/ejemplo_chat.txt
                </span>
                <button
                  onClick={() => handleSaveDocs('ejemplo_chat', docsContent.ejemplo_chat)}
                  className="px-3 py-1 text-xs text-white transition-colors bg-green-500 rounded hover:bg-green-600"
                >
                  💾 Guardar
                </button>
              </div>
            </div>
            <p className="mb-2 text-xs text-gray-600">
              Patrones y ejemplos de interacciones exitosas para entrenar al modelo
            </p>
            <textarea
              value={docsLoading ? '' : docsContent.ejemplo_chat}
              onChange={(e) => setDocsContent((prev: any) => ({ ...prev, ejemplo_chat: e.target.value }))}
              rows={12}
              className="w-full p-3 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder={docsLoading ? "Cargando ejemplos de conversaciones..." : "Escribe ejemplos de conversaciones..."}
              disabled={docsLoading}
            />
          </div>

          {/* Contexto Actual */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-700">
                📊 Contexto y Estado Actual
              </label>
              <div className="flex items-center space-x-2">
                <span className="px-2 py-1 text-xs text-gray-500 bg-purple-100 rounded">
                  Docs/Ultimo_contexto.txt
                </span>
                <button
                  onClick={() => handleSaveDocs('ultimo_contexto', docsContent.ultimo_contexto)}
                  className="px-3 py-1 text-xs text-white transition-colors bg-purple-500 rounded hover:bg-purple-600"
                >
                  💾 Guardar
                </button>
              </div>
            </div>
            <p className="mb-2 text-xs text-gray-600">
              Información actualizada sobre servicios, horarios y estado del sistema
            </p>
            <textarea
              value={docsLoading ? '' : docsContent.ultimo_contexto}
              onChange={(e) => setDocsContent((prev: any) => ({ ...prev, ultimo_contexto: e.target.value }))}
              rows={10}
              className="w-full p-3 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder={docsLoading ? "Cargando contexto actual..." : "Escribe el contexto actual..."}
              disabled={docsLoading}
            />
          </div>

          {/* Botón para recargar documentación */}
          <div className="p-4 rounded-lg bg-gray-50">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-medium text-gray-900">Sincronizar Documentación</h3>
                <p className="text-xs text-gray-600">Recargar contenido desde los archivos Docs/</p>
              </div>
              <button
                onClick={loadDocsContent}
                className="px-4 py-2 text-sm text-white transition-colors bg-indigo-500 rounded-lg hover:bg-indigo-600"
              >
                🔄 Recargar Docs
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="p-6 bg-white rounded-lg shadow-lg">
        <div className="flex flex-col gap-4 sm:flex-row">
          <button
            onClick={handleSaveSettings}
            disabled={saveLoading}
            className="flex items-center justify-center flex-1 px-6 py-3 text-white transition-all duration-200 bg-blue-500 rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <BookmarkIcon className="w-5 h-5 mr-2" />
            {saveLoading ? 'Guardando...' : 'Guardar Configuración'}
          </button>

          <button
            onClick={handleSavePrompts}
            disabled={saveLoading}
            className="flex items-center justify-center flex-1 px-6 py-3 text-white transition-all duration-200 bg-green-500 rounded-lg hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <DocumentTextIcon className="w-5 h-5 mr-2" />
            {saveLoading ? 'Guardando...' : 'Guardar Prompts'}
          </button>

          <button
            onClick={handleResetToDefaults}
            className="flex items-center justify-center flex-1 px-6 py-3 text-white transition-all duration-200 bg-gray-500 rounded-lg hover:bg-gray-600"
          >
            <ArrowPathIcon className="w-5 h-5 mr-2" />
            Restablecer
          </button>
        </div>
      </div>
    </div>
  )
}