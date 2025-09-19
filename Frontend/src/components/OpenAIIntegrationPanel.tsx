import React, { useState, useEffect } from 'react';
import { 
  PlayIcon, 
  CogIcon, 
  CheckCircleIcon, 
  ExclamationTriangleIcon, 
  XCircleIcon,
  BoltIcon,
  ChartBarIcon,
  ClockIcon,
  CurrencyDollarIcon
} from '@heroicons/react/24/outline';
import apiService from '../lib/api';

interface OpenAIModel {
  name: string;
  description: string;
  max_tokens: number;
  cost_per_1k_input: number;
  cost_per_1k_output: number;
  available_in_api?: boolean;
}

interface OpenAIModelsResponse {
  success: boolean;
  models: Record<string, OpenAIModel>;
  total_api_models?: number;
  error?: string;
  fallback?: boolean;
}

const OpenAIIntegrationPanel: React.FC = () => {
  const [connectionStatus, setConnectionStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [connectionMessage, setConnectionMessage] = useState<string>('');
  const [responseTime, setResponseTime] = useState<number | null>(null);
  const [models, setModels] = useState<Record<string, OpenAIModel>>({});
  const [modelsLoading, setModelsLoading] = useState(false);
  const [selectedModel, setSelectedModel] = useState('gpt-3.5-turbo');
  const [testMessage, setTestMessage] = useState('Hola, ¿cómo estás?');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationResult, setGenerationResult] = useState<any>(null);
  const [costEstimation, setCostEstimation] = useState<any>(null);

  useEffect(() => {
    loadModels();
  }, []);

  const loadModels = async () => {
    setModelsLoading(true);
    try {
      const response: OpenAIModelsResponse = await apiService.getOpenAIModels();
      if (response.success) {
        setModels(response.models);
      } else {
        console.error('Error loading models:', response.error);
      }
    } catch (error) {
      console.error('Error loading OpenAI models:', error);
    } finally {
      setModelsLoading(false);
    }
  };

  const testConnection = async () => {
    setConnectionStatus('testing');
    setConnectionMessage('Probando conexión...');
    
    try {
      const result = await apiService.testOpenAIConnection();
      
      if (result.success) {
        setConnectionStatus('success');
        setConnectionMessage(result.message);
        setResponseTime(result.response_time_ms);
      } else {
        setConnectionStatus('error');
        setConnectionMessage(result.error || 'Error desconocido');
        setResponseTime(null);
      }
    } catch (error) {
      setConnectionStatus('error');
      setConnectionMessage('Error de conexión');
      setResponseTime(null);
    }
  };

  const generateResponse = async () => {
    if (!testMessage.trim()) return;
    
    setIsGenerating(true);
    setGenerationResult(null);
    
    try {
      const messages = [
        { role: 'user', content: testMessage }
      ];
      
      const result = await apiService.generateOpenAIResponse({
        messages,
        model: selectedModel,
        temperature: 0.7,
        max_tokens: 512
      });
      
      setGenerationResult(result);
    } catch (error) {
      setGenerationResult({
        success: false,
        error: 'Error generating response'
      });
    } finally {
      setIsGenerating(false);
    }
  };

  const estimateCost = async () => {
    if (!testMessage.trim()) return;
    
    try {
      const result = await apiService.estimateOpenAICost(testMessage, selectedModel);
      setCostEstimation(result);
    } catch (error) {
      console.error('Error estimating cost:', error);
    }
  };

  const getStatusIcon = () => {
    switch (connectionStatus) {
      case 'testing':
        return <ClockIcon className="h-5 w-5 text-yellow-500 animate-spin" />;
      case 'success':
        return <CheckCircleIcon className="h-5 w-5 text-green-500" />;
      case 'error':
        return <XCircleIcon className="h-5 w-5 text-red-500" />;
      default:
        return <ExclamationTriangleIcon className="h-5 w-5 text-gray-400" />;
    }
  };

  const getStatusColor = () => {
    switch (connectionStatus) {
      case 'testing':
        return 'border-yellow-300 bg-yellow-50';
      case 'success':
        return 'border-green-300 bg-green-50';
      case 'error':
        return 'border-red-300 bg-red-50';
      default:
        return 'border-gray-300 bg-gray-50';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white shadow-md rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <BoltIcon className="h-8 w-8 text-green-600" />
            <div>
              <h2 className="text-2xl font-bold text-gray-900">OpenAI Integration</h2>
              <p className="text-gray-600">Integración completa con la API de OpenAI</p>
            </div>
          </div>
          <button
            onClick={testConnection}
            disabled={connectionStatus === 'testing'}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white px-4 py-2 rounded-lg flex items-center space-x-2 transition-colors duration-200"
          >
            <PlayIcon className="h-4 w-4" />
            <span>Probar Conexión</span>
          </button>
        </div>
      </div>

      {/* Connection Status */}
      <div className={`border-2 rounded-lg p-4 ${getStatusColor()}`}>
        <div className="flex items-center space-x-3">
          {getStatusIcon()}
          <div className="flex-1">
            <h3 className="font-semibold text-gray-900">Estado de Conexión</h3>
            <p className="text-gray-700">{connectionMessage}</p>
            {responseTime && (
              <p className="text-sm text-gray-600 mt-1">
                Tiempo de respuesta: {responseTime}ms
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Models Section */}
      <div className="bg-white shadow-md rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center space-x-2">
            <CogIcon className="h-5 w-5" />
            <span>Modelos Disponibles</span>
          </h3>
          <button
            onClick={loadModels}
            disabled={modelsLoading}
            className="text-blue-600 hover:text-blue-800 text-sm"
          >
            {modelsLoading ? 'Cargando...' : 'Actualizar'}
          </button>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Object.entries(models).map(([modelId, model]) => (
            <div
              key={modelId}
              className={`border rounded-lg p-4 cursor-pointer transition-all duration-200 ${ 
                selectedModel === modelId 
                  ? 'border-blue-500 bg-blue-50' 
                  : 'border-gray-200 hover:border-gray-300'
              }`}
              onClick={() => setSelectedModel(modelId)}
            >
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-medium text-gray-900">{model.name}</h4>
                {model.available_in_api !== false && (
                  <CheckCircleIcon className="h-4 w-4 text-green-500" />
                )}
              </div>
              <p className="text-sm text-gray-600 mb-3">{model.description}</p>
              <div className="space-y-1 text-xs text-gray-500">
                <div className="flex justify-between">
                  <span>Max tokens:</span>
                  <span>{model.max_tokens.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span>Input:</span>
                  <span>${model.cost_per_1k_input}/1k</span>
                </div>
                <div className="flex justify-between">
                  <span>Output:</span>
                  <span>${model.cost_per_1k_output}/1k</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Test Generation */}
      <div className="bg-white shadow-md rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center space-x-2">
          <BoltIcon className="h-5 w-5" />
          <span>Prueba de Generación</span>
        </h3>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Mensaje de Prueba
            </label>
            <textarea
              value={testMessage}
              onChange={(e) => setTestMessage(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              rows={3}
              placeholder="Escribe un mensaje para probar la generación..."
            />
          </div>
          
          <div className="flex items-center space-x-4">
            <button
              onClick={generateResponse}
              disabled={isGenerating || !testMessage.trim()}
              className="bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white px-4 py-2 rounded-lg flex items-center space-x-2"
            >
              <BoltIcon className="h-4 w-4" />
              <span>{isGenerating ? 'Generando...' : 'Generar Respuesta'}</span>
            </button>
            
            <button
              onClick={estimateCost}
              disabled={!testMessage.trim()}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-4 py-2 rounded-lg flex items-center space-x-2"
            >
              <CurrencyDollarIcon className="h-4 w-4" />
              <span>Estimar Costo</span>
            </button>
          </div>
          
          {/* Cost Estimation */}
          {costEstimation && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h4 className="font-medium text-blue-900 mb-2">Estimación de Costo</h4>
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <span className="text-blue-700">Tokens estimados:</span>
                  <p className="font-medium">{costEstimation.estimated_tokens}</p>
                </div>
                <div>
                  <span className="text-blue-700">Costo estimado:</span>
                  <p className="font-medium">${costEstimation.estimated_cost_usd}</p>
                </div>
                <div>
                  <span className="text-blue-700">Modelo:</span>
                  <p className="font-medium">{costEstimation.model}</p>
                </div>
              </div>
            </div>
          )}
          
          {/* Generation Result */}
          {generationResult && (
            <div className={`border rounded-lg p-4 ${
              generationResult.success ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'
            }`}>
              <h4 className={`font-medium mb-2 ${
                generationResult.success ? 'text-green-900' : 'text-red-900'
              }`}>
                {generationResult.success ? 'Respuesta Generada' : 'Error en Generación'}
              </h4>
              
              {generationResult.success ? (
                <div className="space-y-3">
                  <div className="bg-white border border-green-200 rounded p-3">
                    <p className="text-gray-900">{generationResult.content}</p>
                  </div>
                  
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <span className="text-green-700">Modelo:</span>
                      <p className="font-medium">{generationResult.model_used}</p>
                    </div>
                    <div>
                      <span className="text-green-700">Tokens:</span>
                      <p className="font-medium">{generationResult.usage?.total_tokens}</p>
                    </div>
                    <div>
                      <span className="text-green-700">Costo:</span>
                      <p className="font-medium">${generationResult.usage?.estimated_cost_usd}</p>
                    </div>
                    <div>
                      <span className="text-green-700">Tiempo:</span>
                      <p className="font-medium">{generationResult.response_time_ms}ms</p>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-red-700">{generationResult.error}</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default OpenAIIntegrationPanel;