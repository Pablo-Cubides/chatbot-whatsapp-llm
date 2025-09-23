import axios, { AxiosInstance } from 'axios'

class ApiService {
  private api: AxiosInstance

  constructor() {
    this.api = axios.create({
      baseURL: 'http://127.0.0.1:8014',
      timeout: 10000, // Reducido de 30000 a 10000ms
      headers: {
        'Content-Type': 'application/json',
        // 'Authorization': 'Bearer admintoken', // TODO: Handle authentication dynamically (e.g., from login response)
      },
    })

    // Interceptor para requests
    this.api.interceptors.request.use(
      (config) => {
        config.headers.Authorization = 'Bearer admintoken'
        return config
      },
      (error) => {
        return Promise.reject(error)
      }
    )

    // Interceptor para responses
    this.api.interceptors.response.use(
      (response) => response,
      (error) => {
        console.error('API Error:', error)
        return Promise.reject(error)
      }
    )
  }

  private handleError(error: any): never {
    const message = error.response?.data?.detail || error.response?.data?.error || error.message || 'Error desconocido'
    throw new Error(message)
  }

  // =========================
  // SISTEMA Y ESTADO
  // =========================

  async getSystemStatus(): Promise<any> {
    try {
      const response = await this.api.get('/api/status')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  // =========================
  // CONFIGURACIÓN
  // =========================

  async getSettings(): Promise<any> {
    try {
      const response = await this.api.get('/api/settings')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async saveSettings(settings: any): Promise<any> {
    try {
      const response = await this.api.post('/api/settings', settings)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  // =========================
  // PROMPTS
  // =========================

  async getPrompts(): Promise<any> {
    try {
      const response = await this.api.get('/api/prompts')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async savePrompts(prompts: any): Promise<any> {
    try {
      const response = await this.api.post('/api/prompts', prompts)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  // =========================
  // ARCHIVOS DE CONFIGURACIÓN
  // =========================

  async getFile(fileName: string): Promise<any> {
    try {
      const response = await this.api.get(`/api/files/${fileName}`)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async getDocsContent(): Promise<any> {
    try {
      // Usar el nuevo endpoint que obtiene todo el contenido de una vez
      const response = await this.api.get('/api/docs-content')
      return response.data
    } catch (error: any) {
      console.warn('Could not load docs content:', error)
      return null
    }
  }

  async saveFile(fileName: string, content: string): Promise<any> {
    try {
      const response = await this.api.post(`/api/files/${fileName}`, { content })
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  // =========================
  // CONTACTOS PERMITIDOS
  // =========================

  async getAllowedContacts(): Promise<any> {
    try {
      const response = await this.api.get('/api/allowed-contacts')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async addAllowedContact(contact: { chat_id: string; perfil?: string; context?: string; objective?: string }): Promise<any> {
    try {
      const response = await this.api.post('/api/allowed-contacts', contact)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async removeAllowedContact(chatId: string): Promise<any> {
    try {
      const response = await this.api.delete(`/api/allowed-contacts/${chatId}`)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async updateAllowedContact(chatId: string, contact: { perfil?: string; context?: string; objective?: string }): Promise<any> {
    try {
      const response = await this.api.put(`/api/allowed-contacts/${chatId}`, contact)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  // =========================
  // GESTIÓN DE CHATS
  // =========================

  async getChatData(chatId: string): Promise<any> {
    try {
      const response = await this.api.get(`/api/chats/${chatId}`)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async saveChatData(chatId: string, data: { perfil?: string; context?: string; objective?: string }): Promise<any> {
    try {
      const response = await this.api.post(`/api/chats/${chatId}`, data)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async refreshChatContext(chatId: string): Promise<any> {
    try {
      const response = await this.api.post(`/api/chats/${chatId}/refresh-context`)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  // =========================
  // LM STUDIO MODELS
  // =========================

  async getLMStudioModels(): Promise<any> {
    try {
      const response = await this.api.get('/api/lmstudio/models')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async getLocalOnlyModels(): Promise<any> {
    try {
      const response = await this.api.get('/api/lmstudio/models/local-only')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async startLMStudio(): Promise<any> {
    try {
      const response = await this.api.post('/api/lmstudio/start')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async startLMStudioServer(): Promise<any> {
    try {
      const response = await this.api.post('/api/lmstudio/server/start')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async stopLMStudioServer(): Promise<any> {
    try {
      const response = await this.api.post('/api/lmstudio/server/stop')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async loadLMStudioModel(model: string): Promise<any> {
    try {
      const response = await this.api.post('/api/lmstudio/load', { model })
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  // =========================
  // GESTIÓN DE MODELOS
  // =========================

  async getCurrentModel(): Promise<any> {
    try {
      const response = await this.api.get('/api/current-model')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async setCurrentModel(model: string): Promise<any> {
    try {
      const response = await this.api.post('/api/current-model', { model })
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async getReasonerModel(): Promise<any> {
    try {
      const response = await this.api.get('/api/reasoner-model')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async setReasonerModel(model: string): Promise<any> {
    try {
      const response = await this.api.post('/api/reasoner-model', { model })
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  // =========================
  // WHATSAPP
  // =========================

  async getWhatsAppStatus(): Promise<any> {
    try {
      const response = await this.api.get('/api/whatsapp/status')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async startWhatsApp(): Promise<any> {
    try {
      const response = await this.api.post('/api/whatsapp/start')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async stopWhatsApp(): Promise<any> {
    try {
      const response = await this.api.post('/api/whatsapp/stop')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async sendWhatsAppMessage(chatId: string, message: string): Promise<any> {
    try {
      const response = await this.api.post('/api/whatsapp/send', { chat_id: chatId, message })
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  // =========================
  // SISTEMA
  // =========================

  async stopAllServices(): Promise<any> {
    try {
      const response = await this.api.post('/api/system/stop-all')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  // =========================
  // ANALÍTICAS
  // =========================

  async getAnalytics(): Promise<any> {
    try {
      const response = await this.api.get('/api/analytics')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async getEvents(): Promise<any> {
    try {
      const response = await this.api.get('/api/events')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  // =========================
  // MULTIMEDIA
  // =========================

  async uploadMedia(file: File): Promise<any> {
    try {
      const formData = new FormData()
      formData.append('file', file)
      
      const response = await this.api.post('/api/media/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async listMedia(): Promise<any> {
    try {
      const response = await this.api.get('/api/media/list')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async deleteMedia(mediaType: string, filename: string): Promise<any> {
    try {
      const response = await this.api.delete(`/api/media/${mediaType}/${filename}`)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async sendMediaMessage(chatId: string, message: string, mediaType: string, filename: string): Promise<any> {
    try {
      const formData = new FormData()
      formData.append('chat_id', chatId)
      formData.append('message', message)
      formData.append('media_type', mediaType)
      formData.append('filename', filename)
      
      const response = await this.api.post('/api/whatsapp/send-media', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  // =========================
  // CONVERSACIONES
  // =========================

  async clearConversation(chatId: string): Promise<any> {
    try {
      const response = await this.api.post('/api/conversations/clear', { chat_id: chatId })
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  // =========================
  // CONTACTOS PARA MENSAJERÍA
  // =========================

  async getContacts(): Promise<any> {
    try {
      const response = await this.api.get('/api/contacts')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async composeMessage(contactId: string, objective: string, context?: string): Promise<any> {
    try {
      const response = await this.api.post('/api/chat/compose', { contact_id: contactId, objective, context })
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  // =========================
  // MODELOS ONLINE
  // =========================

  async getOnlineModels(): Promise<any> {
    try {
      const response = await this.api.get('/api/models/online')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async saveOnlineModel(modelData: any): Promise<any> {
    try {
      const response = await this.api.post('/api/models/online', modelData)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async deleteOnlineModel(modelId: string): Promise<any> {
    try {
      const response = await this.api.delete(`/api/models/online/${modelId}`)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async getAvailableOnlineModels(): Promise<any> {
    try {
      const response = await this.api.get('/api/models/online/available')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  // =========================
  // APIS ONLINE
  // =========================

  async getOnlineApisConfig(): Promise<any> {
    try {
      const response = await this.api.get('/api/online-apis/config')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async saveOnlineApisConfig(config: any): Promise<any> {
    try {
      const response = await this.api.post('/api/online-apis/config', config)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async testOnlineApi(provider: string): Promise<any> {
    try {
      const response = await this.api.post(`/api/online-apis/test/${provider}`)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async getOnlineApiModels(provider: string): Promise<any> {
    try {
      const response = await this.api.get(`/api/online-apis/models/${provider}`)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  // =========================
  // MÉTODOS DE UTILIDAD
  // =========================

  async checkConnection(): Promise<boolean> {
    try {
      await this.getSystemStatus()
      return true
    } catch {
      return false
    }
  }

  // =========================
  // SECURE API MANAGEMENT
  // =========================

  async listSecureApis(): Promise<any> {
    try {
      const response = await this.api.get('/api/secure-apis/list')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async storeSecureApi(provider: string, apiKey: string, metadata?: any): Promise<any> {
    try {
      const response = await this.api.post('/api/secure-apis/store', {
        provider,
        api_key: apiKey,
        metadata
      })
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async getSecureApiKey(provider: string, showKey: boolean = false): Promise<any> {
    try {
      const response = await this.api.get(`/api/secure-apis/key/${provider}?show_key=${showKey}`)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async testSecureApi(provider: string): Promise<any> {
    try {
      const response = await this.api.post(`/api/secure-apis/test/${provider}`)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async removeSecureApi(provider: string): Promise<any> {
    try {
      const response = await this.api.delete(`/api/secure-apis/remove/${provider}`)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async getProviderInfo(provider: string): Promise<any> {
    try {
      const response = await this.api.get(`/api/secure-apis/provider-info/${provider}`)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  // =========================
  // OPENAI INTEGRATION
  // =========================

  async getOpenAIModels(): Promise<any> {
    try {
      const response = await this.api.get('/api/openai/models')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async testOpenAIConnection(): Promise<any> {
    try {
      const response = await this.api.post('/api/openai/test-connection')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async generateOpenAIResponse(data: {
    messages: any[];
    model?: string;
    temperature?: number;
    max_tokens?: number;
  }): Promise<any> {
    try {
      const response = await this.api.post('/api/openai/generate', data)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async estimateOpenAICost(text: string, model?: string): Promise<any> {
    try {
      const response = await this.api.post('/api/openai/estimate-cost', { text, model })
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async getOpenAIUsageStats(): Promise<any> {
    try {
      const response = await this.api.get('/api/openai/usage-stats')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  // =========================
  // CLAUDE INTEGRATION
  // =========================

  async getClaudeModels(): Promise<any> {
    try {
      const response = await this.api.get('/api/claude/models')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async testClaudeConnection(): Promise<any> {
    try {
      const response = await this.api.post('/api/claude/test-connection')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async generateClaudeResponse(data: {
    messages: any[];
    model?: string;
    temperature?: number;
    max_tokens?: number;
  }): Promise<any> {
    try {
      const response = await this.api.post('/api/claude/generate', data)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async estimateClaudeCost(text: string, model?: string): Promise<any> {
    try {
      const response = await this.api.post('/api/claude/estimate-cost', { text, model })
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async getClaudeUsageStats(): Promise<any> {
    try {
      const response = await this.api.get('/api/claude/usage-stats')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  // =========================
  // GEMINI INTEGRATION
  // =========================

  async getGeminiModels(): Promise<any> {
    try {
      const response = await this.api.get('/api/gemini/models')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async testGeminiConnection(): Promise<any> {
    try {
      const response = await this.api.post('/api/gemini/test-connection')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async generateGeminiResponse(data: {
    messages: any[];
    model?: string;
    temperature?: number;
    max_tokens?: number;
  }): Promise<any> {
    try {
      const response = await this.api.post('/api/gemini/generate', data)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async estimateGeminiCost(text: string, model?: string): Promise<any> {
    try {
      const response = await this.api.post('/api/gemini/estimate-cost', { text, model })
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async getGeminiUsageStats(): Promise<any> {
    try {
      const response = await this.api.get('/api/gemini/usage-stats')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  // =========================
  // X.AI GROK INTEGRATION
  // =========================

  async getXAIModels(): Promise<any> {
    try {
      const response = await this.api.get('/api/xai/models')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async testXAIConnection(): Promise<any> {
    try {
      const response = await this.api.post('/api/xai/test-connection')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async generateXAIResponse(data: {
    messages: any[];
    model?: string;
    temperature?: number;
    max_tokens?: number;
  }): Promise<any> {
    try {
      const response = await this.api.post('/api/xai/generate', data)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async estimateXAICost(text: string, model?: string): Promise<any> {
    try {
      const response = await this.api.post('/api/xai/estimate-cost', { text, model })
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async getXAIUsageStats(): Promise<any> {
    try {
      const response = await this.api.get('/api/xai/usage-stats')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async getXAIRateLimits(): Promise<any> {
    try {
      const response = await this.api.get('/api/xai/rate-limits')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  // =========================
  // OLLAMA LOCAL MODELS
  // =========================

  async getOllamaModels(): Promise<any> {
    try {
      const response = await this.api.get('/api/ollama/models')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async testOllamaConnection(): Promise<any> {
    try {
      const response = await this.api.post('/api/ollama/test-connection')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async generateOllamaResponse(data: {
    messages: any[];
    model?: string;
    temperature?: number;
    max_tokens?: number;
  }): Promise<any> {
    try {
      const response = await this.api.post('/api/ollama/generate', data)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async pullOllamaModel(modelName: string): Promise<any> {
    try {
      const response = await this.api.post('/api/ollama/pull-model', { model_name: modelName })
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async deleteOllamaModel(modelName: string): Promise<any> {
    try {
      const response = await this.api.delete('/api/ollama/delete-model', { data: { model_name: modelName } })
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async estimateOllamaCost(text: string, model?: string): Promise<any> {
    try {
      const response = await this.api.post('/api/ollama/estimate-cost', { text, model })
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async getOllamaUsageStats(): Promise<any> {
    try {
      const response = await this.api.get('/api/ollama/usage-stats')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async getOllamaSystemInfo(): Promise<any> {
    try {
      const response = await this.api.get('/api/ollama/system-info')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  // =========================
  // SERVER LOCATIONS MANAGEMENT
  // =========================

  async getServerLocationsStatus(): Promise<any> {
    try {
      const response = await this.api.get('/api/server-locations/status')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async getProviderLocations(provider: string): Promise<any> {
    try {
      const response = await this.api.get(`/api/server-locations/${provider}`)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async forceHealthCheck(provider: string): Promise<any> {
    try {
      const response = await this.api.post(`/api/server-locations/${provider}/health-check`)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async addCustomLocation(provider: string, locationConfig: {
    id?: string;
    name: string;
    region: string;
    base_url: string;
    priority?: number;
  }): Promise<any> {
    try {
      const response = await this.api.post(`/api/server-locations/${provider}/add`, locationConfig)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async removeLocation(provider: string, locationId: string): Promise<any> {
    try {
      const response = await this.api.delete(`/api/server-locations/${provider}/${locationId}`)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async getBestLocation(provider: string): Promise<any> {
    try {
      const response = await this.api.get(`/api/server-locations/${provider}/best`)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async exportLocationsConfig(): Promise<any> {
    try {
      const response = await this.api.get('/api/server-locations/export')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async importLocationsConfig(configuration: any): Promise<any> {
    try {
      const response = await this.api.post('/api/server-locations/import', { configuration })
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  // =========================
  // STATUS MONITORING
  // =========================

  async getRealTimeStatus(): Promise<any> {
    try {
      const response = await this.api.get('/api/status/real-time')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async forceStatusUpdate(): Promise<any> {
    try {
      const response = await this.api.post('/api/status/force-update')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async getServiceStatus(serviceName: string): Promise<any> {
    try {
      const response = await this.api.get(`/api/status/service/${serviceName}`)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async getServiceTrends(serviceName: string, hours: number = 24): Promise<any> {
    try {
      const response = await this.api.get(`/api/status/trends/${serviceName}?hours=${hours}`)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async getAllRecommendations(): Promise<any> {
    try {
      const response = await this.api.get('/api/status/recommendations')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async startStatusMonitoring(): Promise<any> {
    try {
      const response = await this.api.post('/api/status/monitoring/start')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async stopStatusMonitoring(): Promise<any> {
    try {
      const response = await this.api.post('/api/status/monitoring/stop')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  // =========================
  // GESTIÓN DE COSTOS
  // =========================

  async getCostDashboard(period: string = 'daily'): Promise<any> {
    try {
      const response = await this.api.get(`/api/cost/dashboard?period=${period}`)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async createBudgetLimit(budget: {
    name: string
    limit_type: string
    amount_usd: number
    alert_threshold_percent?: number
    services?: string[]
  }): Promise<any> {
    try {
      const response = await this.api.post('/api/cost/budget', budget)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async trackUsage(usage: {
    service: string
    model: string
    input_tokens: number
    output_tokens: number
    user_id?: string
    conversation_id?: string
    session_id?: string
    metadata?: Record<string, any>
  }): Promise<any> {
    try {
      const response = await this.api.post('/api/cost/track', usage)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async getCostStats(period: string = 'daily', service?: string): Promise<any> {
    try {
      const params = new URLSearchParams({ period })
      if (service) params.append('service', service)
      const response = await this.api.get(`/api/cost/stats?${params}`)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async getBudgets(): Promise<any> {
    try {
      const response = await this.api.get('/api/cost/budgets')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async getCostAlerts(acknowledged?: boolean): Promise<any> {
    try {
      const params = acknowledged !== undefined ? `?acknowledged=${acknowledged}` : ''
      const response = await this.api.get(`/api/cost/alerts${params}`)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async acknowledgeAlert(alertId: number): Promise<any> {
    try {
      const response = await this.api.post(`/api/cost/alerts/${alertId}/acknowledge`)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async deleteBudget(budgetId: number): Promise<any> {
    try {
      const response = await this.api.delete(`/api/cost/budgets/${budgetId}`)
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async startCostMonitoring(): Promise<any> {
    try {
      const response = await this.api.post('/api/cost/monitoring/start')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }

  async stopCostMonitoring(): Promise<any> {
    try {
      const response = await this.api.post('/api/cost/monitoring/stop')
      return response.data
    } catch (error: any) {
      this.handleError(error)
    }
  }
}

export const apiService = new ApiService()
export default apiService