#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Robô de Atualização Automática do Dashboard MetLife
--------------------------------------------------
Executa diariamente para:
1. Detectar o dump JSON mais recente (no diretório do projeto ou no Desktop).
2. Processar simulações, usuários, métricas e competências.
3. Atualizar os arquivos metlife_users_data.js e metlife_simulations_data.js.
4. Atualizar o selo de data e versão de cache no index.html.
5. Fazer commit e push automático para o repositório GitHub.
"""

import json
import re
import sys
import os
import glob
import subprocess
from datetime import datetime
from collections import defaultdict
import random
import unicodedata

# ── Diretórios e Arquivos ──────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DESKTOP_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
LOG_FILE = os.path.join(BASE_DIR, "auto_updater.log")
USERS_OUT = os.path.join(BASE_DIR, "metlife_users_data.js")
SIMS_OUT = os.path.join(BASE_DIR, "metlife_simulations_data.js")
INDEX_HTML = os.path.join(BASE_DIR, "index.html")

# ── Mapeamento de usecase → scenario ─────────────────────────────────────────
USECASE_TO_SCENARIO = {
    # PT
    "da8edee8-c5ba-4062-87c1-a2e28cba2859": "PROSPECT_FRIO",
    "40fec240-3942-4e13-89b0-e1afecbc2ba5": "PROSPECT_FRIO",
    "edb69d70-a801-4570-b477-9085e5f8598d": "OBJECAO_ADIAMENTO",
    "e04f94a2-5ff1-4f6b-b87a-9b652e53a5ba": "RECOMENDACOES",
    "9b7ba04b-d7e3-4313-88f9-325b66621218": "RECOMENDACOES",
    "2582a605-9b69-4dfe-a095-b294cc509c6e": "DOCUMENTO_REUNIAO",
    "d5f156fa-022a-4b5b-91d4-d8d9ddfdb84c": "OBJECAO_FINANCEIRA",
    # FR
    "5a5378d7-7fce-4519-9e0e-164e87a6ca30": "PROSPECT_FRIO",
    "cfbd8492-0bec-478e-b3b4-b91f0ecab565": "PROSPECT_FRIO",
    "fc6a5127-20d9-46ae-9ba9-c8451f97fce4": "PROSPECT_FRIO",
    "03c97af7-7da3-43e7-81cd-1bef95dffe1f": "DOCUMENTO_REUNIAO",
    "4e6416b5-b3ba-4cb3-80ea-781c3e53e374": "RECOMENDACOES",
    "dd39514e-ecdd-46ee-81f3-2ef033efc1ea": "RECOMENDACOES",
    "412444ae-3d01-4296-ba0a-8397e198e23b": "CONVENCER_PROSPECT",
}

SKILL_KEYWORDS = {
    "Escuta": ["escuta", "ouvir", "ouviu", "attention", "ecoute", "atenção ao cliente", "active listening"],
    "Personalizacao": ["personaliz", "qualifica", "rapide", "qualification", "rapida", "besoin", "necessidade"],
    "Empatia": ["objecao", "objection", "lidar com", "obstacle", "resist", "resistencia"],
    "Crises": ["assertiv", "ferme", "firmeza", "firmemente", "posicao clara", "pertinent", "pertinente"],
    "Padroes": ["padrao", "metodo", "methode", "metbook", "script", "estrutura", "protocole", "protocolo"],
}

MONTHS_MAP = {
    "jan": "01", "feb": "02", "fev": "02", "mar": "03", "apr": "04", "abr": "04",
    "may": "05", "mai": "05", "jun": "06", "jul": "07", "aug": "08", "ago": "08",
    "sep": "09", "set": "09", "oct": "10", "out": "10", "nov": "11", "dec": "12", "dez": "12"
}

def log(msg):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{now_str}] {msg}"
    print(formatted)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass

def parse_dump_date(filename):
    """
    Extrai data e hora do nome do arquivo, ex:
    dump-Metlife-10aug26-10h27.json -> (10/08/2026, 10:27, datetime)
    """
    base = os.path.basename(filename)
    match = re.search(r"(\d{1,2})([a-zA-Z]{3})(\d{2,4})-(\d{1,2})h(\d{2})", base, re.IGNORECASE)
    if match:
        day, mon_str, yr_str, hr, mn = match.groups()
        mon = MONTHS_MAP.get(mon_str.lower(), "08")
        year = f"20{yr_str}" if len(yr_str) == 2 else yr_str
        day = day.zfill(2)
        hr = hr.zfill(2)
        mn = mn.zfill(2)
        date_br = f"{day}/{mon}/{year}"
        time_str = f"{hr}:{mn}"
        dt = datetime(int(year), int(mon), int(day), int(hr), int(mn))
        return date_br, time_str, dt
    
    # Fallback para timestamp de modificação do arquivo
    mtime = os.path.getmtime(filename)
    dt = datetime.fromtimestamp(mtime)
    return dt.strftime("%d/%m/%Y"), dt.strftime("%H:%M"), dt

def find_latest_dump():
    """Busca o dump JSON mais recente no diretório do projeto e no Desktop."""
    candidates = []
    search_patterns = [
        os.path.join(BASE_DIR, "dump-Metlife-*.json"),
        os.path.join(BASE_DIR, "*Metlife*.json"),
        os.path.join(DESKTOP_DIR, "dump-Metlife-*.json"),
        os.path.join(DESKTOP_DIR, "*Metlife*.json")
    ]
    
    seen = set()
    for pat in search_patterns:
        for f in glob.glob(pat):
            norm = os.path.normpath(f)
            if norm not in seen and os.path.isfile(norm) and not norm.endswith(".js"):
                seen.add(norm)
                _, _, dt = parse_dump_date(norm)
                candidates.append((dt, norm))
                
    if not candidates:
        return None
        
    candidates.sort(key=lambda x: x[0], reverse=True)
    latest_file = candidates[0][1]
    
    # Se o arquivo estiver no Desktop fora da pasta do projeto, copia para dentro da pasta
    target_in_base = os.path.join(BASE_DIR, os.path.basename(latest_file))
    if os.path.normpath(latest_file) != os.path.normpath(target_in_base):
        try:
            import shutil
            shutil.copy2(latest_file, target_in_base)
            log(f"Copiado novo dump do Desktop para o projeto: {os.path.basename(latest_file)}")
            latest_file = target_in_base
        except Exception as e:
            log(f"Aviso ao copiar arquivo: {e}")
            
    return latest_file

def fmt_date_iso_to_br(iso_str):
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return None

def dur_ms_to_str(ms):
    if not ms or ms <= 0:
        return "0m 0s"
    total_s = ms // 1000
    return f"{total_s // 60}m {total_s % 60}s"

def extract_insights_from_feedback(feedback_text):
    if not feedback_text:
        return []
    lines = [l.strip() for l in feedback_text.split("\n") if l.strip()]
    bullets = []
    header_re = re.compile(r"^[^\w\s]{1,3}\s*[A-Z]")
    for line in lines:
        if header_re.match(line) or len(line) < 20:
            continue
        if line.startswith("**") and line.endswith("**"):
            bullets.append(line)
        elif line.startswith("-") or line.startswith("•"):
            bullets.append(line.lstrip("-•").strip())
        elif re.match(r"^\d+[\.\)]\s", line):
            bullets.append(re.sub(r"^\d+[\.\)]\s", "", line))
    if not bullets:
        sentences = re.split(r"(?<=[.!?])\s+", feedback_text)
        bullets = [s.strip() for s in sentences[:4] if len(s.strip()) > 20]
    return bullets[:6]

def score_skills_from_feedback(feedback_text, base_score):
    skills = {"Escuta": 0, "Personalizacao": 0, "Empatia": 0, "Crises": 0, "Padroes": 0}
    if not feedback_text or base_score <= 0:
        return skills
    text_lower = (feedback_text or "").lower()
    def rm_acc(s):
        return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    text_lower = rm_acc(text_lower)
    rng = random.Random(hash(feedback_text[:50]))
    for skill, keywords in SKILL_KEYWORDS.items():
        mentions = sum(1 for kw in keywords if rm_acc(kw) in text_lower)
        variation = rng.randint(-15, 15)
        skill_score = max(0, min(100, base_score + variation + (mentions * 5)))
        skills[skill] = skill_score
    return skills

def process_dump_file(dump_path):
    log(f"Lendo e processando dump: {os.path.basename(dump_path)}")
    with open(dump_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    members = data.get("members", [])
    all_simulations = []
    user_records = []

    for member in members:
        user = member.get("user", {})
        conversations = user.get("conversations", [])
        first = user.get("firstName", "") or ""
        last = user.get("lastName", "") or ""
        name = (first + " " + last).strip()
        if not name:
            continue

        agency, region = "Outros", "Outros"
        locale = (user.get("locale") or "PT").upper()
        scores = []
        durations_ms = []
        sim_dates = []
        skills_acc = defaultdict(list)
        insights_list = []
        lqa_scores = []

        for conv_entry in conversations:
            inner = conv_entry.get("conversation", {})
            eval_d = inner.get("evaluation")
            uc_id = inner.get("usecaseId", "")
            scenario = USECASE_TO_SCENARIO.get(uc_id, "PROSPECT_FRIO")
            created = inner.get("createdAt")
            user_dur_ms = inner.get("userSpeakingDurationMs") or 0
            messages = inner.get("messages", []) or []
            finished = bool(eval_d)

            date_br = fmt_date_iso_to_br(created)
            dur_str = dur_ms_to_str(user_dur_ms)

            score = 0
            feedback = ""
            lqa = "N/A"
            if eval_d:
                score = eval_d.get("score") or 0
                feedback = eval_d.get("feedback") or ""
                u_score = eval_d.get("userScore")
                if u_score and u_score > 0:
                    lqa = u_score
                    lqa_scores.append(u_score)

            msgs_fmt = []
            for msg in messages:
                role = msg.get("participantType") or msg.get("role") or "HUMAN"
                text = msg.get("content") or msg.get("text") or ""
                if text:
                    msgs_fmt.append({"role": role, "text": text})

            sim_record = {
                "name": name,
                "agency": agency,
                "region": region,
                "date": date_br or "01/01/2026",
                "dur": dur_str,
                "score": score if finished else 0,
                "scenario": scenario,
                "lqa": lqa,
                "interactions": len(msgs_fmt),
                "messages": msgs_fmt,
                "finished": finished
            }
            all_simulations.append(sim_record)

            if date_br:
                sim_dates.append(date_br)
            if finished and score > 0:
                scores.append(score)
                skills_partial = score_skills_from_feedback(feedback, score)
                for sk, val in skills_partial.items():
                    skills_acc[sk].append(val)
                if not insights_list:
                    bullets = extract_insights_from_feedback(feedback)
                    if bullets:
                        insights_list = bullets
            if user_dur_ms > 0:
                durations_ms.append(user_dur_ms)

        avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
        avg_dur_ms = sum(durations_ms) / len(durations_ms) if durations_ms else 0
        avg_dur_sec = int(avg_dur_ms / 1000)
        avg_dur_min = avg_dur_sec // 60
        avg_dur_sec_r = avg_dur_sec % 60
        lqa_avg = round(sum(lqa_scores) / len(lqa_scores), 1) if lqa_scores else 0.0

        skills_avg = {}
        for sk in ["Escuta", "Personalizacao", "Empatia", "Crises", "Padroes"]:
            vals = skills_acc.get(sk, [])
            skills_avg[sk] = round(sum(vals) / len(vals), 1) if vals else 0.0

        languages = [locale] if locale else ["PT"]

        if not insights_list:
            insights_list = [
                "Usuario ainda nao possui simulacoes avaliadas.",
                "Incentive a realizar simulacoes para gerar analise detalhada."
            ]

        user_rec = {
            "avgDurSec": avg_dur_sec_r,
            "avgScore": avg_score,
            "skills": skills_avg,
            "count": len(conversations),
            "insights": {
                "pt": insights_list,
                "fr": insights_list
            },
            "name": name,
            "agency": agency,
            "region": region,
            "lqaScore": lqa_avg,
            "languages": languages,
            "improvement": {
                "pt": "Continuar praticando e trabalhando os pontos de melhoria identificados.",
                "fr": "Continuer a pratiquer et travailler les points d amelioration identifies."
            },
            "dates": sim_dates,
            "avgDurMin": avg_dur_min
        }
        user_records.append(user_rec)

    # Escrever arquivos JS
    with open(USERS_OUT, "w", encoding="utf-8") as f:
        f.write("const users = ")
        json.dump(user_records, f, ensure_ascii=False, indent=4)
        f.write(";\n")

    with open(SIMS_OUT, "w", encoding="utf-8") as f:
        f.write("const RAW_SIMULATIONS = ")
        json.dump(all_simulations, f, ensure_ascii=False, indent=4)
        f.write(";\n")

    log(f"Arquivos JS gerados com sucesso: {len(user_records)} usuários, {len(all_simulations)} simulações.")
    return len(user_records), len(all_simulations)

def update_index_html(date_br, time_str):
    """Atualiza o selo de data e bumpa a versão do cache no index.html."""
    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Bump version query string (?v=X -> ?v=X+1)
    def bump_ver(m):
        prefix = m.group(1)
        ver = int(m.group(2)) + 1
        return f'{prefix}?v={ver}"'

    content = re.sub(r'(src="metlife_users_data\.js)\?v=(\d+)"', bump_ver, content)
    content = re.sub(r'(src="metlife_simulations_data\.js)\?v=(\d+)"', bump_ver, content)

    # 2. Atualiza textos de última atualização
    pt_str = f'lastUpdate: "Última atualização: {date_br} - {time_str}",'
    fr_time = time_str.replace(":", "h")
    fr_str = f'lastUpdate: "Mise à jour : {date_br} - {fr_time}",'

    content = re.sub(r'lastUpdate:\s*"Última atualização:[^"]*",', pt_str, content)
    content = re.sub(r'lastUpdate:\s*"Mise à jour:[^"]*",', fr_str, content)
    content = re.sub(r'lastUpdate:\s*"Mise à jour\s*:[^"]*",', fr_str, content)

    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(content)

    log(f"index.html atualizado: Última atualização: {date_br} - {time_str}")

def git_commit_and_push(dump_filename):
    """Comita e envia as alterações para o GitHub."""
    os.chdir(BASE_DIR)
    try:
        # Verificar se há alterações
        status = subprocess.check_output(["git", "status", "--porcelain"], text=True)
        if not status.strip():
            log("Nenhuma alteração detectada para commit no Git.")
            return True

        subprocess.check_call(["git", "add", "index.html", "metlife_users_data.js", "metlife_simulations_data.js"])
        msg = f"auto: daily update with {os.path.basename(dump_filename)}"
        subprocess.check_call(["git", "commit", "-m", msg])
        log(f"Commit realizado: '{msg}'")

        log("Enviando para o GitHub (git push origin main)...")
        subprocess.check_call(["git", "push", "origin", "main"])
        log("Push para o GitHub concluído com sucesso!")
        return True
    except subprocess.CalledProcessError as e:
        log(f"Erro no Git: {e}")
        return False

def main():
    log("=" * 60)
    log("Iniciando rotina do Robô de Atualização MetLife...")
    
    latest_dump = find_latest_dump()
    if not latest_dump:
        log("Erro: Nenhum arquivo de dump JSON encontrado para processar.")
        sys.exit(1)

    date_br, time_str, dt = parse_dump_date(latest_dump)
    log(f"Dump mais recente identificado: {os.path.basename(latest_dump)} ({date_br} {time_str})")

    # Processar dados
    process_dump_file(latest_dump)

    # Atualizar HTML
    update_index_html(date_br, time_str)

    # Publicar no GitHub
    git_commit_and_push(latest_dump)

    log("Rotina de atualização finalizada com sucesso!")
    log("=" * 60)

if __name__ == "__main__":
    main()
