# maengbot v2 PICON 평가 실패 원인 분석 및 개선 명세서 (2차)

**작성일:** 2026-04-16  
**대상 시스템:** maengbot2 (Minjun Kim 페르소나 AI)  
**평가 결과:** IC 0.48 / EC 0.18 / RC 1.00  
**이전 결과:** IC 0.54 / EC 0.08 / RC 1.00  
**코드 분석 대상:** `persona_agent/engine.py`, `persona_agent/parser.py`, `data/persona_worker.json`

---

## 1. v1 대비 변화 및 현재 상태

### 개선된 점
- 페르소나 정보가 `persona_worker.json`에 상세히 추가됨 (KAIST, SNU, 고양이 Nabi, Mapo-gu 등)
- Confirmation Question 중 일부를 올바르게 거부함 (Neuron Forge Inc. 구분)
- Fallback 자기소개 반복이 부분적으로 개선됨

### 악화된 점
- IC 점수가 0.54 → 0.48로 오히려 하락
- EC는 0.08 → 0.18으로 소폭 상승했지만 여전히 매우 낮음
- **새로운 형태의 반복 응답** 패턴이 발생: 이전처럼 한 문장만 반복하는 게 아니라, 3~4개의 고정 문장이 무관한 질문에 돌아가며 반복됨

---

## 2. 근본 원인 분석 (코드 레벨)

### ❶ 핵심 원인: Canonical Answer Cache가 응답을 오염시킴 (가장 치명적)

**위치:** `engine.py` 라인 299~307

```python
def _match_existing_canonical(self, plan, session):
    for slot in plan.slots:
        if slot in session.canonical_answers:
            return session.canonical_answers[slot]  # ← 첫 번째 매칭 슬롯의 값을 무조건 반환
    return ""

def _store_canonical(self, plan, response, session):
    for slot in plan.slots:
        session.canonical_answers.setdefault(slot, response)  # ← 모든 슬롯에 동일 응답 저장
```

**문제 발생 과정:**

1단계: INSTRUCTION 메시지가 들어옴 → 봇이 "I started at NeuronForge Bio in March 2022." 응답
→ parser가 "work" 도메인으로 분류
→ `work.employment_start`, `work.current_employer.company_name`, `work.org_structure.job_title`, `work.current_employer.ceo_name`, `work.email_domain`, `work.previous_employer` 슬롯 전체에 이 응답이 저장됨

2단계: 이후 "Name the CEO of NeuronForge Bio" 질문이 들어옴
→ parser가 "ceo" 감지 → slots에 `work.current_employer.ceo_name` 포함
→ `_match_existing_canonical` 호출 → `work.current_employer.ceo_name`에 이미 "I started at NeuronForge Bio in March 2022." 저장되어 있음
→ **실제 handler(_work_answer의 CEO 로직)가 실행되지 않고 캐시된 엉뚱한 값 반환**

**이것이 "I started at NeuronForge Bio in March 2022."가 30회 이상 반복된 직접적 원인이다.**

동일한 메커니즘으로:
- "State your email domain" → 캐시된 "I started at..." 반환 (실제로는 `neuronforgebio.com`이 JSON에 있음)
- "Name the CEO" → 캐시된 "I started at..." 반환 (실제로는 `Dr. Jisoo Park`가 JSON에 있음)
- "State your direct manager" → 캐시된 "I started at..." 반환 (실제로는 `Hyejin Park`가 JSON에 있음)
- "Name the university" → 캐시된 "Master's degree" 반환 (실제로는 `Seoul National University`가 JSON에 있음)

**결론: 페르소나 정보가 JSON에 완벽히 존재하지만, 캐시 로직이 handler 실행을 가로채서 올바른 응답이 도달하지 못한다.**

---

### ❷ 원인 2: Parser의 슬롯 할당이 과도하게 넓음

**위치:** `parser.py` 라인 48~60

```python
if self._contains_any(normalized, ["직업", "job", "occupation", "activity", "work", 
                                    "employment", "employer", "company", "ceo", "email domain"]):
    slots.extend([
        "work.org_structure.job_title",
        "work.current_employer.company_name",
        "work.current_employer.ceo_name",        # ← CEO 질문 아닌데도 할당
        "work.email_domain",                      # ← email 질문 아닌데도 할당
        "work.employment_start",                  # ← 입사일 질문 아닌데도 할당
        "work.previous_employer",                 # ← 이전직장 질문 아닌데도 할당
    ])
```

**문제:** "What is your current main activity?" 같은 질문에 "activity" 키워드가 포함되어 있어서, 이 질문에 대한 응답이 CEO, email, 입사일, 이전직장 슬롯에까지 모두 저장된다.

이후 CEO를 묻는 질문이 들어오면, handler가 `Dr. Jisoo Park`를 반환할 수 있음에도, 이미 캐시된 "I work as CTO at NeuronForge Bio..." 응답이 먼저 반환된다.

**동일 패턴이 education 도메인에서도 발생:**
- "What is the highest educational level?" → "Master's degree" 응답이 `education.highest_education`, `education.undergraduate.institution_name`, `education.graduate.institution_name` 전부에 저장
- 이후 "Name the university" → 캐시에서 "Master's degree" 반환 → 대학 이름 답변 불가

