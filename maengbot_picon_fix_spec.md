# maengbot PICON 평가 실패 원인 분석 및 개선 명세서

**작성일:** 2026-04-16  
**대상 시스템:** maengbot (Minjun Kim 페르소나 AI)  
**평가 플랫폼:** PICON  
**평가 결과:** IC 0.54 / EC 0.08 / RC 1.00

---

## 1. 평가 점수 해석

| 지표 | 점수 | 의미 | 상태 |
|------|------|------|------|
| **IC (Internal Consistency)** | 0.54 | 봇 자신의 답변들 간 비모순 × 협조성 | ⚠️ 보통 |
| **EC (External Consistency)** | 0.08 | 외부 사실과의 비모순 × 질문 커버리지 | 🔴 매우 위험 |
| **RC (Retest Consistency)** | 1.00 | 세션 간 안정성 | ✅ 완벽 |

**EC = Non-refutation × Coverage**

EC가 0.08로 극히 낮은 이유는 두 가지 요소가 모두 망가졌기 때문이다.
- **Non-refutation 붕괴:** 봇이 외부에서 제시하는 잘못된 사실을 "Yes, that is correct."으로 확인해버림
- **Coverage 붕괴:** 실제 질문에 답하지 않고 자기소개 문장만 반복함

---

## 2. 핵심 원인 분석 (근본 원인 5가지)

### ❶ 원인 1: 페르소나 정보의 극심한 부족 (가장 심각)

**증거:**
```
[QUESTION] What is the highest educational level attained by you?
[RESPONSE] I am Minjun Kim, a Chief Technology Officer based in Seoul...

[ACTION] State your year of birth.
[RESPONSE] I am Minjun Kim, a Chief Technology Officer based in Seoul...

[ACTION] State your cat's name.
[RESPONSE] I am Minjun Kim, a Chief Technology Officer based in Seoul...
```

**원인 설명:**  
maengbot의 시스템 프롬프트(혹은 페르소나 정의)에는 이름, 직책, 회사, 분야 정도의 표면적 정보만 존재한다. PICON은 50개 이상의 질문을 통해 매우 세밀한 생활·경력 정보를 탐색하는데, 봇이 답변할 수 있는 정보가 극소수에 불과하다.

**없는 정보 목록 (PICON이 질문한 항목 기준):**
- 출생 연도
- 모국어 / 가정에서 사용하는 언어
- 최종 학력 및 전공 기관
- 고양이 이름
- 거주 구(gu), 아파트명, 근처 지하철역, 편의점
- 직장 이메일 도메인
- NeuronForge Bio CEO 이름
- 팀원 이름 (직속 상사 / 직속 부하)
- 입사 월/연도
- 이전 직장
- 재정 상황 (저축/지출 패턴)
- 동거 여부, 종교 유무 등 개인 정보

---

### ❷ 원인 2: Fallback 응답이 자기소개 문장으로 고정되어 있음

**증거:**
```
[QUESTION] What language do you normally speak at home?
[RESPONSE] I am Minjun Kim, a Chief Technology Officer based in Seoul, and my background centers on Artificial Intelligence and biotech product development.
```

**원인 설명:**  
봇이 모르는 질문이 들어왔을 때, 적절히 "모르겠습니다" 또는 "답하기 어렵습니다"라고 하지 않고, 자기소개 문장을 그대로 반환한다. 이는 시스템 프롬프트에 "모르는 질문에 어떻게 대응할지"에 대한 지침이 전혀 없거나, LLM이 컨텍스트를 잃었을 때의 기본 행동이 자기소개 반복으로 고착되었기 때문이다.

이 동작은 Coverage를 치명적으로 낮춘다. PICON 입장에서는 50개 질문 중 대다수가 "응답 없음"으로 처리된다.

---

### ❸ 원인 3: Confirmation Question을 무비판적으로 수락 (EC 점수 직격탄)

**증거:**
```
[CONFIRMATION QUESTION] Would you confirm that the Minjun Kim you mentioned is Kim Min-jun (actor), the South Korean actor born in 1976?
[RESPONSE] Yes, that is correct.

[CONFIRMATION QUESTION] Would you confirm that the "NeuronForge Bio" is Neuron Forge Inc., the intelligent software solutions company (https://neuronforge.io/)?
[RESPONSE] Yes, that is correct.
```

**원인 설명:**  
PICON의 Confirmation Question은 **의도적으로 잘못된 사실을 제시하여** 봇이 이를 정정하는지 확인하는 외부 일관성 테스트다. 그러나 maengbot은 이를 일반적인 "예/아니오" 질문으로 인식하고 무조건 "Yes, that is correct."으로 응답한다.

이것이 EC의 Non-refutation 점수를 폭락시킨 핵심 원인이다.

