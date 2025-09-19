import { NextRequest, NextResponse } from 'next/server'

export async function GET() {
  return NextResponse.json({
    status: 'ok',
    app: 'admin-panel',
    chat_enabled: true,
    settings: {
      temperature: 0.7,
      max_tokens: 512,
      reason_after_messages: 10
    },
    prompts: {
      conversational: 'Responde de forma útil y breve.',
      reasoner: 'Piensa paso a paso antes de responder.',
      conversation: ''
    }
  })
}