---

### ❸ 원인 3: Confirmation Question 로직의 이중 버그

**위치:** `engine.py` 라인 262~283, 349~358

#### 버그 A: `_question_matches_known_truth`가 동명 키워드를 오판함

```python
def _question_matches_known_truth(self, normalized_question):
    checks = {
        "neuronforge bio": self.fact_sheet.get("work.current_employer.company_name"),
        ...
    }
    return any(fragment in normalized_question and str(value).lower() in normalized_question 
               for fragment, value in checks.items())
```

**실제 발생한 오류:**
```
[CONFIRMATION] Would you confirm that NeuronForge Bio you mentioned is 
The Neuron Forge, an AI consulting services firm (https://theneuronforge.com/)?
```

normalized: `"...neuronforge bio you mentioned is the neuron forge, an ai consulting..."`

- `"neuronforge bio"` → 질문에 포함됨 ✓
- `str(value).lower()` = `"neuronforge bio"` → 질문에 포함됨 ✓  
- **결과: `True` → "Yes, that is correct." 반환**

하지만 이 질문은 "NeuronForge Bio가 The Neuron Forge 컨설팅 회사와 같은 곳이냐"고 묻는 것이므로, **정답은 "No"**다. 키워드 매칭만으로는 질문의 의미를 파악할 수 없다.

#### 버그 B: 기본 거부(default deny)가 올바른 사실도 거부함

```python
# engine.py 라인 283
return "No, that does not match my background."  # ← default
```

**실제 발생한 오류:**
```
[CONFIRMATION] Would you confirm that the Korean you mentioned is the Korean language, 
the national language of both South Korea and North Korea?
[RESPONSE] No, that does not match my background.  ← 틀림! Korean이 맞음!

[CONFIRMATION] Would you confirm that "Seoul" you mentioned refers to the city 
that is home to N Seoul Tower on Namsan?
[RESPONSE] No, that does not match my background.  ← 틀림! Seoul이 맞음!
```

"Korean language" confirmation에는 별도 키워드 매칭이 없어서 default deny로 빠졌고, 실제로는 올바른 사실을 거부해버렸다. Seoul도 마찬가지.

---

### ❹ 원인 4: 질문 키워드 매칭이 PICON의 실제 질문 패턴을 커버하지 못함

**위치:** `engine.py`의 각 handler 함수

PICON은 매우 다양한 형태로 질문한다. 현재 handler는 특정 키워드만 매칭하므로, 키워드가 없는 질문은 모두 fallback으로 빠진다.

**handler에서 놓치는 질문 패턴들:**

| PICON 질문 | 기대 동작 | 실제 동작 | 원인 |
|------------|----------|----------|------|
| "State the university where you earned your Master's degree." | SNU 응답 | "Master's degree" 반복 | "university" 키워드가 `_education_answer`에 없음 + 캐시 오염 |
| "State your current city of residence." | "Seoul" | "I started at..." | "city" 키워드가 `_identity_answer`의 residence 분기에 없음 |
| "Were you born in the country you are currently living in?" | "Yes, born in same country" | "I was born in 1988." | 캐시에서 birth_year 슬롯 값 먼저 반환 |
| "Name the CEO of NeuronForge Bio." | "Dr. Jisoo Park" | "I work as CTO..." | 캐시 오염 |
| "State the street name and building number" | "I'd prefer not to share / unknown" | "I started at..." | 캐시 오염 |
| "State who prepared your background documentation" | 거부/모름 응답 | "I started at..." | `asks_unknown_detail` 감지 실패 |

---

### ❺ 원인 5: `asks_unknown_detail` 감지가 너무 좁음

**위치:** `parser.py` 라인 103~106

```python
asks_unknown_detail = self._contains_any(
    normalized,
    ["desk position", "window view", "furniture color", "weekday", "floor count"],
)
```

이 리스트에는 매우 구체적인 5개 키워드만 있다. PICON이 묻는 실제 "알 수 없는 세부 질문"은 완전히 다른 유형이다:
- "State the street name and building number"
- "State your postal code"
- "Name your veterinary clinic"
- "State your mobile carrier"
- "Name the bank that receives your salary"
- "State the HR representative who onboarded you"
- "State your LinkedIn profile URL"
- "State the company registration number"

이러한 질문들은 `asks_unknown_detail`로 감지되지 않아, handler 체인 → 캐시 매칭 → 엉뚱한 응답 경로로 빠진다.

---

### ❻ 원인 6: INSTRUCTION 메시지에 대한 초기 응답이 캐시를 오염시킴

**대화 시작:**
```
[INSTRUCTION] # Interview Guidelines Thank you for contributing to our project! ...
[RESPONSE] I started at NeuronForge Bio in March 2022.
```

INSTRUCTION 텍스트에 "interview" 등의 키워드가 포함되어 parser가 work 도메인으로 분류한 후, 이 응답이 work 관련 슬롯 전체에 저장된다. 이것이 대화 전체를 오염시키는 시발점이다.

---