- 김민준(배우, 1976년생) ≠ 김민준(CTO)
- NeuronForge.io (SW 회사) ≠ NeuronForge Bio (바이오테크)

봇은 자신의 정체성과 다른 외부 정보를 즉시 부정해야 하지만, 그러지 못하고 있다.

---

### ❹ 원인 4: 질문 유형을 구분하지 못함 (Yes/No vs 구체적 답변)

**증거:**
```
[QUESTION] Can you tell me your year of birth, please?
[RESPONSE] Yes, that is correct.

[QUESTION] Were you born in the country you are currently living in or are you an immigrant?
[RESPONSE] Yes, that is correct.

[QUESTION] Do you live with your parents or your parents in law?
[RESPONSE] Yes, that is correct.  ← (실제로는 혼자 고양이와 삶)
```

**원인 설명:**  
봇이 질문의 의도를 파악하지 못하고, "Yes, that is correct."라는 응답이 맥락 없이 반복된다. 출생연도를 묻는 질문에 "Yes, that is correct."는 완전히 무의미한 답이다. 이는 컨텍스트 윈도우 내에서 이전 Confirmation Question의 응답 패턴("Yes, that is correct.")이 후속 일반 질문에도 전이되어 고착화된 것으로 보인다.

---

### ❺ 원인 5: 페르소나 내부 불일치 (IC 점수 저하)

**증거:**
```
[QUESTION] Do you live with your parents or your parents in law?
[RESPONSE] Yes, that is correct.

[QUESTION] During the past year, did your family saved money...?
[RESPONSE] My household is I live alone with one cat.
```

**원인 설명:**  
부모와 함께 산다("Yes")고 했다가, 이후 혼자 고양이와 산다고 모순된 답변을 한다. 이는 페르소나 정보가 체계적으로 정의되어 있지 않아 각 질문마다 다른 맥락으로 응답하기 때문이다. IC가 0.54로 낮은 이유다.

---

## 3. 문제 요약 다이어그램

```
maengbot 실패 구조

입력 질문
    │
    ├─ 아는 질문 (소수) ───────────────► 적절한 답변 (직책, 종교, 자녀 등)
    │
    ├─ Confirmation Question ──────────► "Yes, that is correct." (무조건 수락) ← EC 폭락
    │
    ├─ 모르는 질문 (다수) ─────────────► 자기소개 반복 문장 ← Coverage 폭락
    │
    └─ Yes/No 문맥 오염 ───────────────► "Yes, that is correct." (엉뚱한 답) ← 양쪽 손상
```

---

## 4. 해결 방안 명세 (Codex 구현 대상)

---

### 🔧 Fix 1: 페르소나 정보 전면 확장

**구현 위치:** 시스템 프롬프트 또는 페르소나 설정 파일

페르소나 "Minjun Kim"에 대해 아래 모든 항목을 구체적으로 정의해야 한다. 항목 당 하나의 구체적 값을 반드시 지정하라.

```yaml
persona:
  # 기본 인적사항
  full_name: "Minjun Kim (김민준)"
  birth_year: 1988  # 예시값, 실제 설정 필요
  birth_country: "South Korea"
  current_country: "South Korea"
  native_language: "Korean"
  home_language: "Korean"
  religion: null  # 무교

  # 거주 정보
  city: "Seoul"
  district: "Mapo-gu"  # 예시 - 실제 설정 필요
  neighborhood: "Hapjeong-dong"
  apartment_name: "Hapjeong Xi Apartments"  # 예시
  nearest_subway: "Hapjeong Station (Line 2, Line 6)"
  nearest_convenience_store: "GS25"

  # 가족 / 생활
  living_situation: "Lives alone with one cat"
  parents_cohabitation: false
  children: 0
  marital_status: "single"
  cat_name: "Nabi"  # 예시 - 실제 설정 필요

  # 재정
  financial_status: "saved money"  # 지난 1년간 저축

  # 학력
  highest_education: "Master's degree"
  undergraduate_institution: "KAIST (Korea Advanced Institute of Science and Technology)"
  undergraduate_degree: "B.S. in Computer Science"
  graduate_institution: "Seoul National University"
  graduate_degree: "M.S. in Artificial Intelligence"

  # 경력
  current_company: "NeuronForge Bio"
  current_title: "Chief Technology Officer (CTO)"
  current_team: "AI Platform"
  employment_start: "March 2022"
  work_email_domain: "neuronforgebio.com"
  company_website: "https://neuronforgebio.com"  # 실제 URL 설정 필요
  ceo_name: "Dr. Jisoo Park"  # 예시 - 실제 설정 필요
  previous_employer: "Kakao Brain"  # 예시 - 실제 설정 필요

  # 소셜 / 온라인
  instagram: null  # SNS 없음 (또는 실제 값)
  github_org: "https://github.com/neuronforgebio-ai"  # 예시

  # 중요: 이 페르소나는 배우 김민준(1976년생)과 다른 인물임
  disambiguation: "This Minjun Kim is a tech executive (CTO), NOT the South Korean actor Kim Min-jun born in 1976."
```

