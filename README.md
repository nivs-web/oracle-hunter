# 오라클 헌터 (GitHub Actions 판)

`C:\down\.ssh\oci_auto_create.py` 와 똑같은 로직입니다. 다른 점 하나 —
**내 PC를 안 켜 둬도** 10분마다 GitHub 서버가 대신 시도합니다.

실제로 켜서 확인해봤습니다: 지금(도쿄 리전) 여전히 자리가 없습니다 —
2주 동안 겪으신 것과 같은 "Out of capacity" 입니다. 스크립트 문제가
아니라 진짜 자리가 없는 것이었고, 이젠 PC를 꺼도 계속 노려줍니다.

## 1. GitHub 저장소 만들기

- 새 저장소 이름: `oracle-hunter` (이름은 아무거나 됩니다)
- **Public(공개)로 만드세요** — 코드 안에 열쇠가 전혀 없어서 공개해도 안전하고,
  Public 이어야 GitHub Actions 를 무제한(시간 제한 없이) 무료로 쓸 수 있습니다.

## 2. Secrets 등록 (저장소 → Settings → Secrets and variables → Actions → New repository secret)

아래 이름 그대로 등록하세요. 값은 전부 **이미 가지고 계신 파일**에서 그대로 복사하면 됩니다.

| Secret 이름 | 어디서 복사하나 |
|---|---|
| `OCI_USER_OCID` | `C:\down\.ssh\oci_auto_create.py` 의 `"user"` 값 |
| `OCI_FINGERPRINT` | 같은 파일의 `"fingerprint"` 값 |
| `OCI_TENANCY_OCID` | 같은 파일의 `"tenancy"` 값 |
| `OCI_REGION` | 같은 파일의 `"region"` 값 (지금 `ap-tokyo-1`) |
| `OCI_COMPARTMENT_ID` | 같은 파일의 `COMPARTMENT_ID` 값 |
| `OCI_SUBNET_ID` | 같은 파일의 `SUBNET_ID` 값 |
| `OCI_PRIVATE_KEY` | `C:\down\.ssh\oci_api_key.pem` 파일을 **메모장으로 열어서 전체 내용**(`-----BEGIN PRIVATE KEY-----` 부터 `-----END PRIVATE KEY-----` 까지 전부) 그대로 붙여넣기 |
| `SSH_PUBLIC_KEY` | `C:\down\.ssh\ssh-key-2026-08-11.key.pub` 파일 내용 전체 |

메일 알림을 받고 싶으면(선택):

| Secret 이름 | 값 |
|---|---|
| `GMAIL_USER` | `opioo84@gmail.com` |
| `GMAIL_APP_PASSWORD` | 서재 서버에 쓰던 것과 같은 지메일 앱 비밀번호(공유기의 `/jffs/.mylib_mail_pass`) |
| `GMAIL_TO` | 받을 주소 (**안 넣어도 됨 — 기본값이 `opioo84@gmail.com`으로 고정되어 있음**) |

메일을 안 넣어도 문제없습니다 — 성공하면 저장소의 **Actions 탭 → 해당 실행 → Summary** 에
"🎉 오라클 서버 생성 성공!" 이라고 크게 뜹니다.

## 3. 코드 올리기

```bash
cd oracle-hunter
git init
git add .
git commit -m "오라클 무료 서버 자동 헌터"
git branch -M main
git remote add origin https://github.com/<계정이름>/oracle-hunter.git
git push -u origin main
```

## 4. 확인

- 저장소 **Actions** 탭에 들어가면 `oracle-free-tier-hunt` 워크플로가 보입니다.
- 10분마다 자동으로 돕니다. 지금 바로 한 번 시켜보고 싶으면
  Actions 탭 → 왼쪽 `oracle-free-tier-hunt` 클릭 → **Run workflow** 버튼.
- 성공하면 Summary 에 뜨고(+메일 설정했으면 메일도), **예약(cron)은 그 실행이 끝나면
  자동으로 꺼집니다** — 따로 손댈 필요 없습니다(이미 있는 서버에 또 만들려다
  "한도 초과" 오류만 반복되는 것을 막기 위한 처리입니다). 확인하고 싶으면
  Actions 탭 → 왼쪽 `oracle-free-tier-hunt` 옆에 "This workflow has been disabled" 표시를
  보면 됩니다. 다시 켜고 싶으면 같은 자리에서 "Enable workflow" 를 누르면 됩니다.

## 60일 넘게 걸려도 괜찮은가?

커뮤니티 사례를 보면 자리 잡는 데 **1~3개월** 걸리는 경우도 흔합니다. 문제는
GitHub가 **저장소에 60일 동안 커밋이 하나도 없으면 예약(cron)을 자동으로 꺼버린다**는
점입니다 — 서버를 못 잡아서가 아니라 이 규칙 때문에 먼저 멈추면 억울하니,
`.github/workflows/keepalive.yml`이 매달 1일·15일에 빈 커밋을 하나씩 남겨서
저장소를 계속 "살아있는" 상태로 유지합니다. 따로 신경 쓸 필요 없이 자동으로 돕니다.

## 사양을 바꾸고 싶다면

`.github/workflows/hunt.yml` 맨 아래 `SHAPE` / `OCPUS` / `MEMORY_GB` / `BOOT_VOLUME_GB` 를
고치면 됩니다. 지금은 1 OCPU / 6GB RAM / 50GB 로, 예전 스크립트가 "사양을 낮출수록
잡힐 확률이 올라간다"며 골라 둔 값을 그대로 썼습니다. 책 33.9GB + 별도 이북 36.9GB
(합 70.8GB) 를 담을 거면 부트볼륨을 100GB 정도로 올리는 것도 고려해볼 만합니다
(오라클 무료 한도는 계정 전체 200GB 라 여유 있습니다).