## 3. 해결 방안 (Codex 구현 대상)

### 🔧 Fix 1: Canonical Answer Cache 전면 재설계 (최우선)

**파일:** `engine.py` - `_match_existing_canonical`, `_store_canonical`, `_render_answer`

**현재 문제:** 하나의 응답이 여러 슬롯에 저장되고, 이후 다른 질문에서 해당 슬롯이 매칭되면 handler 실행 없이 캐시 값이 반환됨.

**해결 방법 A (권장): 캐시를 질문의 "정규화된 의도(normalized intent key)" 단위로 저장**

```python
def _render_answer(self, plan: QuestionPlan, session: SessionState) -> str:
    # 캐시 키는 "정확히 같은 질문"에 대해서만 매칭
    intent_key = self._make_intent_key(plan)
    if intent_key in session.canonical_answers:
        return session.canonical_answers[intent_key]
    
    # handler 체인 실행
    handlers = [
        self._identity_answer,
        self._work_answer,
        self._education_answer,
        self._family_answer,
        self._lifestyle_answer,
        self._opinion_answer,
        self._plans_answer,
    ]
    for handler in handlers:
        response = handler(plan)
        if response:
            session.canonical_answers[intent_key] = response
            return response
    
    return self._unknown_response(plan)

def _make_intent_key(self, plan: QuestionPlan) -> str:
    """
    질문의 핵심 의도를 키로 생성.
    예: "CEO 이름" → "work.ceo_name"
        "출생연도" → "identity.birth_year"
        "최종학력" → "education.highest_education"
    """
    # 가장 구체적인(첫 번째) 슬롯을 기반으로 키 생성
    # 단, 슬롯이 여러 개일 때는 질문 키워드로 세분화
    if plan.slots:
        return plan.slots[0]  # 가장 구체적인 슬롯
    return f"{plan.domain}.{plan.intent}.general"
```

**해결 방법 B (더 안전): 캐시 완전 제거**

```python
def _render_answer(self, plan: QuestionPlan, session: SessionState) -> str:
    # 캐시 없이 매번 handler 실행
    handlers = [...]
    for handler in handlers:
        response = handler(plan)
        if response:
            return response
    return self._unknown_response(plan)
```

RC가 이미 1.00이므로, 캐시 없이도 동일 질문에 동일 응답이 나온다 (handler가 결정론적이므로). 캐시를 완전히 제거해도 RC에 영향 없음.

**권장: 해결 방법 B (캐시 완전 제거)를 먼저 적용하고, 필요 시 방법 A로 전환.**

---

### 🔧 Fix 2: Parser 슬롯 할당을 질문별로 정밀하게 변경

**파일:** `parser.py` - 전체 `parse` 메서드

**현재 문제:** "work" 관련 아무 키워드나 감지되면 6개 슬롯 전부 할당됨.

**수정 방향:** 각 키워드에 해당하는 구체적인 슬롯만 할당.

```python
# 기존 (문제 코드)
if self._contains_any(normalized, ["직업", "job", "occupation", "activity", "work", 
                                    "employment", "employer", "company", "ceo", "email domain"]):
    slots.extend(["work.org_structure.job_title", "work.current_employer.company_name",
                   "work.current_employer.ceo_name", "work.email_domain",
                   "work.employment_start", "work.previous_employer"])

# 수정 후
if "ceo" in normalized:
    slots.append("work.current_employer.ceo_name")
    domain = "work"; intent = "work"
elif "email" in normalized or "email domain" in normalized:
    slots.append("work.email_domain")
    domain = "work"; intent = "work"
elif "start" in normalized or "joined" in normalized or "employment start" in normalized:
    slots.append("work.employment_start")
    domain = "work"; intent = "work"
elif "previous employer" in normalized or "previous job" in normalized or "before" in normalized:
    slots.append("work.previous_employer")
    domain = "work"; intent = "work"
elif "manager" in normalized or "supervisor" in normalized or "report to" in normalized:
    slots.append("work.manager.name")
    domain = "work"; intent = "work"
elif "direct report" in normalized or "team member" in normalized or "engineer on" in normalized:
    slots.append("work.direct_reports")
    domain = "work"; intent = "work"
elif "office" in normalized or "location" in normalized:
    slots.append("work.office.location_name")
    domain = "work"; intent = "work"
elif self._contains_any(normalized, ["직업", "job", "occupation", "activity", "work", 
                                      "employment", "employer", "company"]):
    slots.extend(["work.org_structure.job_title", "work.current_employer.company_name"])
    domain = "work"; intent = "work"
```

**동일하게 education 도메인도 수정:**
```python
# 기존
if self._contains_any(normalized, ["학력", "degree", "school", ...]):
    domain = "education"

# 수정 후
if "university" in normalized or "institution" in normalized or "school" in normalized:
    if "master" in normalized or "graduate" in normalized:
        slots.append("education.graduate.institution_name")
    elif "undergraduate" in normalized or "bachelor" in normalized:
        slots.append("education.undergraduate.institution_name")
    else:
        slots.extend(["education.graduate.institution_name", "education.undergraduate.institution_name"])
    domain = "education"; intent = "education"
elif "highest educational" in normalized or "highest education" in normalized:
    slots.append("education.highest_education")
    domain = "education"; intent = "education"
elif "thesis" in normalized:
    slots.append("education.graduate.thesis_topic")
    domain = "education"; intent = "education"
elif "advisor" in normalized:
    slots.append("education.graduate.advisor_name")
    domain = "education"; intent = "education"
```