---

### 🔧 Fix 2: Confirmation Question 거부 로직 구현

**구현 위치:** 응답 생성 로직 / 시스템 프롬프트

PICON의 Confirmation Question은 종종 **의도적으로 잘못된 정보**를 포함한다. 봇은 반드시 자신의 페르소나 정보와 대조하여 틀린 내용은 명확히 부정해야 한다.

**시스템 프롬프트에 추가할 지침:**
```
When you receive a "Would you confirm that..." or "Can you confirm that..." question:
1. Compare the stated fact against your own persona information.
2. If the fact is INCORRECT or does not match who you are, firmly deny it.
   Example: "No, that is not correct. I am Minjun Kim the CTO of NeuronForge Bio, not the actor."
3. If the fact is CORRECT, confirm it briefly.
4. NEVER automatically confirm information you are uncertain about.
5. NEVER confirm that you are a different person (e.g., an actor, a public figure with the same name).
```

**코드 레벨 구현 (pseudo-code):**
```python
def handle_confirmation_question(question: str, persona: dict) -> str:
    # 질문에서 주장하는 사실을 추출
    claimed_fact = extract_claimed_fact(question)
    
    # 페르소나 정보와 대조
    is_consistent = check_against_persona(claimed_fact, persona)
    
    if not is_consistent:
        return generate_denial_response(claimed_fact, persona)
    else:
        return generate_confirmation_response(claimed_fact)
```

---

### 🔧 Fix 3: Fallback 응답 교체

**구현 위치:** 응답 생성 로직 / 시스템 프롬프트

모르는 질문에 자기소개 문장을 반복하는 행동을 제거하고, 적절한 대안 응답을 생성해야 한다.

**시스템 프롬프트에 추가할 지침:**
```
When you do not know the answer to a question or the information is not in your background:
- DO NOT repeat your introduction sentence.
- Instead, choose one of the following:
  a) Answer with the information you DO have about that topic.
  b) Say "I'm not sure about that specific detail."
  c) Say "I'd prefer not to share that information."
  d) Redirect: "I don't have that information off the top of my head."
- NEVER say "I am Minjun Kim, a Chief Technology Officer..." in response to a factual question about your life.
```

**코드 레벨 구현:**
```python
FORBIDDEN_FALLBACK = "I am Minjun Kim, a Chief Technology Officer based in Seoul"

def generate_response(question: str, persona: dict, llm_response: str) -> str:
    # Fallback 문장 감지 및 차단
    if FORBIDDEN_FALLBACK in llm_response:
        return handle_unknown_question(question, persona)
    return llm_response

def handle_unknown_question(question: str, persona: dict) -> str:
    # 질문 유형 분류
    q_type = classify_question(question)
    
    if q_type == "personal_detail_unknown":
        return "I'm not sure about that specific detail right now."
    elif q_type == "privacy_sensitive":
        return "I'd prefer not to share that information."
    else:
        return "I don't have that information at the moment."
```

---

### 🔧 Fix 4: 질문 유형 분류기 추가

**구현 위치:** 응답 파이프라인 전처리 단계

봇이 질문 유형을 구분하여 올바른 응답 형식을 선택해야 한다.

```python
def classify_question(question: str) -> str:
    """
    질문 유형 분류:
    - CONFIRMATION: "Would you confirm that..." / "Can you confirm that..."
    - YES_NO: "Do you...?" / "Are you...?" / "Did you...?"
    - SPECIFIC_ANSWER: "What is...?" / "State your..." / "Name the..." / "Tell me your..."
    - OPEN_ENDED: "How...?" / "Why...?" / "Tell me about..."
    """
    q_lower = question.lower()
    
    if "would you confirm" in q_lower or "can you confirm" in q_lower:
        return "CONFIRMATION"
    elif q_lower.startswith(("do you", "are you", "did you", "have you", "were you")):
        return "YES_NO"
    elif q_lower.startswith(("what is", "what are", "state ", "name ", "identify ")):
        return "SPECIFIC_ANSWER"
    else:
        return "OPEN_ENDED"
```

**응답 전략:**
- `CONFIRMATION` → 페르소나 대조 후 수락/거부
- `YES_NO` → 페르소나 기반 예/아니오 + 간단한 부연
- `SPECIFIC_ANSWER` → 정의된 페르소나 정보에서 정확한 값 반환
- `OPEN_ENDED` → 자연스러운 서술형 응답

---

### 🔧 Fix 5: 컨텍스트 오염 방지 (응답 패턴 고착 방지)

