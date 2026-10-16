import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  const apiUrl = process.env.SEI_AGENT_API_URL;
  const token = process.env.SEI_BRIDGE_TOKEN;
  if (!apiUrl || !token) {
    return NextResponse.json({error: 'O motor multiagente não está configurado no servidor.'}, {status: 503});
  }
  let message: unknown;
  try {
    const payload = await request.json();
    message = payload?.message;
  } catch {
    return NextResponse.json({error:'Pedido inválido.'}, {status:400});
  }
  if (typeof message !== 'string' || !message.trim() || message.length > 1200) {
    return NextResponse.json({error:'Escreva uma pergunta com até 1200 caracteres.'}, {status:400});
  }
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 45000);
    try {
      const endpoint = new URL('/chat', apiUrl);
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {'Content-Type':'application/json', Authorization: `Bearer ${token}`},
        body: JSON.stringify({message:message.trim()}),
        signal: controller.signal,
        cache: 'no-store',
      });
      if (!response.ok) return NextResponse.json({error:'O motor de análise não está disponível neste momento.'}, {status:502});
      const result = await response.json();
      if (typeof result.answer !== 'string') throw new Error('Resposta inválida');
      return NextResponse.json({answer: result.answer, agents: result.agents ?? [], sources: result.sources ?? []});
    } finally {
      clearTimeout(timer);
    }
  } catch {
    return NextResponse.json({error:'Não foi possível contactar o motor multiagente.'}, {status:502});
  }
}