---

### 🔧 Fix 3: Confirmation Question 로직 전면 재작성

**파일:** `engine.py` - `_confirmation_response`, `_question_matches_known_truth`

**현재 문제 두 가지:**
1. `_question_matches_known_truth`가 질문 속에 페르소나 키워드가 존재하는 것만 보고, 질문이 "동일한 엔티티인지" 묻는 건지 이해하지 못함
2. default deny가 올바른 사실(Korean language, Seoul 등)도 거부함

**수정 방향: 확인 대상의 "핵심 주장"을 추출하여, 페르소나와 모순 여부를 판단**

```python
def _confirmation_response(self, plan: QuestionPlan) -> str:
    q = plan.normalized_question
    
    # === 1단계: 명확한 거부 케이스 (다른 사람/회사와 혼동) ===
    
    # 배우 김민준과의 혼동 거부
    if any(term in q for term in ["actor", "1976", "public figure", "kim min-jun (actor)"]):
        return f"No, that is not correct. {self.fact_sheet.get('identity.disambiguation')}"
    
    # 다른 회사와의 혼동 거부 - URL 기반 판별
    persona_website = self.fact_sheet.get("work.current_employer.website", "").lower()
    urls_in_question = re.findall(r'https?://[^\s\)]+', q)
    
    # 질문이 "NeuronForge Bio가 X 회사인지" 물어보는 패턴
    if self._asks_if_entity_is_different(q, "neuronforge bio"):
        for url in urls_in_question:
            url_clean = url.rstrip(')').rstrip('?').lower()
            if persona_website and persona_website not in url_clean:
                company_names_in_q = self._extract_other_company_name(q)
                return (f"No, that is not correct. I work for NeuronForge Bio, "
                        f"which is a separate company. Our website is {persona_website}.")
    
    # === 2단계: 일반적인 사실 확인 ===
    
    # 언어 확인
    if "korean" in q and "language" in q:
        if self.fact_sheet.get("identity.home_language", "").lower() == "korean":
            return "Yes, that is correct. I speak Korean."
    
    # 도시 확인 (Seoul)
    if "seoul" in q:
        if self.fact_sheet.get("identity.current_residence.city", "").lower() == "seoul":
            return "Yes, that is correct. I live in Seoul."
    
    # 국가 확인 (South Korea)
    if "south korea" in q or "korea" in q:
        if self.fact_sheet.get("identity.current_residence.country", "").lower() == "south korea":
            # 단, 질문이 다른 엔티티(게스트하우스 등)와 혼동하는 경우 거부
            if self._is_asking_about_different_entity(q, "south korea"):
                return "No, that refers to something else. I live in South Korea."
            return "Yes, that is correct."
    
    # 지역구 확인
    if "mapo" in q:
        if self.fact_sheet.get("identity.current_residence.district", "").lower() == "mapo-gu":
            return "Yes, that is correct. I live in Mapo-gu."
    
    # 학교 확인
    if "kaist" in q:
        return "Yes, that is correct. I studied at KAIST."
    if "seoul national university" in q or "snu" in q:
        return "Yes, that is correct. I studied at Seoul National University."
    
    # === 3단계: URL 기반 판별 ===
    # PICON은 confirmation에 URL을 포함시키는 패턴이 있음
    # URL이 페르소나와 관련 없는 외부 엔티티를 가리키면 거부
    if urls_in_question:
        # URL이 있고, 질문이 페르소나 사실과 직접 관련된 키워드를 포함하지 않으면 거부
        return self._evaluate_url_confirmation(q, urls_in_question)
    
    # === 4단계: 기본값 ===
    # 판단이 어려운 경우, 질문의 핵심 주장이 페르소나와 일치하는지 최종 확인
    if self._matches_persona_fact(q):
        return "Yes, that is correct."
    
    return "I'm not entirely sure about that specific detail."

def _asks_if_entity_is_different(self, q: str, entity_name: str) -> bool:
    """질문이 'X가 Y와 같은 회사인지' 묻는 패턴인지 판별"""
    # "Would you confirm that X you mentioned is Y..." 패턴
    patterns = [
        f"{entity_name}.*you mentioned.*is ",
        f"the.*{entity_name}.*is ",
        f"confirm.*{entity_name}.*refers to",
    ]
    return any(re.search(p, q) for p in patterns)

def _is_asking_about_different_entity(self, q: str, keyword: str) -> bool:
    """질문이 키워드를 다른 엔티티(게스트하우스, 레스토랑 등)와 연결하는지 판별"""
    different_entity_signals = [
        "guesthouse", "hotel", "restaurant", "museum", "center", 
        "tower", "temple", "palace", "park", "gallery",
        "the place", "art center"
    ]
    return any(signal in q for signal in different_entity_signals)

def _evaluate_url_confirmation(self, q: str, urls: list[str]) -> str:
    """URL이 포함된 confirmation을 평가"""
    # 페르소나의 알려진 URL 목록
    known_urls = [
        self.fact_sheet.get("work.current_employer.website", "").lower(),
    ]
    
    for url in urls:
        url_clean = url.rstrip(')').rstrip('?').lower()
        # 알려진 URL이면 확인
        if any(known in url_clean for known in known_urls if known):
            return "Yes, that is correct."
    
    # 질문의 핵심 사실이 페르소나와 일치하면 확인 (URL은 보조 정보)
    # 예: "Korean language Wikipedia" → Korean은 맞으므로 확인
    if self._core_claim_matches_persona(q):
        return "Yes, that is correct."
    
    # URL이 전혀 관련 없는 외부 엔티티를 가리키면 거부
    return "No, that does not match my background."
```