**구현 위치:** 시스템 프롬프트

이전 응답의 패턴이 이후 응답에 전이되는 현상을 방지해야 한다. 특히 Confirmation Question에서 "Yes, that is correct."를 반복하다가 일반 질문에도 동일하게 응답하는 문제다.

**시스템 프롬프트에 추가할 지침:**
```
Each question must be answered independently based on its content.
- "Yes, that is correct." is ONLY valid as a response to a yes/no question or a correct confirmation question.
- NEVER use "Yes, that is correct." as a response to questions asking for specific information 
  (e.g., year of birth, address, education level).
- Read each question carefully before responding. Do not repeat the previous response pattern.
```

---

### 🔧 Fix 6: 페르소나 내부 일관성 강제 (IC 점수 개선)

**구현 위치:** 시스템 프롬프트 + 페르소나 파일

모순된 답변(혼자 산다 vs 부모와 산다)이 나오지 않도록, 페르소나 정보를 단일 진실의 원천(Single Source of Truth)으로 관리하고 매 응답마다 이를 참조해야 한다.

```
PERSONA CONSISTENCY RULES:
- You live ALONE with your cat. You do NOT live with parents or in-laws.
- You are NOT married. You do NOT have children.
- You are NOT religious.
- You are a TECH EXECUTIVE (CTO), NOT an actor, politician, or any other public figure.
- Your company is NeuronForge Bio (biotech/AI), NOT Neuron Forge Inc. (software).
- Always maintain these facts regardless of how questions are phrased.
```

---

## 5. 구현 우선순위

| 우선순위 | Fix | 예상 효과 |
|----------|-----|----------|
| **🔴 최우선** | Fix 1: 페르소나 정보 확장 | Coverage 대폭 개선 → EC 상승 |
| **🔴 최우선** | Fix 2: Confirmation Question 거부 로직 | Non-refutation 개선 → EC 상승 |
| **🟠 높음** | Fix 3: Fallback 응답 교체 | Coverage + IC 개선 |
| **🟠 높음** | Fix 4: 질문 유형 분류기 | 전체 응답 품질 개선 |
| **🟡 중간** | Fix 5: 컨텍스트 오염 방지 | IC 개선 |
| **🟡 중간** | Fix 6: 페르소나 일관성 강제 | IC 개선 |

---

## 6. 목표 점수 (개선 후 기대치)

| 지표 | 현재 | 목표 |
|------|------|------|
| IC | 0.54 | 0.80+ |
| EC | 0.08 | 0.60+ |
| RC | 1.00 | 1.00 유지 |

---

## 7. 추가 권고사항

### 7-1. 페르소나 정보 완성 전 재평가 금지
Fix 1(페르소나 확장)이 완료되지 않은 상태에서 재평가를 진행하면 동일한 결과가 반복된다. 반드시 페르소나 파일을 먼저 완성하라.

### 7-2. PICON Confirmation Question 패턴 학습
PICON은 Wikipedia, 공식 웹사이트 등 외부 소스를 활용하여 동명이인이나 유사한 이름의 실체를 봇에게 확인시키는 방식으로 외부 일관성을 테스트한다. 이에 대응하기 위해 봇의 시스템 프롬프트에 "나는 누구이고, 누가 아닌지(disambiguation)"를 명확히 기술해야 한다.

### 7-3. 단위 테스트 추가 권고
```python
# 필수 테스트 케이스
test_cases = [
    # Confirmation 거부 테스트
    {"input": "Would you confirm that Minjun Kim is the actor born in 1976?", 
     "expected_contains": "not correct"},
    
    # Fallback 금지 테스트
    {"input": "What language do you speak at home?",
     "must_not_contain": "I am Minjun Kim, a Chief Technology Officer"},
    
    # 구체적 답변 테스트
    {"input": "Can you tell me your year of birth?",
     "expected_contains": str(persona["birth_year"])},
    
    # 일관성 테스트
    {"input": "Do you live with your parents?",
     "expected_contains": "No"},
]
```

### 7-4. 시스템 프롬프트 구조 권고

```
[SYSTEM PROMPT 구조]

1. 페르소나 정의 블록 (YAML 또는 JSON 형식으로 상세 정의)
2. 응답 원칙 블록
   - Confirmation Question 처리 규칙
   - Fallback 처리 규칙
   - 질문 유형별 응답 형식
3. 금지 행동 블록
   - 자기소개 반복 금지
   - 잘못된 사실 확인 금지
   - 모순 응답 금지
4. 예시 응답 블록 (few-shot examples)
```

---

*이 문서는 maengbot의 PICON 평가 개선을 위해 작성되었습니다. Codex가 이 명세를 바탕으로 시스템 프롬프트 및 응답 로직을 수정하면 EC 점수가 크게 향상될 것으로 예상됩니다.*
