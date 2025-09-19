'use client'

import { useState, useEffect } from 'react'
import { 
  QuestionMarkCircleIcon,
  XMarkIcon,
  PlayIcon,
  ChevronRightIcon,
  CheckCircleIcon,
  ClockIcon
} from '@heroicons/react/24/outline'

interface GuideStep {
  id: string
  title: string
  description: string
  content: React.ReactNode
  completed: boolean
  estimated_time: number // in minutes
}

interface Guide {
  id: string
  title: string
  description: string
  category: 'setup' | 'messaging' | 'automation' | 'advanced'
  difficulty: 'beginner' | 'intermediate' | 'advanced'
  steps: GuideStep[]
  total_time: number
}

const guides: Guide[] = [
  {
    id: 'initial-setup',
    title: 'Configuración Inicial',
    description: 'Configura tu chatbot de WhatsApp paso a paso',
    category: 'setup',
    difficulty: 'beginner',
    total_time: 15,
    steps: [
      {
        id: 'connect-whatsapp',
        title: 'Conectar WhatsApp',
        description: 'Escanea el código QR para conectar tu cuenta de WhatsApp',
        content: (
          <div className="space-y-4">
            <p className="text-gray-700">
              1. Abre WhatsApp en tu teléfono<br/>
              2. Ve a Configuración → Dispositivos vinculados<br/>
              3. Toca "Vincular un dispositivo"<br/>
              4. Escanea el código QR que aparece en el dashboard
            </p>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <p className="text-blue-700 text-sm">
                <strong>Tip:</strong> Asegúrate de que tu teléfono tenga conexión a internet estable durante este proceso.
              </p>
            </div>
          </div>
        ),
        completed: false,
        estimated_time: 3
      },
      {
        id: 'configure-llm',
        title: 'Configurar Modelo de IA',
        description: 'Selecciona y configura el modelo de inteligencia artificial',
        content: (
          <div className="space-y-4">
            <p className="text-gray-700">
              1. Ve a la sección de Configuración<br/>
              2. Selecciona "Modelos de IA"<br/>
              3. Elige entre LM Studio (local) u OpenAI (en línea)<br/>
              4. Configura los parámetros del modelo
            </p>
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <p className="text-yellow-700 text-sm">
                <strong>Recomendación:</strong> Para empezar, usa LM Studio con el modelo llama-3.1-8b-instruct.
              </p>
            </div>
          </div>
        ),
        completed: false,
        estimated_time: 5
      },
      {
        id: 'test-conversation',
        title: 'Probar Conversación',
        description: 'Envía un mensaje de prueba para verificar que todo funciona',
        content: (
          <div className="space-y-4">
            <p className="text-gray-700">
              1. Ve a la sección de Mensajería<br/>
              2. Selecciona un contacto de prueba<br/>
              3. Envía un mensaje simple como "Hola"<br/>
              4. Verifica que el bot responda correctamente
            </p>
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <p className="text-green-700 text-sm">
                <strong>¡Perfecto!</strong> Si recibes una respuesta, tu chatbot está funcionando correctamente.
              </p>
            </div>
          </div>
        ),
        completed: false,
        estimated_time: 2
      }
    ]
  },
  {
    id: 'send-messages',
    title: 'Enviar Mensajes',
    description: 'Aprende a enviar mensajes individuales y masivos',
    category: 'messaging',
    difficulty: 'beginner',
    total_time: 10,
    steps: [
      {
        id: 'individual-message',
        title: 'Mensaje Individual',
        description: 'Envía un mensaje a un contacto específico',
        content: (
          <div className="space-y-4">
            <p className="text-gray-700">
              1. Ve a la sección de Mensajería<br/>
              2. Selecciona un contacto de la lista<br/>
              3. Escribe tu mensaje en el área de texto<br/>
              4. Haz clic en "Enviar"
            </p>
          </div>
        ),
        completed: false,
        estimated_time: 3
      },
      {
        id: 'bulk-message',
        title: 'Mensaje Masivo',
        description: 'Envía el mismo mensaje a múltiples contactos',
        content: (
          <div className="space-y-4">
            <p className="text-gray-700">
              1. Ve a la sección de Mensajería<br/>
              2. Selecciona "Mensaje Masivo"<br/>
              3. Elige los contactos destinatarios<br/>
              4. Escribe tu mensaje y programa el envío
            </p>
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <p className="text-yellow-700 text-sm">
                <strong>Importante:</strong> Respeta los límites de WhatsApp para evitar restricciones.
              </p>
            </div>
          </div>
        ),
        completed: false,
        estimated_time: 7
      }
    ]
  },
  {
    id: 'automation-rules',
    title: 'Reglas de Automatización',
    description: 'Configura respuestas automáticas y reglas de negocio',
    category: 'automation',
    difficulty: 'intermediate',
    total_time: 20,
    steps: [
      {
        id: 'create-rule',
        title: 'Crear Regla',
        description: 'Configura una regla de automatización básica',
        content: (
          <div className="space-y-4">
            <p className="text-gray-700">
              1. Ve a la sección de Automatización<br/>
              2. Haz clic en "Nueva Regla"<br/>
              3. Define las condiciones de activación<br/>
              4. Configura la respuesta automática
            </p>
          </div>
        ),
        completed: false,
        estimated_time: 10
      },
      {
        id: 'test-automation',
        title: 'Probar Automatización',
        description: 'Verifica que las reglas funcionen correctamente',
        content: (
          <div className="space-y-4">
            <p className="text-gray-700">
              1. Envía un mensaje que active la regla<br/>
              2. Verifica la respuesta automática<br/>
              3. Revisa los logs de automatización<br/>
              4. Ajusta la regla si es necesario
            </p>
          </div>
        ),
        completed: false,
        estimated_time: 10
      }
    ]
  }
]

