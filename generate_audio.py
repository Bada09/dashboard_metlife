"""
Script de Geração de Áudio Neural Gratuito (Estilo ElevenLabs / Azure Neural)
Gera arquivos de áudio .mp3 de alta fidelidade para as simulações da MetLife
utilizando as vozes neurais brasileiras (Francisca e Antonio).
"""

import os
import re
import json
import asyncio
import argparse
import edge_tts

FEMALE_NAMES = {
    'juliana', 'sabrina', 'ana', 'mariana', 'marina', 'patricia', 'beatriz',
    'carolina', 'fernanda', 'gabriela', 'larissa', 'vanessa', 'jessica',
    'amanda', 'aline', 'camila', 'daniela', 'debora', 'bruna', 'luana',
    'renata', 'tatiana', 'flavia', 'elaine', 'thais', 'leticia', 'carla'
}

def clean_phonetics(text):
    if not text:
        return ""
    t = text
    # Remove tags HTML se houver
    t = re.sub(r'<[^>]+>', '', t)
    # Ajustes fonéticos para pronúncia brasileira perfeita
    t = re.sub(r'\bR\$\s*(\d+)', r'\1 reais', t, flags=re.IGNORECASE)
    t = re.sub(r'\b(\d+)%', r'\1 por cento', t)
    t = re.sub(r'\bMetLife\b', 'Metlaife', t, flags=re.IGNORECASE)
    t = re.sub(r'\brhapsody\b', 'Rápsodi', t, flags=re.IGNORECASE)
    t = re.sub(r'\bIA\b', 'I.A.', t)
    t = re.sub(r'\bDr\.', 'Doutor', t, flags=re.IGNORECASE)
    t = re.sub(r'\bDra\.', 'Doutora', t, flags=re.IGNORECASE)
    t = re.sub(r'\bSr\.', 'Senhor', t, flags=re.IGNORECASE)
    t = re.sub(r'\bSra\.', 'Senhora', t, flags=re.IGNORECASE)
    return t.strip()

def detect_gender(name):
    first_name = name.split()[0].lower() if name else ""
    if first_name in FEMALE_NAMES or first_name.endswith('a'):
        return 'female'
    return 'male'

async def generate_message_audio(text, voice, out_path):
    if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
        return False  # Já existe
    communicate = edge_tts.Communicate(text, voice, rate="+0%", pitch="+0Hz")
    await communicate.save(out_path)
    return True

async def process_simulations(sim_indices=None, latest_count=None, finished_only=True):
    audio_dir = os.path.join(os.path.dirname(__file__), 'audio')
    os.makedirs(audio_dir, exist_ok=True)

    with open('metlife_simulations_data.js', 'r', encoding='utf-8') as f:
        content = f.read()

    m = re.search(r'const\s+RAW_SIMULATIONS\s*=\s*(\[.*\]);', content, re.DOTALL)
    if not m:
        print("Erro: Não foi possível carregar RAW_SIMULATIONS")
        return

    sims = json.loads(m.group(1))
    indexed_sims = list(enumerate(sims))

    if finished_only:
        indexed_sims = [(idx, s) for idx, s in indexed_sims if s.get('finished') and s.get('messages')]
    else:
        indexed_sims = [(idx, s) for idx, s in indexed_sims if s.get('messages')]

    if sim_indices:
        indexed_sims = [(idx, s) for idx, s in indexed_sims if idx in sim_indices]
    elif latest_count:
        # Pega as últimas N simulações
        indexed_sims = indexed_sims[-latest_count:]

    print(f"Iniciando geração para {len(indexed_sims)} simulações...")

    total_generated = 0
    total_skipped = 0

    for s_idx, (orig_idx, sim) in enumerate(indexed_sims):
        broker_name = sim.get('name', '')
        gender = detect_gender(broker_name)

        # Vozes: Corretor e Cliente/IA têm vozes opostas e complementares
        if gender == 'female':
            human_voice = 'pt-BR-FranciscaNeural'  # Voz feminina humana
            ai_voice = 'pt-BR-AntonioNeural'        # Voz masculina cliente/IA
        else:
            human_voice = 'pt-BR-AntonioNeural'    # Voz masculina humana
            ai_voice = 'pt-BR-FranciscaNeural'      # Voz feminina cliente/IA

        messages = sim.get('messages', [])
        print(f"[{s_idx + 1}/{len(indexed_sims)}] Simulação #{orig_idx} ({broker_name}) - {len(messages)} mensagens")

        for m_idx, msg in enumerate(messages):
            role = msg.get('role', 'HUMAN')
            text = clean_phonetics(msg.get('text', ''))
            if not text:
                continue

            voice = human_voice if role == 'HUMAN' else ai_voice
            out_file = os.path.join(audio_dir, f"sim_{orig_idx}_msg_{m_idx}.mp3")

            try:
                gen = await generate_message_audio(text, voice, out_file)
                if gen:
                    total_generated += 1
                else:
                    total_skipped += 1
            except Exception as e:
                print(f"  Erro ao gerar msg {m_idx}: {e}")
                await asyncio.sleep(1)

    print(f"\nConcluído! {total_generated} novos áudios gerados, {total_skipped} já existiam.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Gerador de Áudio Neural para o Dashboard MetLife")
    parser.add_argument('--latest', type=int, default=10, help="Número de simulações recentes para gerar (padrão: 10)")
    parser.add_argument('--all', action='store_true', help="Gerar para todas as simulações finalizadas")
    parser.add_argument('--sim', type=int, nargs='+', help="Índices específicos de simulações")
    args = parser.parse_args()

    if args.all:
        asyncio.run(process_simulations(latest_count=None))
    elif args.sim:
        asyncio.run(process_simulations(sim_indices=args.sim))
    else:
        asyncio.run(process_simulations(latest_count=args.latest))
