# 로그인 전용 혼합 벤더 셋업

API 키를 쓰지 않습니다. Claude Code는 Claude 플랜 로그인, Codex는 ChatGPT
로그인으로 동작합니다. 둘 다 이미 로그인돼 있으면 설치 후 바로 실행됩니다.

```
   project-leader      Claude Fable 5   Claude Code 메인 세션
   logic-reviewer      Claude Opus 5    Claude 서브에이전트
   uiux-designer       Claude Opus 5    Claude 서브에이전트 (조건부)
   software-engineer   GPT-5.6 Sol      Haiku 브리지 -> codex exec
```

## 먼저 읽어야 할 경고

**ChatGPT 계정 인증에서 `gpt-5.6-sol`이 거부된다는 보고가 여러 건 있습니다.**

- 공식 문서(learn.chatgpt.com)는 ChatGPT 로그인 Codex에서 5.6 Sol이 기본 Power
  설정이며 `codex exec -m gpt-5.6`도 된다고 합니다.
- 그런데 openai/codex 저장소 이슈 #31905, #35148과 커뮤니티 스레드에는
  `"The 'gpt-5.6-sol' model is not supported when using Codex with a ChatGPT
  account."` 라는 400 에러 보고가 있습니다. Plus뿐 아니라 Pro 20x에서도 발생하고,
  **Terra와 Luna는 정상 동작**하며 API 키 인증에서는 Sol도 동작한다고 합니다.
- 즉 로그인 경로에서 Sol이 되는지는 계정마다 갈리는 상태입니다.

그래서 브리지는 Sol이 거부되면 **Terra로 자동 폴백**하고, 어느 모델이 실제로
돌았는지 출력 파일 끝에 `MODEL_USED:` 로 기록합니다. 리더와 리뷰어 프롬프트에는
그 값을 확인하고 Terra였으면 검토를 더 강하게 하라는 지시가 들어 있습니다.
스텁으로 4가지 경로(Sol 성공 / Sol 거부→Terra 폴백 / codex 미설치 / 무관한
실패는 폴백 안 함)를 테스트했습니다.

30초로 확인하는 방법:

```bash
codex exec --skip-git-repo-check -m gpt-5.6-sol "reply with PING only" 2>/dev/null
```

`PING`이 나오면 Sol이 님 계정에서 동작합니다. 400 에러면 Terra로 돌아갑니다.

## 설치

```bash
npm i -g @anthropic-ai/claude-code @openai/codex   # 없으면
codex login                                        # ChatGPT 로그인
./init.sh /path/to/your/project
```

`init.sh`는 `ANTHROPIC_API_KEY`, `CODEX_API_KEY`, `OPENAI_API_KEY`가 설정돼 있으면
경고합니다. 이 셋업은 로그인 전용이고, 키가 있으면 조용히 종량제 API 과금으로
넘어갈 수 있습니다. 특히 `CODEX_API_KEY`는 `codex exec`에서만 읽히므로
비대화형 실행만 과금 경로로 바뀌어서 알아채기 어렵습니다.

## 실행

```bash
cd your-project
claude --agent project-leader
```

첫 실행 때 워크스페이스 신뢰 프롬프트를 수락하세요 — 거절하면 리뷰어의 쓰기
차단 훅이 조용히 건너뛰어집니다.

## 브리지 구조

엔지니어 자리는 Haiku 서브에이전트입니다. 구현 판단을 전혀 하지 않고 프롬프트를
파일로 조립해 `scripts/run_codex.sh`에 넘기고 결과를 요약만 하므로, 이 자리에
프론티어 모델을 쓰는 건 낭비입니다.

```bash
scripts/run_codex.sh <prompt-file> <output-file> [model] [effort]
```

실제 명령:

```bash
codex exec --sandbox workspace-write --skip-git-repo-check --ephemeral \
  -m gpt-5.6-sol -c model_reasoning_effort=high \
  -o <output-file> "$(cat <prompt-file>)"
```

- 프롬프트를 셸 인자가 아니라 **파일**로 받습니다. 패킷에 백틱·따옴표·줄바꿈이
  들어가면 셸에서 깨지기 때문입니다.
- `--sandbox workspace-write`를 씁니다. `--full-auto`는 폐기 예정 호환 플래그로
  경고를 냅니다.
- `--ephemeral`은 세션 파일을 디스크에 남기지 않아 병렬 실행 충돌을 막습니다.
- Codex는 진행 상황을 stderr로, 최종 메시지만 stdout으로 냅니다. stderr는
  `.agents/codex-logs/`에 남깁니다.

## 두 개의 별도 예산

이게 가장 실질적인 이점입니다. 리더·리뷰어·디자이너는 Claude 플랜 한도를 쓰고,
엔지니어는 ChatGPT 플랜 한도를 씁니다. 엔지니어가 턴 수가 가장 많은 자리인데
그 부담이 Claude 한도에서 빠집니다.

주의할 점:

- Fable 5는 Max/Team Premium에서만 플랜에 포함되고 주간 한도의 최대 50%까지입니다.
  Pro라면 `project-leader.md`의 `model: fable`을 `opus`로 바꾸세요.
- 멀티에이전트는 토큰을 곱해서 씁니다. 한쪽 한도가 먼저 소진되면 그쪽 역할만
  멈추므로, 어느 쪽이 막혔는지 `.agents/timeline.jsonl`과
  `.agents/codex-logs/`로 구분할 수 있습니다.

## 토폴로지가 실제로 돌았는지

```bash
cat .agents/timeline.jsonl              # logic-reviewer가 software-engineer보다 먼저 start
ls .agents/critiques/                   # 비어 있으면 필수 비평 단계를 건너뛴 것
grep MODEL_USED .agents/codex-out/*.md  # Sol이었나 Terra 폴백이었나
```

## 앞선 두 구조와의 차이

| | 이 셋업 | claude-code/ | mixed-vendor/ |
|---|---|---|---|
| 인증 | 양쪽 로그인 | Claude 로그인 | 양쪽 API 키 |
| 엔지니어 | GPT-5.6 Sol | Claude Opus 5 | GPT-5.6 Sol |
| 리뷰 독립성 | 벤더 다름 | 같은 모델(약함) | 벤더 다름 |
| 비평 게이트 | 프롬프트 지시 | 프롬프트 지시 | **코드 강제** |
| 비용 | 플랜 2개 | 플랜 1개 | 종량제 |

비평 게이트를 코드로 강제하는 건 `mixed-vendor/`(API 방식)에서만 가능합니다.
Claude Code는 리더가 스스로 판단해 위임하는 구조라서, 여기서는 게이트가 여전히
프롬프트 지시입니다. 그래서 `.agents/critiques/`가 비었는지 확인하는 게
중요합니다 — 그게 유일한 사후 증거입니다.
