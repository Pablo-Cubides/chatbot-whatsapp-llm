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
  ArrowPathIcon
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'

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
  const [loading, setLoading] = useState(false)
  const [saveLoading, setSaveLoading] = useState(false)

  useEffect(() => {
    loadConfiguration()
    loadDocsContent()
  }, [])

  const loadDocsContent = async () => {
    try {
      // Cargar contenido de los archivos de documentación
      const docsData = await apiService.getDocsContent()
      if (docsData) {
        setDocsContent(docsData)
        // Actualizar los prompts con el contenido real de los documentos
        setPrompts((prev: any) => ({
          ...prev,
          system_prompt: docsData.perfil || prev.system_prompt,
          initial_prompt: docsData.ejemplo_chat || prev.initial_prompt,
          reasoning_prompt: docsData.ultimo_contexto || prev.reasoning_prompt
        }))
      }
    } catch (error) {
      console.error('Error loading docs content:', error)
      // Si no se pueden cargar los docs, usar valores por defecto
      setDocsContent({
        perfil: 'Eres un asistente médico especializado en gestión de citas...',
        ejemplo_chat: 'Ejemplos de conversaciones exitosas...',
        ultimo_contexto: 'Contexto actual del sistema...'
      })
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
      }
    } catch (error) {
      console.error('Error loading configuration:', error)
      toast.error('Error al cargar configuración')
    } finally {
      setLoading(false)
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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-600">Cargando configuración...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-2 flex items-center">
          <CogIcon className="h-7 w-7 mr-3 text-blue-500" />
          Configuración del Sistema
        </h1>
        <p className="text-gray-600">Configura API keys, parámetros de modelos y prompts del sistema</p>
      </div>

      {/* API Keys Section */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
          <KeyIcon className="h-6 w-6 mr-2 text-green-500" />
          API Keys para Modelos Online
        </h2>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              OpenAI API Key
            </label>
            <input
              type="password"
              value={apiKeys.openai}
              onChange={(e) => setApiKeys((prev: any) => ({ ...prev, openai: e.target.value }))}
              className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="sk-..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Claude API Key (Anthropic)
            </label>
            <input
              type="password"
              value={apiKeys.claude}
              onChange={(e) => setApiKeys((prev: any) => ({ ...prev, claude: e.target.value }))}
              className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="sk-ant-..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Gemini API Key (Google)
            </label>
            <input
              type="password"
              value={apiKeys.gemini}
              onChange={(e) => setApiKeys((prev: any) => ({ ...prev, gemini: e.target.value }))}
              className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="AIza..."
            />
          </div>
        </div>
      </div>

      {/* Model Configuration */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
          <AdjustmentsHorizontalIcon className="h-6 w-6 mr-2 text-purple-500" />
          Configuración de Modelos
        </h2>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Temperatura: <span className="font-bold text-blue-600">{modelConfig.temperature}</span>
              <span className="text-xs text-gray-500 ml-1">(0.0 - 2.0)</span>
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
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>Preciso</span>
              <span>Creativo</span>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Max Tokens: <span className="font-bold text-green-600">{modelConfig.max_tokens}</span>
              <span className="text-xs text-gray-500 ml-1">(50 - 4000)</span>
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
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>50</span>
              <span>4000</span>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Top P: <span className="font-bold text-purple-600">{modelConfig.top_p}</span>
              <span className="text-xs text-gray-500 ml-1">(0.0 - 1.0)</span>
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
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>Determinístico</span>
              <span>Diverso</span>
            </div>
          </div>
        </div>

        {/* Configuración adicional */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Reasoning cada X mensajes
              <span className="text-xs text-gray-500 ml-1">(1 - 50)</span>
            </label>
            <input
              type="number"
              min="1"
              max="50"
              value={settings.reason_after_messages || 10}
              onChange={(e) => setSettings((prev: any) => ({ ...prev, reason_after_messages: parseInt(e.target.value) }))}
              className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-900"
            />
          </div>

          <div className="flex items-center">
            <input
              type="checkbox"
              id="respond-to-all"
              checked={settings.respond_to_all || false}
              onChange={(e) => setSettings((prev: any) => ({ ...prev, respond_to_all: e.target.checked }))}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
            />
            <label htmlFor="respond-to-all" className="ml-2 block text-sm text-gray-900">
              <span className="font-medium">Responder a TODOS los mensajes</span>
              <span className="block text-xs text-gray-500">No solo a contactos de la lista</span>
            </label>
          </div>
        </div>
      </div>

      {/* Prompts Configuration */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
          <DocumentTextIcon className="h-6 w-6 mr-2 text-indigo-500" />
          Configuración de Prompts y Documentación
        </h2>
        
        <div className="space-y-6">
          {/* Perfil del Asistente */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-700">
                🤖 Perfil del Asistente
              </label>
              <span className="text-xs text-gray-500 bg-blue-100 px-2 py-1 rounded">
                Docs/Perfil.txt
              </span>
            </div>
            <p className="text-xs text-gray-600 mb-2">
              Define la personalidad, especialidades y comportamiento del chatbot médico
            </p>
            <textarea
              value={prompts.system_prompt || docsContent.perfil}
              onChange={(e) => setPrompts((prev: any) => ({ ...prev, system_prompt: e.target.value }))}
              rows={8}
              className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
              placeholder="Cargando contenido del perfil..."
            />
          </div>

          {/* Ejemplos de Conversación */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-700">
                💬 Ejemplos de Conversaciones
              </label>
              <span className="text-xs text-gray-500 bg-green-100 px-2 py-1 rounded">
                Docs/ejemplo_chat.txt
              </span>
            </div>
            <p className="text-xs text-gray-600 mb-2">
              Patrones y ejemplos de interacciones exitosas para entrenar al modelo
            </p>
            <textarea
              value={prompts.initial_prompt || docsContent.ejemplo_chat}
              onChange={(e) => setPrompts((prev: any) => ({ ...prev, initial_prompt: e.target.value }))}
              rows={12}
              className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
              placeholder="Cargando ejemplos de conversaciones..."
            />
          </div>

          {/* Contexto Actual */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-700">
                📊 Contexto y Estado Actual
              </label>
              <span className="text-xs text-gray-500 bg-purple-100 px-2 py-1 rounded">
                Docs/Ultimo_contexto.txt
              </span>
            </div>
            <p className="text-xs text-gray-600 mb-2">
              Información actualizada sobre servicios, horarios y estado del sistema
            </p>
            <textarea
              value={prompts.reasoning_prompt || docsContent.ultimo_contexto}
              onChange={(e) => setPrompts((prev: any) => ({ ...prev, reasoning_prompt: e.target.value }))}
              rows={10}
              className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
              placeholder="Cargando contexto actual..."
            />
          </div>

          {/* Botón para recargar documentación */}
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-medium text-gray-900">Sincronizar Documentación</h3>
                <p className="text-xs text-gray-600">Recargar contenido desde los archivos Docs/</p>
              </div>
              <button
                onClick={loadDocsContent}
                className="px-4 py-2 bg-indigo-500 text-white rounded-lg hover:bg-indigo-600 transition-colors text-sm"
              >
                🔄 Recargar Docs
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <div className="flex flex-col sm:flex-row gap-4">
          <button
            onClick={handleSaveSettings}
            disabled={saveLoading}
            className="flex-1 flex items-center justify-center px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
          >
            <BookmarkIcon className="h-5 w-5 mr-2" />
            {saveLoading ? 'Guardando...' : 'Guardar Configuración'}
          </button>

          <button
            onClick={handleSavePrompts}
            disabled={saveLoading}
            className="flex-1 flex items-center justify-center px-6 py-3 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
          >
            <DocumentTextIcon className="h-5 w-5 mr-2" />
            {saveLoading ? 'Guardando...' : 'Guardar Prompts'}
          </button>

          <button
            onClick={handleResetToDefaults}
            className="flex-1 flex items-center justify-center px-6 py-3 bg-gray-500 text-white rounded-lg hover:bg-gray-600 transition-all duration-200"
          >
            <ArrowPathIcon className="h-5 w-5 mr-2" />
            Restablecer
          </button>
        </div>
      </div>
    </div>
  )
}