interface UserGuideSystemProps {
  isOpen: boolean
  onClose: () => void
}

export default function UserGuideSystem({ isOpen, onClose }: UserGuideSystemProps) {
  const [selectedGuide, setSelectedGuide] = useState<Guide | null>(null)
  const [currentStepIndex, setCurrentStepIndex] = useState(0)
  const [completedSteps, setCompletedSteps] = useState<Set<string>>(new Set())

  useEffect(() => {
    // Load completed steps from localStorage
    const saved = localStorage.getItem('guide-completed-steps')
    if (saved) {
      setCompletedSteps(new Set(JSON.parse(saved)))
    }
  }, [])

  const markStepCompleted = (stepId: string) => {
    const newCompleted = new Set(completedSteps)
    newCompleted.add(stepId)
    setCompletedSteps(newCompleted)
    localStorage.setItem('guide-completed-steps', JSON.stringify(Array.from(newCompleted)))
  }

  const startGuide = (guide: Guide) => {
    setSelectedGuide(guide)
    setCurrentStepIndex(0)
  }

  const nextStep = () => {
    if (selectedGuide && currentStepIndex < selectedGuide.steps.length - 1) {
      setCurrentStepIndex(currentStepIndex + 1)
    }
  }

  const prevStep = () => {
    if (currentStepIndex > 0) {
      setCurrentStepIndex(currentStepIndex - 1)
    }
  }

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty) {
      case 'beginner': return 'bg-green-100 text-green-800'
      case 'intermediate': return 'bg-yellow-100 text-yellow-800'
      case 'advanced': return 'bg-red-100 text-red-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'setup': return '⚙️'
      case 'messaging': return '💬'
      case 'automation': return '🤖'
      case 'advanced': return '🔧'
      default: return '📖'
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black bg-opacity-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div className="flex items-center space-x-3">
            <QuestionMarkCircleIcon className="h-8 w-8 text-blue-500" />
            <div>
              <h2 className="text-xl font-semibold text-gray-900">
                {selectedGuide ? selectedGuide.title : 'Sistema de Guías'}
              </h2>
              <p className="text-sm text-gray-500">
                {selectedGuide ? selectedGuide.description : 'Aprende a usar el chatbot paso a paso'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-500"
          >
            <XMarkIcon className="h-6 w-6" />
          </button>
        </div>

        <div className="flex h-[calc(90vh-120px)]">
          {/* Sidebar - Lista de guías */}
          {!selectedGuide && (
            <div className="w-full p-6 overflow-y-auto">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {guides.map((guide) => {
                  const completedCount = guide.steps.filter(step => completedSteps.has(step.id)).length
                  const progress = (completedCount / guide.steps.length) * 100

                  return (
                    <div
                      key={guide.id}
                      className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer"
                      onClick={() => startGuide(guide)}
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex items-center space-x-2">
                          <span className="text-2xl">{getCategoryIcon(guide.category)}</span>
                          <div>
                            <h3 className="font-medium text-gray-900">{guide.title}</h3>
                            <p className="text-sm text-gray-500">{guide.description}</p>
                          </div>
                        </div>
                        <ChevronRightIcon className="h-5 w-5 text-gray-400" />
                      </div>

                      <div className="flex items-center justify-between mb-2">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${getDifficultyColor(guide.difficulty)}`}>
                          {guide.difficulty}
                        </span>
                        <div className="flex items-center text-sm text-gray-500">
                          <ClockIcon className="h-4 w-4 mr-1" />
                          {guide.total_time} min
                        </div>
                      </div>

                      {/* Progress bar */}
                      <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
                        <div
                          className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${progress}%` }}
                        />
                      </div>
                      <p className="text-xs text-gray-500">
                        {completedCount} de {guide.steps.length} pasos completados
                      </p>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Content - Guía seleccionada */}
          {selectedGuide && (
            <>
              {/* Steps sidebar */}
              <div className="w-1/3 border-r border-gray-200 p-4 overflow-y-auto">
                <button
                  onClick={() => setSelectedGuide(null)}
                  className="text-blue-500 hover:text-blue-700 text-sm mb-4 flex items-center"
                >
                  ← Volver a las guías
                </button>

                <div className="space-y-3">
                  {selectedGuide.steps.map((step, index) => {
                    const isCompleted = completedSteps.has(step.id)
                    const isCurrent = index === currentStepIndex
                    
                    return (
                      <div
                        key={step.id}
                        className={`p-3 rounded-lg cursor-pointer transition-colors ${
                          isCurrent 
                            ? 'bg-blue-50 border-2 border-blue-200' 
                            : isCompleted
                            ? 'bg-green-50 border border-green-200'
                            : 'bg-gray-50 border border-gray-200 hover:bg-gray-100'
                        }`}
                        onClick={() => setCurrentStepIndex(index)}
                      >
                        <div className="flex items-center space-x-3">
                          <div className={`flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${
                            isCompleted 
                              ? 'bg-green-500 text-white' 
                              : isCurrent
                              ? 'bg-blue-500 text-white'
                              : 'bg-gray-300 text-gray-600'
                          }`}>
                            {isCompleted ? <CheckCircleIcon className="h-4 w-4" /> : index + 1}
                          </div>
                          <div className="flex-1 min-w-0">
                            <h4 className="text-sm font-medium text-gray-900 truncate">
                              {step.title}
                            </h4>
                            <p className="text-xs text-gray-500 truncate">
                              {step.description}
                            </p>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Step content */}
              <div className="flex-1 flex flex-col">
                <div className="flex-1 p-6 overflow-y-auto">
                  {selectedGuide.steps[currentStepIndex] && (
                    <div>
                      <div className="mb-4">
                        <h3 className="text-lg font-semibold text-gray-900 mb-2">
                          {selectedGuide.steps[currentStepIndex].title}
                        </h3>
                        <p className="text-gray-600 mb-4">
                          {selectedGuide.steps[currentStepIndex].description}
                        </p>
                        <div className="flex items-center text-sm text-gray-500 mb-6">
                          <ClockIcon className="h-4 w-4 mr-1" />
                          Tiempo estimado: {selectedGuide.steps[currentStepIndex].estimated_time} minutos
                        </div>
                      </div>

                      <div className="prose max-w-none">
                        {selectedGuide.steps[currentStepIndex].content}
                      </div>
                    </div>
                  )}
                </div>

                {/* Navigation */}
                <div className="border-t border-gray-200 p-4 flex items-center justify-between">
                  <button
                    onClick={prevStep}
                    disabled={currentStepIndex === 0}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Anterior
                  </button>

                  <div className="flex items-center space-x-3">
                    <button
                      onClick={() => markStepCompleted(selectedGuide.steps[currentStepIndex].id)}
                      disabled={completedSteps.has(selectedGuide.steps[currentStepIndex].id)}
                      className="px-4 py-2 text-sm font-medium text-white bg-green-600 border border-transparent rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {completedSteps.has(selectedGuide.steps[currentStepIndex].id) ? 'Completado ✓' : 'Marcar como completado'}
                    </button>

                    <button
                      onClick={nextStep}
                      disabled={currentStepIndex === selectedGuide.steps.length - 1}
                      className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Siguiente
                    </button>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}