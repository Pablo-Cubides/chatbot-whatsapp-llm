'use client'

import { useState, useEffect } from 'react'
import { apiService } from '@/lib/api'
import { Sidebar } from '@/components/Sidebar'
import { MainPage } from '@/components/pages/MainPage'
import { ConfigPage } from '@/components/pages/ConfigPage'
import { ContactsPage } from '@/components/pages/ContactsPage'
import { StatsPage } from '@/components/pages/StatsPage'
import { SettingsPage } from '@/components/pages/SettingsPage'
import toast from 'react-hot-toast'

type Page = 'main' | 'config' | 'contacts' | 'stats' | 'settings'

export default function Dashboard() {
  const [currentPage, setCurrentPage] = useState<Page>('main')
  const [systemStatus, setSystemStatus] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  // Verificar estado del sistema al cargar
  useEffect(() => {
    const checkSystemStatus = async () => {
      try {
        const status = await apiService.getSystemStatus()
        setSystemStatus(status)
      } catch (error: any) {
        console.error('Error al obtener estado del sistema:', error)
        // Establecer un estado por defecto si falla
        setSystemStatus({
          status: 'error',
          message: 'Backend no disponible'
        })
      } finally {
        setLoading(false)
      }
    }

    checkSystemStatus()
    
    // Actualizar estado cada 30 segundos
    const interval = setInterval(checkSystemStatus, 30000)
    return () => clearInterval(interval)
  }, [])

  const renderPage = () => {
    switch (currentPage) {
      case 'main':
        return <MainPage systemStatus={systemStatus} onStatusChange={setSystemStatus} />
      case 'config':
        return <ConfigPage />
      case 'contacts':
        return <ContactsPage />
      case 'stats':
        return <StatsPage />
      case 'settings':
        return <SettingsPage />
      default:
        return <MainPage systemStatus={systemStatus} onStatusChange={setSystemStatus} />
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-600">Conectando con el sistema...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <Sidebar 
        currentPage={currentPage} 
        onPageChange={setCurrentPage}
        systemStatus={systemStatus}
      />
      <main className="flex-1 p-6 overflow-auto">
        {renderPage()}
      </main>
    </div>
  )
}
