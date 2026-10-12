# 마라톤 대회 달력 — GitHub 자동 데이터 배포

기존 Blogger(블로그스팟) XML 스킨은 유지하고, GitHub Pages의 `events.json`을 읽도록 만든 프로젝트입니다.

## 아주 중요한 현재 상태

- 초기 대회 397개는 **2026-10-12에 정리한 스냅샷**입니다. 기존 확인 결과가 모두 현재 시점에서 재검증되었다는 뜻은 아닙니다.
- 이 저장소를 올리면 **매일 오전 8:17 / 오후 8:17(한국시간) 실행 → JSON 배포**까지 됩니다.
- **런닝인사이드 사이트에서 새로운 대회를 자동으로 가져오는 기능은 현재 꺼져 있습니다.** 공개 API 또는 자동 수집·재이용 허용 여부와 실제 형식을 검증하지 않았기 때문입니다. 승인된 JSON 출처를 설정하거나 직접 추가한 CSV에만 새 대회가 들어옵니다.
- 예전 데이터가 사라지지 않도록 최종 정상본을 유지합니다.
- 신청 링크는 확인된 URL만 표시하되, 사이트 리디렉션·접수 마감 등은 바뀔 수 있습니다.

## 1) GitHub에서 저장소 만들기

1. <https://github.com/new> 접속
2. `Repository name`을 **`marathon-data`** 로 입력 (철자 중요)
3. `Public` 선택 (GitHub Free에서 Pages를 무료로 공개하기 위한 설정)
4. `Add a README file`은 체크하지 않아도 됩니다.
5. `Create repository` 선택
6. 이 ZIP을 PC에서 **압축 해제**한 다음, 압축을 푼 폴더 안의 파일과 폴더를 GitHub 저장소의 **Add file → Upload files**에 올립니다. `.github` 폴더도 꼭 포함하세요.
7. `Commit changes` 클릭

ZIP 자체를 업로드하면 동작하지 않습니다. 압축을 풀어 나온 **폴더 내부의 내용물**을 올려야 합니다.

## 2) GitHub Pages 활성화

1. GitHub 저장소의 `Settings → Pages` 이동
2. `Build and deployment → Source`에서 **`GitHub Actions`** 선택
3. `Actions` 탭 → **`마라톤 일정 갱신 및 공개`** → `Run workflow` → 실행
4. 실행이 정상 종료되면: `https://내계정.github.io/marathon-data/events.json` 확인
5. `update-status.json`을 열면 최종 배포 확인 시간과 승인 피드 수를 볼 수 있습니다.

실패했다면 `Actions`에서 빨간 실행 항목을 열어 오류 기록을 확인하세요. 기본 브랜치가 `main`이어야 합니다.

## 3) Blogger XML 스킨에서 GitHub 사용자명 입력

대화에서 별도 제공된 **`마라톤_GitHub_자동업데이트_연동스킨.xml`** 파일을 텍스트 편집기로 엽니다.

XML에서 `YOUR_GITHUB_USERNAME` 문구를 검색해 **모두 바꾸기**로 실제 GitHub 사용자명으로 변경합니다.

- 수정 전: `YOUR_GITHUB_USERNAME`
- 수정 후: `본인 GitHub 계정 아이디` (예: `runner123`)

그다음 블로그스팟 관리자 → `테마` → **현재 스킨 백업** → `복원`에서 수정한 XML 업로드.

접속하면 스킨에 보관된 397개 대회가 즉시 보이고, GitHub JSON을 받으면 목록이 자동 갱신됩니다. `최신 데이터를 불러오지 못해 기본 저장된...`가 계속 표시된다면 username 오타·Pages 설정·연결 오류 여부를 확인하세요.

## 4) 마라톤 대회 추가·수정하기 (즉시 가능)

`data/manual_events.csv`를 클릭하여 오른쪽 연필 모양으로 편집합니다. 표 첫 줄(header)은 절대 바꾸지 마세요.

형식: `title,run,start,end,fee,startPlace,officialLink,badgeText,source`

- `run`, `start`, `end`: `YYYY-MM-DD` 형식. 시작/종료일 모르면 빈칸으로 둡니다.
- `officialLink`: 공식 신청 페이지나 공식 홈페이지 링크만 적습니다. 확인하지 못하면 빈칸으로 둡니다.
- `badgeText`: `접수중`, `접수예정`, `접수마감`, `접수정보 없음`, `취소` 중 하나. 근거 없는 `접수중`을 쓰지 마세요.
- `source`: 확인한 정보의 출처(예: 공식 공지 링크)

변경 후 `Commit changes`를 누르면 `Actions`가 자동으로 실행됩니다.

**쉼표가 들어간 텍스트는 따옴표("...")로 감싸야 합니다.**

## 5) 새로운 대회 자동 수집을 활성화하려면

1. 사용 허용이 확인된 공식 데이터 소스(공개 JSON API 또는 제공받은 JSON)를 구합니다.
2. `data/source_config.json`의 `feeds` 배열에 피드를 지정합니다.
3. 등록된 JSON은 `[{"title":"...","run":"2026-12-31",...}]` 또는 `{ "events": [...] }` 형식이어야 합니다.
4. 데이터 사용을 허용한 소스만 `authorized: true`로 설정합니다.

예시 (주소는 **가상의 예시**, 실제로 작동하지 않습니다):

```json
{
  "feeds": [
    {
      "name": "공식 승인 JSON 피드",
      "url": "https://example.org/approved-marathon-events.json",
      "authorized": true
    }
  ],
  "fail_on_feed_error": false
}
```

외부 대회 목록 사이트를 허락 없이 대량 자동 수집하도록 만드는 방식은 제공하지 않습니다. 권한을 얻어도 페이지 HTML에만 의존하면 사이트 변경으로 수집이 멈출 수 있으니 JSON API가 훨씬 안정적입니다.

## 6) 파일별 역할

| 파일 | 용도 |
|---|---|
| `.github/workflows/update-and-publish.yml` | 한국시간 하루 두 번 일정 실행 및 Pages 공개 |
| `data/base_events.json` | 397개 기존 대회 초기 자료 |
| `data/manual_events.csv` | 사람이 검증한 새로운 대회, 접수 정보 추가 |
| `data/source_config.json` | 승인된 JSON 피드만 허용 |
| `scripts/update_events.py` | 검증, 중복 병합, 실패 시 기존 데이터 보호 |
| `docs/events.json` | Blogger 스킨이 읽는 데이터 파일 |
| `docs/update-status.json` | 업데이트 결과 기록 |

**이 사이트는 대회 개최일·접수 정보가 수시로 바뀔 수 있습니다. 참가 전 반드시 공식 대회 페이지에서 다시 확인하세요.**
