'use client'

import { useState, useEffect } from 'react'
import { apiService } from '@/lib/api'
import { 
  PlayIcon, 
  StopIcon, 
  CpuChipIcon,
  DevicePhoneMobileIcon,
  CloudIcon,
  ComputerDesktopIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  CogIcon,
  ExclamationTriangleIcon
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'

interface MainPageProps {
  systemStatus: any
  onStatusChange: (status: any) => void
}

export function MainPage({ systemStatus, onStatusChange }: MainPageProps) {
  const [modelMode, setModelMode] = useState<'local' | 'online'>('local')
  const [selectedModel, setSelectedModel] = useState<string>('')
  const [selectedReasonerModel, setSelectedReasonerModel] = useState<string>('')
  const [models, setModels] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [lmStudioStatus, setLmStudioStatus] = useState<any>(null)
  const [whatsappStatus, setWhatsappStatus] = useState<any>(null)
  const [activeTab, setActiveTab] = useState<'main' | 'reasoner'>('main')

  useEffect(() => {
    loadModels()
    loadCurrentModels()
    updateStatuses()
  }, [modelMode])

  const loadCurrentModels = async () => {
    try {
      const [currentModel, reasonerModel] = await Promise.all([
        apiService.getCurrentModel(),
        apiService.getReasonerModel()
      ])
      setSelectedModel(currentModel?.model || '')
      setSelectedReasonerModel(reasonerModel?.model || '')
    } catch (error) {
      console.error('Error loading current models:', error)
    }
  }

  const loadModels = async () => {
    try {
      if (modelMode === 'local') {
        const response = await apiService.getLMStudioModels()
        // Extraer los modelos del objeto response
        const modelsArray = response?.models || []
        setModels(Array.isArray(modelsArray) ? modelsArray : [])
      } else {
        // Para APIs online, cargar modelos disponibles desde el backend
        const response = await apiService.getAvailableOnlineModels()
        const onlineModels = []
        for (const [provider, models] of Object.entries(response)) {
          for (const model of models as any[]) {
            onlineModels.push({ ...model, provider })
          }
        }
        setModels(onlineModels)
      }
    } catch (error) {
      console.error('Error loading models:', error)
      toast.error('Error al cargar modelos')
      setModels([])
    }
  }

  const updateStatuses = async () => {
    try {
      const [systemData, waStatus] = await Promise.all([
        apiService.getSystemStatus(),
        apiService.getWhatsAppStatus()
      ])
      setLmStudioStatus(systemData)
      setWhatsappStatus(waStatus)
    } catch (error) {
      console.error('Error updating statuses:', error)
    }
  }

  const handleStartLMStudio = async () => {
    if (modelMode === 'online') {
      // Redirigir a configuración para API keys
      toast.error('Primero configura las API keys en la sección de Configuración')
      return
    }

    setLoading(true)
    try {
      const response = await apiService.startLMStudio()
      if (response.status === 'success') {
        toast.success(response.message || 'Iniciando LM Studio...')
      } else {
        toast.error(response.message || 'Error al iniciar LM Studio')
      }
      await updateStatuses()
    } catch (error: any) {
      toast.error(error.message || 'Error al iniciar LM Studio')
    } finally {
      setLoading(false)
    }
  }

  const handleStopLMStudio = async () => {
    setLoading(true)
    try {
      await apiService.stopLMStudioServer()
      toast.success('Deteniendo LM Studio...')
      await updateStatuses()
    } catch (error) {
      toast.error('Error al detener LM Studio')
    } finally {
      setLoading(false)
    }
  }

  const handleLoadModel = async () => {
    if (!selectedModel) {
      toast.error('Selecciona un modelo primero')
      return
    }

    setLoading(true)
    try {
      if (modelMode === 'local') {
        await apiService.loadLMStudioModel(selectedModel)
        await apiService.setCurrentModel(selectedModel)
      } else {
        await apiService.setCurrentModel(selectedModel)
      }
      toast.success('Modelo principal cargado exitosamente')
      updateStatuses()
    } catch (error) {
      toast.error('Error al cargar modelo principal')
    } finally {
      setLoading(false)
    }
  }

  const handleLoadReasonerModel = async () => {
    if (!selectedReasonerModel) {
      toast.error('Selecciona un modelo reasoning primero')
      return
    }

    setLoading(true)
    try {
      await apiService.setReasonerModel(selectedReasonerModel)
      toast.success('Modelo reasoning configurado exitosamente')
      updateStatuses()
    } catch (error) {
      toast.error('Error al configurar modelo reasoning')
    } finally {
      setLoading(false)
    }
  }

  const handleStartWhatsApp = async () => {
    // Verificar si LM Studio está corriendo (para modo local) o si hay API configurada (para online)
    if (modelMode === 'local') {
      // Verificar múltiples indicadores de que LM Studio está funcionando
      const isLMStudioRunning = lmStudioStatus?.status === 'running' || lmStudioStatus?.status === 'healthy'
      
      if (!isLMStudioRunning) {
        toast.error('Primero inicia el servidor de LM Studio')
        return
      }
    }

    setLoading(true)
    try {
      await apiService.startWhatsApp()
      toast.success('Iniciando WhatsApp...')
      setTimeout(updateStatuses, 3000)
    } catch (error) {
      toast.error('Error al iniciar WhatsApp')
    } finally {
      setLoading(false)
    }
  }

  const handleStopWhatsApp = async () => {
    setLoading(true)
    try {
      await apiService.stopWhatsApp()
      toast.success('Deteniendo WhatsApp...')
      setTimeout(updateStatuses, 2000)
    } catch (error) {
      toast.error('Error al detener WhatsApp')
    } finally {
      setLoading(false)
    }
  }

  const handleStopAll = async () => {
    setLoading(true)
    try {
      await apiService.stopAllServices()
      toast.success('Deteniendo todos los servicios...')
      setTimeout(updateStatuses, 3000)
    } catch (error) {
      toast.error('Error al detener servicios')
    } finally {
      setLoading(false)
    }
  }

  const getStatusIcon = (isRunning: boolean, isLoading: boolean = false) => {
    if (isLoading) return <ClockIcon className="h-5 w-5 text-yellow-500 animate-spin" />
    if (isRunning) return <CheckCircleIcon className="h-5 w-5 text-green-500" />
    return <XCircleIcon className="h-5 w-5 text-red-500" />
  }

  const getBackendHealthIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircleIcon className="h-5 w-5 text-green-500" />
      case 'warning':
        return <ExclamationTriangleIcon className="h-5 w-5 text-yellow-500" />
      case 'critical':
        return <XCircleIcon className="h-5 w-5 text-red-500" />
      default:
        return <ClockIcon className="h-5 w-5 text-gray-500" />
    }
  }

  const getBackendStatusText = (status: string, issues: string[] = []) => {
    const statusTexts: {[key: string]: string} = {
      'healthy': 'Servidor Saludable',
      'warning': 'Servidor con Advertencias', 
      'critical': 'Servidor con Problemas Críticos',
      'ok': 'Servidor Funcionando' // fallback para compatibilidad
    }
    
    const mainText = statusTexts[status] || 'Estado Desconocido'
    
    if (issues && issues.length > 0) {
      return `${mainText} - ${issues[0]}`
    }
    
    return mainText
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Panel de Control Principal</h1>
        <p className="text-gray-600">Controla todos los servicios del chatbot desde aquí</p>
      </div>

      {/* Paso 1: Selección de modo */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
          <CogIcon className="h-6 w-6 mr-2 text-blue-500" />
          1. Seleccionar Modo de Operación
        </h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <button
            onClick={() => setModelMode('local')}
            className={`p-6 rounded-lg border-2 transition-all duration-200 ${
              modelMode === 'local'
                ? 'border-blue-500 bg-blue-50 shadow-lg transform scale-105'
                : 'border-gray-200 hover:border-gray-300 hover:shadow-md'
            }`}
          >
            <div className="flex items-center justify-center mb-3">
              <ComputerDesktopIcon className={`h-12 w-12 ${modelMode === 'local' ? 'text-blue-500' : 'text-gray-400'}`} />
            </div>
            <h3 className={`text-lg font-semibold mb-2 ${modelMode === 'local' ? 'text-blue-900' : 'text-gray-700'}`}>
              Modelos Locales
            </h3>
            <p className={`text-sm ${modelMode === 'local' ? 'text-blue-700' : 'text-gray-500'}`}>
              Usar LM Studio y modelos descargados localmente
            </p>
          </button>

          <button
            onClick={() => setModelMode('online')}
            className={`p-6 rounded-lg border-2 transition-all duration-200 ${
              modelMode === 'online'
                ? 'border-blue-500 bg-blue-50 shadow-lg transform scale-105'
                : 'border-gray-200 hover:border-gray-300 hover:shadow-md'
            }`}
          >
            <div className="flex items-center justify-center mb-3">
              <CloudIcon className={`h-12 w-12 ${modelMode === 'online' ? 'text-blue-500' : 'text-gray-400'}`} />
            </div>
            <h3 className={`text-lg font-semibold mb-2 ${modelMode === 'online' ? 'text-blue-900' : 'text-gray-700'}`}>
              APIs Online
            </h3>
            <p className={`text-sm ${modelMode === 'online' ? 'text-blue-700' : 'text-gray-500'}`}>
              Usar OpenAI, Claude, Gemini, etc.
            </p>
          </button>
        </div>
      </div>

      {/* Paso 2: Gestión de Servidor/API */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
          <CpuChipIcon className="h-6 w-6 mr-2 text-green-500" />
          2. {modelMode === 'local' ? 'Servidor LM Studio' : 'Configuración API'}
        </h2>

        {modelMode === 'local' ? (
          <div className="space-y-4">
            {/* Estado del Backend/Servidor */}
            <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
              <div className="flex items-center space-x-3">
                {getBackendHealthIcon(lmStudioStatus?.status || 'unknown')}
                <div>
                  <div className="font-medium text-gray-900">Estado del Backend</div>
                  <div className="text-sm text-gray-500">
                    {getBackendStatusText(
                      lmStudioStatus?.server_health?.status || lmStudioStatus?.status || 'unknown',
                      lmStudioStatus?.server_health?.issues || []
                    )}
                  </div>
                </div>
              </div>
              <div className="text-xs text-gray-400">
                {lmStudioStatus?.server_health?.timestamp ? 
                  `Último check: ${new Date(lmStudioStatus.server_health.timestamp).toLocaleTimeString()}` 
                  : 'Verificando...'
                }
              </div>
            </div>

            {/* Estado del LM Studio */}
            <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
              <div className="flex items-center space-x-3">
                {getStatusIcon(lmStudioStatus?.lm_studio?.is_running, loading)}
                <div>
                  <div className="font-medium text-gray-900">LM Studio</div>
                  <div className="text-sm text-gray-500">
                    {lmStudioStatus?.lm_studio?.status || 'Verificando...'}
                    {lmStudioStatus?.lm_studio?.current_model && 
                      ` - ${lmStudioStatus.lm_studio.current_model}`
                    }
                  </div>
                </div>
              </div>
              <div className="space-x-2">
                <button
                  onClick={handleStartLMStudio}
                  disabled={loading || lmStudioStatus?.status?.includes('running')}
                  className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                >
                  <PlayIcon className="h-4 w-4 inline mr-1" />
                  Iniciar
                </button>
                <button
                  onClick={handleStopLMStudio}
                  disabled={loading || !(lmStudioStatus?.status === 'running' || lmStudioStatus?.status === 'healthy')}
                  className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                >
                  <StopIcon className="h-4 w-4 inline mr-1" />
                  Detener
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="p-4 bg-yellow-50 rounded-lg border border-yellow-200">
            <div className="flex">
              <CogIcon className="h-5 w-5 text-yellow-600 mt-0.5 mr-2" />
              <div>
                <div className="font-medium text-yellow-800">Configuración Requerida</div>
                <div className="text-sm text-yellow-700 mt-1">
                  Ve a la sección de Configuración para agregar tus API keys
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Paso 3: Selección de Modelos */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
          <CpuChipIcon className="h-6 w-6 mr-2 text-purple-500" />
          3. Configuración de Modelos
        </h2>

        {/* Tabs para Main, Reasoning y Online APIs */}
        <div className="mb-6">
          <div className="border-b border-gray-200">
            <nav className="-mb-px flex space-x-8">
              <button
                onClick={() => setActiveTab('main')}
                className={`py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'main'
                    ? 'border-purple-500 text-purple-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Modelo Principal
              </button>
              <button
                onClick={() => setActiveTab('reasoner')}
                className={`py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'reasoner'
                    ? 'border-purple-500 text-purple-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Modelo Reasoning
              </button>
            </nav>
          </div>
        </div>

        {/* Contenido del tab activo */}
        <div className="space-y-4">
          {activeTab === 'main' && (
            <div>
              <div className="mb-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
                <p className="text-sm text-blue-700">
                  <strong>Modelo Principal:</strong> Se usa para las conversaciones generales con los usuarios
                </p>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Modelo Principal Disponible
                </label>
                <select
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-900 bg-white"
                >
                  <option value="" className="text-gray-500">Seleccionar modelo principal...</option>
                  {Array.isArray(models) && models.map((model) => (
                    <option key={model.id || model.name} value={model.name || model.id} className="text-gray-900 bg-white">
                      {model.name || model.id}
                      {model.provider && ` (${model.provider})`}
                    </option>
                  ))}
                </select>
              </div>

              <button
                onClick={handleLoadModel}
                disabled={!selectedModel || loading}
                className="w-full py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
              >
                {loading ? 'Cargando...' : 'Configurar Modelo Principal'}
              </button>
            </div>
          )}
          
          {activeTab === 'reasoner' && (
            <div>
              <div className="mb-4 p-3 bg-purple-50 rounded-lg border border-purple-200">
                <p className="text-sm text-purple-700">
                  <strong>Modelo Reasoning:</strong> Se usa para análisis profundo y razonamiento estratégico cada cierto número de mensajes
                </p>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Modelo Reasoning Disponible
                </label>
                <select
                  value={selectedReasonerModel}
                  onChange={(e) => setSelectedReasonerModel(e.target.value)}
                  className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent text-gray-900 bg-white"
                >
                  <option value="" className="text-gray-500">Seleccionar modelo reasoning...</option>
                  {Array.isArray(models) && models.map((model) => (
                    <option key={`reasoner_${model.id || model.name}`} value={model.name || model.id} className="text-gray-900 bg-white">
                      {model.name || model.id}
                      {model.provider && ` (${model.provider})`}
                    </option>
                  ))}
                </select>
              </div>

              <button
                onClick={handleLoadReasonerModel}
                disabled={!selectedReasonerModel || loading}
                className="w-full py-3 bg-purple-500 text-white rounded-lg hover:bg-purple-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
              >
                {loading ? 'Configurando...' : 'Configurar Modelo Reasoning'}
              </button>

              <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                <p className="text-xs text-gray-600">
                  💡 <strong>Recomendación:</strong> Usa un modelo más potente para reasoning (como GPT-4 o Claude) 
                  y uno más rápido para conversaciones generales.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Paso 4: Control de WhatsApp */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
          <DevicePhoneMobileIcon className="h-6 w-6 mr-2 text-green-500" />
          4. Control de WhatsApp
        </h2>

        <div className="space-y-4">
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
            <div className="flex items-center space-x-3">
              {getStatusIcon(whatsappStatus?.status === 'connected', loading)}
              <div>
                <div className="font-medium text-gray-900">Estado de WhatsApp</div>
                <div className="text-sm text-gray-500">
                  {whatsappStatus?.status === 'connected' ? 'Conectado y funcionando' : 'Desconectado'}
                </div>
              </div>
            </div>
            <div className="space-x-2">
              <button
                onClick={handleStartWhatsApp}
                disabled={loading || whatsappStatus?.status === 'connected'}
                className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
              >
                <PlayIcon className="h-4 w-4 inline mr-1" />
                Iniciar
              </button>
              <button
                onClick={handleStopWhatsApp}
                disabled={loading || whatsappStatus?.status !== 'connected'}
                className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
              >
                <StopIcon className="h-4 w-4 inline mr-1" />
                Detener
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Control Global */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Control Global</h2>
        
        <button
          onClick={handleStopAll}
          disabled={loading}
          className="w-full py-3 bg-red-500 text-white rounded-lg hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
        >
          <StopIcon className="h-5 w-5 inline mr-2" />
          Detener Todos los Servicios
        </button>
      </div>
    </div>
  )
}