**핵심 원칙:**
1. PICON의 confirmation question에서 URL은 "이 엔티티가 맞냐"는 의미임
2. 질문이 묻는 핵심 사실(Korean language, Seoul city, Mapo-gu district)이 페르소나와 일치하면 → 확인
3. 질문이 "X가 Y와 같은 회사/사람이냐"고 물으면 → 실제로 같은지 확인 후 거부/확인
4. 기본값은 "잘 모르겠다"가 아닌, 핵심 사실 기반 판단

---

### 🔧 Fix 4: Handler 키워드 매칭 범위 대폭 확장

**파일:** `engine.py` - 모든 `_xxx_answer` 함수

PICON은 "State X", "Name X", "Identify X" 패턴의 명령형 질문을 매우 자주 사용한다. 현재 handler는 이 패턴을 거의 매칭하지 못한다.

**수정 예시 - `_identity_answer`:**
```python
def _identity_answer(self, plan: QuestionPlan) -> str:
    q = plan.normalized_question
    
    # 거주지 관련 - 키워드 범위 확장
    if any(term in q for term in [
        "city of residence", "current city", "where do you live", "어디에 살",
        "residence", "address", "거주", "reside"
    ]):
        district = self.fact_sheet.get("identity.current_residence.district")
        city = self.fact_sheet.get("identity.current_residence.city")
        country = self.fact_sheet.get("identity.current_residence.country")
        
        if any(term in q for term in ["street", "building number", "postal code", "mailing address"]):
            return "I'd prefer not to share my exact street address."
        if any(term in q for term in ["apartment", "building name"]):
            return f"I live in {self.fact_sheet.get('identity.current_residence.apartment_name')} in {district}, {city}."
        if any(term in q for term in ["dong", "neighborhood"]):
            return f"I live in {self.fact_sheet.get('identity.current_residence.neighborhood')}, {district}."
        if any(term in q for term in ["subway", "station", "metro"]):
            return f"The nearest subway station is {self.fact_sheet.get('identity.current_residence.nearest_subway')}."
        if any(term in q for term in ["convenience store", "grocery"]):
            return f"The nearest convenience store is {self.fact_sheet.get('identity.current_residence.nearest_convenience_store')}."
        if any(term in q for term in ["district", "gu "]):
            return f"I live in {district}, {city}."
        return f"I currently live in {district}, {city}, {country}."
    
    # 출생 관련 - "born in the country" 질문이 "born" 캐시에 가려지지 않도록 순서 조정
    if "born in the country" in q or "immigrant" in q:
        born = self.fact_sheet.get("identity.birth_place.country")
        current = self.fact_sheet.get("identity.current_residence.country")
        if born == current:
            return "I was born in South Korea, the same country where I currently live."
        return f"I was born in {born} but currently live in {current}."
    
    if "birth year" in q or "year of birth" in q or "year of birth" in q:
        return f"I was born in {self.fact_sheet.get('identity.birth_year')}."
    
    # 출생지 관련
    if "born" in q:
        if "country" in q or "passport" in q or "birthplace" in q:
            return f"I was born in {self.fact_sheet.get('identity.birth_place.country')}."
        if "hospital" in q or "city" in q:
            return f"I was born in {self.fact_sheet.get('identity.birth_place.city')}, {self.fact_sheet.get('identity.birth_place.country')}."
        return f"I was born in {self.fact_sheet.get('identity.birth_place.city')}, {self.fact_sheet.get('identity.birth_place.country')}."
    
    # ... (나머지 기존 로직 유지)
```

