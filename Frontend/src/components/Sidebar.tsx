'use client'

import { 
  HomeIcon, 
  CogIcon, 
  UsersIcon, 
  ChartBarIcon,
  WifiIcon,
  XCircleIcon,
  CheckCircleIcon,
  ClockIcon,
  AdjustmentsHorizontalIcon
} from '@heroicons/react/24/outline'

type Page = 'main' | 'config' | 'contacts' | 'stats' | 'settings'

interface SidebarProps {
  currentPage: Page
  onPageChange: (page: Page) => void
  systemStatus: any
}

const menuItems = [
  {
    id: 'main' as Page,
    name: 'Principal',
    icon: HomeIcon,
    description: 'Control principal del sistema'
  },
  {
    id: 'config' as Page,
    name: 'Configuración',
    icon: CogIcon,
    description: 'Configurar modelos y API keys'
  },
  {
    id: 'contacts' as Page,
    name: 'Contactos',
    icon: UsersIcon,
    description: 'Gestión de contactos y mensajes'
  },
  {
    id: 'stats' as Page,
    name: 'Estadísticas',
    icon: ChartBarIcon,
    description: 'Métricas y análisis'
  },
  
]

export function Sidebar({ currentPage, onPageChange, systemStatus }: SidebarProps) {
  const getStatusIndicator = () => {
    if (!systemStatus) {
      return {
        icon: ClockIcon,
        color: 'text-yellow-500',
        bg: 'bg-yellow-100',
        text: 'Conectando...'
      }
    }

    const whatsappRunning = systemStatus?.whatsapp?.is_running
    const lmStudioRunning = systemStatus?.lm_studio?.is_running

    if (whatsappRunning && lmStudioRunning) {
      return {
        icon: CheckCircleIcon,
        color: 'text-green-500',
        bg: 'bg-green-100',
        text: 'Todo funcionando'
      }
    } else if (whatsappRunning || lmStudioRunning) {
      return {
        icon: WifiIcon,
        color: 'text-yellow-500',
        bg: 'bg-yellow-100',
        text: 'Parcialmente activo'
      }
    } else {
      return {
        icon: XCircleIcon,
        color: 'text-red-500',
        bg: 'bg-red-100',
        text: 'Servicios detenidos'
      }
    }
  }

  const status = getStatusIndicator()

  return (
    <div className="w-64 bg-white shadow-xl border-r border-gray-200 flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-gray-200">
        <h1 className="text-xl font-bold text-gray-900 mb-2">
          🤖 Chatbot Admin
        </h1>
        
        {/* Status Indicator */}
        <div className={`flex items-center space-x-2 p-3 rounded-lg ${status.bg} transition-all duration-300`}>
          <status.icon className={`h-5 w-5 ${status.color}`} />
          <span className={`text-sm font-medium ${status.color}`}>
            {status.text}
          </span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-2">
        {menuItems.map((item) => {
          const isActive = currentPage === item.id
          return (
            <button
              key={item.id}
              onClick={() => onPageChange(item.id)}
              className={`
                w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-left transition-all duration-200
                ${isActive 
                  ? 'bg-gradient-to-r from-blue-500 to-indigo-600 text-white shadow-lg transform scale-105' 
                  : 'text-gray-700 hover:bg-gray-100 hover:shadow-md'
                }
              `}
            >
              <item.icon className={`h-5 w-5 ${isActive ? 'text-white' : 'text-gray-500'}`} />
              <div className="flex-1">
                <div className={`font-medium ${isActive ? 'text-white' : 'text-gray-900'}`}>
                  {item.name}
                </div>
                <div className={`text-xs ${isActive ? 'text-blue-100' : 'text-gray-500'}`}>
                  {item.description}
                </div>
              </div>
            </button>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-gray-200">
        <div className="text-xs text-gray-500 text-center">
          <div>WhatsApp Chatbot</div>
          <div>V1.0.0</div>
        </div>
      </div>
    </div>
  )
}