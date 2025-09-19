'use client'

import { createContext, useContext, useEffect, useState } from 'react'
import { io, Socket } from 'socket.io-client'

interface AppContextType {
  socket: Socket | null
  isConnected: boolean
  systemStatus: 'online' | 'offline' | 'maintenance'
}

const AppContext = createContext<AppContextType | undefined>(undefined)

export function Providers({ children }: { children: React.ReactNode }) {
  const [socket, setSocket] = useState<Socket | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [systemStatus, setSystemStatus] = useState<'online' | 'offline' | 'maintenance'>('offline')

  useEffect(() => {
    // Temporalmente desactivado - nuestro backend no tiene WebSocket
    console.log('WebSocket connection disabled for debugging')
    setSystemStatus('online')
    setIsConnected(true)
    
    // const socketUrl = process.env.NEXT_PUBLIC_WEBSOCKET_URL || 'ws://localhost:8003'
    // const newSocket = io(socketUrl, {
    //   transports: ['websocket', 'polling'],
    // })

    // newSocket.on('connect', () => {
    //   setIsConnected(true)
    //   setSystemStatus('online')
    // })

    // newSocket.on('disconnect', () => {
    //   setIsConnected(false)
    //   setSystemStatus('offline')
    // })

    // newSocket.on('system_status', (status) => {
    //   setSystemStatus(status)
    // })

    // setSocket(newSocket)

    // return () => {
    //   newSocket.close()
    // }
  }, [])

  return (
    <AppContext.Provider value={{ socket, isConnected, systemStatus }}>
      {children}
    </AppContext.Provider>
  )
}

export function useApp() {
  const context = useContext(AppContext)
  if (context === undefined) {
    throw new Error('useApp must be used within a Providers component')
  }
  return context
}