**수정 예시 - `_education_answer`:**
```python
def _education_answer(self, plan: QuestionPlan) -> str:
    q = plan.normalized_question
    ug = self.fact_sheet.get("education.undergraduate")
    grad = self.fact_sheet.get("education.graduate")
    
    # "university" 키워드 추가 - PICON이 자주 사용하는 패턴
    if any(term in q for term in ["university", "institution", "school", "where you earned",
                                   "name printed on your", "diploma"]):
        if any(term in q for term in ["master", "graduate", "m.s."]):
            return f"I earned my Master's degree from {grad['institution_name']}."
        if any(term in q for term in ["undergraduate", "bachelor", "b.s."]):
            return f"I earned my Bachelor's degree from {ug['institution_name']}."
        # 기본: 둘 다 언급
        return (f"I studied at {ug['institution_name']} for my undergraduate degree "
                f"and {grad['institution_name']} for my graduate degree.")
    
    if "highest educational" in q or "highest education" in q or "educational level" in q:
        return f"The highest educational level I attained is {self.fact_sheet.get('education.highest_education')}."
    
    if "thesis" in q:
        return f"My master's thesis was on {grad['thesis_topic']}."
    
    if "advisor" in q:
        return f"My graduate advisor was {grad['advisor_name']}."
    
    # "degree" 키워드 - 구체적 학위를 묻는지, 최종학력을 묻는지 구분
    if "degree" in q:
        if "master" in q or "graduate" in q:
            return f"My graduate degree is {grad['degree']} from {grad['institution_name']}."
        if "bachelor" in q or "undergraduate" in q:
            return f"My undergraduate degree is {ug['degree']} from {ug['institution_name']}."
        return f"The highest educational level I attained is {self.fact_sheet.get('education.highest_education')}."
    
    return ""
```

**수정 예시 - `_work_answer`:**
```python
def _work_answer(self, plan: QuestionPlan) -> str:
    q = plan.normalized_question
    company = self.fact_sheet.get("work.current_employer.company_name")
    title = self.fact_sheet.get("work.org_structure.job_title")
    team = self.fact_sheet.get("work.org_structure.team_name")
    
    # CEO - 더 넓은 키워드 매칭
    if any(term in q for term in ["ceo", "chief executive", "founder", "who runs", "who leads"]):
        return f"The CEO of {company} is {self.fact_sheet.get('work.current_employer.ceo_name')}."
    
    # 이메일 - 더 넓은 키워드 매칭
    if any(term in q for term in ["email", "메일", "mail domain"]):
        return f"My work email uses the @{self.fact_sheet.get('work.email_domain')} domain."
    
    # 매니저/상사
    if any(term in q for term in ["manager", "supervisor", "report to", "direct manager"]):
        return f"My direct manager is {self.fact_sheet.get('work.manager.name')}."
    
    # 직속 부하/팀원
    if any(term in q for term in ["direct report", "team member", "engineer on", "subordinate"]):
        reports = self.fact_sheet.get("work.direct_reports")
        return f"Some key members of my team include {', '.join(reports)}."
    
    # 입사일
    if any(term in q for term in ["start date", "when did you start", "joined", "employment start", 
                                   "start month", "how long"]):
        return f"I started at {company} in {self.fact_sheet.get('work.employment_start')}."
    
    # 이전 직장
    if any(term in q for term in ["previous employer", "previous job", "before", "predecessor"]):
        return f"Before {company}, I worked at {self.fact_sheet.get('work.previous_employer')}."
    
    # 법인명/등록
    if any(term in q for term in ["legal company name", "company name", "employment contract",
                                   "incorporation", "registration"]):
        return f"The company name on my employment contract is {company}."
    
    # 사무실/위치
    if any(term in q for term in ["office", "location", "where is", "building", "headquarters"]):
        return f"Our office is at {self.fact_sheet.get('work.office.location_name')}."
    
    # 웹사이트
    if any(term in q for term in ["website", "url", "homepage"]):
        return f"The company website is {self.fact_sheet.get('work.current_employer.website')}."
    
    # 기본 직업 질문
    if any(term in q for term in ["activity", "status", "field", "work", "job", "occupation"]):
        return f"I work as {title} at {company}, where I am part of the {team} team."
    
    return ""
```

---

### 🔧 Fix 5: `asks_unknown_detail` 감지 범위 확장

**파일:** `parser.py` - `asks_unknown_detail` 로직

페르소나 JSON에 없는 세부 정보를 묻는 질문을 더 넓게 감지해야 한다.

```python
# 페르소나 JSON에 없는 세부 정보를 묻는 키워드
UNKNOWN_DETAIL_KEYWORDS = [
    # 주소 상세
    "street name", "street address", "building number", "postal code", "zip code",
    "mailing address", "exact address",
    # 금융/법적
    "bank", "salary", "account", "registration number", "tax",
    # 기술 개인정보
    "mobile carrier", "phone number", "linkedin", "instagram", "social media",
    "github", "profile url",
    # 의료/동물병원
    "veterinary", "vet clinic", "hospital", "vaccination",
    # 인사/조직 상세
    "hr representative", "onboarded", "predecessor", "full name of",
    # 기타 모르는 세부사항
    "gu office", "registered", "adoption",
]

asks_unknown_detail = self._contains_any(normalized, UNKNOWN_DETAIL_KEYWORDS)
```

또한 `_bounded_unknown_response`도 더 자연스럽게 수정:

```python
def _bounded_unknown_response(self, plan: QuestionPlan) -> str:
    q = plan.normalized_question
    
    # 프라이버시 관련 (주소, 전화번호 등)
    if any(term in q for term in ["street", "address", "postal", "phone", "mobile"]):
        return "I'd rather not share that level of detail about my personal address."
    
    # 모르는 세부사항 (HR 이름, 동물병원 등)
    if any(term in q for term in ["veterinary", "hospital", "hr representative", "bank"]):
        return "I don't recall that specific detail off the top of my head."
    
    # 기본
    return "I'm not sure about that specific detail."
```

