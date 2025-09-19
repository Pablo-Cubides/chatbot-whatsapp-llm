#!/usr/bin/env node

const { execSync } = require('child_process');
const path = require('path');

console.log('🚀 Iniciando el servidor de desarrollo...\n');

try {
  // Check if we're in the Frontend directory
  const currentDir = process.cwd();
  const frontendPath = path.join(currentDir, 'Frontend');
  
  // If we're not in Frontend directory, try to change to it
  if (!currentDir.endsWith('Frontend')) {
    if (require('fs').existsSync(frontendPath)) {
      process.chdir(frontendPath);
      console.log('📁 Cambiando al directorio Frontend...');
    } else {
      console.error('❌ No se encontró el directorio Frontend');
      process.exit(1);
    }
  }

  // Install dependencies if node_modules doesn't exist
  if (!require('fs').existsSync('node_modules')) {
    console.log('📦 Instalando dependencias...');
    execSync('npm install', { stdio: 'inherit' });
  }

  // Start the development server
  console.log('🔥 Iniciando servidor Next.js...');
  execSync('npm run dev', { stdio: 'inherit' });

} catch (error) {
  console.error('❌ Error al iniciar el servidor:', error.message);
  console.log('\n💡 Soluciones posibles:');
  console.log('1. Ejecutar desde el directorio del proyecto');
  console.log('2. Verificar que Node.js esté instalado');
  console.log('3. Ejecutar "npm install" manualmente');
  process.exit(1);
}