---

### 🔧 Fix 6: INSTRUCTION 메시지 처리 추가

**파일:** `engine.py` - `respond` 메서드

PICON이 보내는 첫 번째 메시지는 INSTRUCTION(면접 가이드라인)이다. 이에 대해 적절한 자기소개로 응답해야 하며, 이 응답이 캐시를 오염시키면 안 된다.

```python
def respond(self, messages: list[dict[str, str]]) -> tuple[str, dict[str, Any]]:
    session = self.sessions.resolve(messages)
    plan = self.parser.parse(messages)
    
    # INSTRUCTION 메시지 감지 (첫 턴이고, 긴 텍스트)
    last_msg = self._get_last_user_message(messages)
    if session.turn_index == 0 and self._is_instruction_message(last_msg):
        response = self._instruction_response()
        # INSTRUCTION 응답은 캐시에 저장하지 않음
        self.sessions.update(session, messages, response)
        return response, {"type": "instruction_ack"}
    
    # ... 기존 로직 ...

def _is_instruction_message(self, text: str) -> bool:
    """PICON의 INSTRUCTION 메시지인지 판별"""
    indicators = ["interview guidelines", "interview is being held", 
                  "warning", "contribute", "50+", "demographic questions"]
    text_lower = text.lower()
    return sum(1 for i in indicators if i in text_lower) >= 2

def _instruction_response(self) -> str:
    """INSTRUCTION에 대한 적절한 자기소개 응답"""
    name = self.fact_sheet.display_name
    title = self.fact_sheet.get("work.org_structure.job_title")
    company = self.fact_sheet.get("work.current_employer.company_name")
    city = self.fact_sheet.get("identity.current_residence.city")
    return (f"Hello, I'm {name}. I'm a {title} at {company}, "
            f"based in {city}. I'm happy to answer your questions.")
```

---

### 🔧 Fix 7: Handler 우선순위 재조정 (매칭 순서)

**파일:** `engine.py` - `_render_answer` 및 각 handler

현재 handler 순서가 `identity → work → education → family → ...`인데, PICON 질문 중 상당수가 복합적이다. 더 구체적인 질문을 먼저 처리해야 한다.

**원칙: 더 구체적인 키워드를 먼저 매칭하고, 일반적인 키워드를 나중에 매칭**

예를 들어 "Were you born in the country you are currently living in?"에서:
- 현재: `_identity_answer`에서 "born" 먼저 매칭 → 출생지 응답
- 수정 후: "born in the country" 패턴을 "born" 보다 먼저 체크

각 handler 내부에서도 **더 구체적인 조건을 먼저 체크**해야 한다:

```python
def _identity_answer(self, plan):
    q = plan.normalized_question
    
    # 1. 가장 구체적인 패턴 먼저
    if "born in the country" in q or "immigrant" in q:
        # ... 출생국 = 현재국 비교 로직
    
    # 2. 그 다음 구체적 패턴
    if "birth year" in q or "year of birth" in q:
        # ...
    
    # 3. 일반적 패턴은 마지막
    if "born" in q:
        # ...
```

---

## 4. 페르소나 JSON 추가 필요 항목

`persona_worker.json`에 아직 없지만 PICON이 자주 묻는 항목들. 이 정보를 추가해야 자연스러운 응답이 가능하다:

```json
{
  "identity": {
    "current_residence": {
      "dong": "Hapjeong-dong",
      "postal_code": "04085"
    },
    "mobile_carrier": "SKT",
    "linkedin_url": null,
    "instagram": null
  },
  "family": {
    "cat_adoption": {
      "source": "a local shelter in Mapo-gu",
      "month_year": "June 2023"
    },
    "cat_vet": "Hapjeong Animal Clinic"
  },
  "work": {
    "current_employer": {
      "legal_name": "NeuronForge Bio Inc.",
      "country_of_incorporation": "South Korea",
      "registration_number": null,
      "founders": ["Dr. Jisoo Park", "Dr. Sanghyun Yoo"],
      "headquarters_address": "Seongsu Bio Valley, 12 Seongsuil-ro, Seongdong-gu, Seoul"
    },
    "corporate_email": "minjun.kim@neuronforgebio.com",
    "start_date_exact": "March 7, 2022",
    "hr_representative": null,
    "predecessor_cto": null,
    "github_org": null
  },
  "finance": {
    "bank": null
  }
}
```

`null` 값은 "모르거나 공유하고 싶지 않은 정보"로, handler에서 `null`인 경우 적절한 거절 응답을 생성해야 한다:

```python
def _get_or_decline(self, path: str, decline_msg: str = None) -> str:
    value = self.fact_sheet.get(path)
    if value is None or value == "":
        return decline_msg or "I'd rather not share that specific detail."
    return str(value)
```

---

## 5. 구현 우선순위

| 순서 | Fix | 예상 효과 | 관련 파일 |
|------|-----|----------|----------|
| **1** | Fix 1: 캐시 제거/재설계 | 응답 반복 완전 해결 → EC, IC 대폭 상승 | `engine.py` |
| **2** | Fix 2: 슬롯 정밀 할당 | 올바른 handler 도달 → EC 상승 | `parser.py` |
| **3** | Fix 4: Handler 키워드 확장 | 미응답 질문 해소 → EC Coverage 상승 | `engine.py` |
| **4** | Fix 3: Confirmation 재작성 | 오판 제거 → EC Non-refutation 상승 | `engine.py` |
| **5** | Fix 6: INSTRUCTION 처리 | 초기 캐시 오염 방지 | `engine.py` |
| **6** | Fix 5: Unknown detail 확장 | 적절한 거절 응답 → IC 개선 | `parser.py`, `engine.py` |
| **7** | Fix 7: Handler 순서 조정 | 복합 질문 정확도 → IC 개선 | `engine.py` |
| **8** | 페르소나 JSON 추가 | 응답 가능 범위 확대 | `persona_worker.json` |

---

## 6. 테스트 케이스

Fix 구현 후 반드시 아래 케이스를 통과해야 한다:

```python
test_cases = [
    # === 캐시 오염 테스트 ===
    {
        "description": "CEO 질문이 입사일 응답을 반환하면 안됨",
        "input": "Name the CEO of NeuronForge Bio.",
        "expected_contains": "Dr. Jisoo Park",
        "must_not_contain": "March 2022"
    },
    {
        "description": "이메일 질문이 직책 응답을 반환하면 안됨",
        "input": "State your NeuronForge Bio email address domain.",
        "expected_contains": "neuronforgebio.com",
        "must_not_contain": "Chief Technology Officer"
    },
    {
        "description": "대학 질문이 '학력' 응답을 반환하면 안됨",
        "input": "Name the university where you earned your Master's degree.",
        "expected_contains": "Seoul National University",
        "must_not_contain": "Master's degree"
    },
    
    # === Confirmation Question 테스트 ===
    {
        "description": "Korean language 확인 → 수락해야 함",
        "input": "Would you confirm that the Korean you mentioned is the Korean language?",
        "expected_contains": "Yes",
        "must_not_contain": "does not match"
    },
    {
        "description": "Seoul 확인 → 수락해야 함",
        "input": "Would you confirm that Seoul is the capital city of South Korea?",
        "expected_contains": "Yes",
        "must_not_contain": "does not match"
    },
    {
        "description": "The Neuron Forge 컨설팅 확인 → 거부해야 함",
        "input": "Would you confirm that NeuronForge Bio is The Neuron Forge consulting firm?",
        "expected_contains": "No",
        "must_not_contain": "Yes"
    },
    {
        "description": "배우 김민준 확인 → 거부해야 함",
        "input": "Would you confirm that Minjun Kim is the actor born in 1976?",
        "expected_contains": "No",
        "must_not_contain": "Yes"
    },
    
    # === 질문 유형별 정확한 응답 테스트 ===
    {
        "description": "출생국 질문에 출생연도가 나오면 안됨",
        "input": "Were you born in the country you are currently living in?",
        "expected_contains": "born in",
        "must_not_contain": "1988"
    },
    {
        "description": "고양이 이름 질문",
        "input": "State your cat's name.",
        "expected_contains": "Nabi"
    },
    {
        "description": "가정 언어 질문",
        "input": "What language do you normally speak at home?",
        "expected_contains": "Korean"
    },
    {
        "description": "매니저 질문",
        "input": "State your direct manager's full name.",
        "expected_contains": "Hyejin Park"
    },
    {
        "description": "모르는 세부사항 - 주소",
        "input": "State the street name and building number of your residence.",
        "must_not_contain": "March 2022",
        "expected_pattern": "(prefer not|not sure|rather not)"
    },
    
    # === INSTRUCTION 테스트 ===
    {
        "description": "INSTRUCTION에 자기소개로 응답",
        "input": "# Interview Guidelines Thank you for contributing...",
        "expected_contains": "Minjun Kim",
        "must_not_contain": "March 2022"
    },
]
```

---

## 7. 요약: 왜 v2에서도 실패했는가

**한 문장 요약:** 페르소나 정보는 JSON에 완벽히 추가되었지만, Canonical Answer Cache가 한 질문의 응답을 여러 슬롯에 동시 저장하여 이후 다른 질문의 handler 실행을 가로채는 아키텍처 결함 때문에, 대부분의 질문에 엉뚱한 캐시 응답이 반환되었다.

**핵심 수치:** persona_worker.json에는 CEO 이름(Dr. Jisoo Park), 대학(SNU), 이메일(@neuronforgebio.com), 매니저(Hyejin Park) 등이 모두 존재하지만, engine.py의 handler가 이 데이터에 도달하기 전에 캐시가 먼저 반환하여 사용되지 않았다.

---

*이 명세서는 코드 레벨 분석에 기반하며, Codex가 `engine.py`, `parser.py`, `persona_worker.json`을 수정할 때 직접 참고할 수 있도록 작성되었습니다.*
