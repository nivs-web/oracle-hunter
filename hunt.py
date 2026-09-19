"""
Oracle Cloud - Ampere A1 Always Free 인스턴스 자동 재시도 (GitHub Actions용)
----------------------------------------------------------------------
기존 C:\\down\\.ssh\\oci_auto_create.py 를 그대로 가져왔다. 다른 점은 딱 하나 —
"내 PC가 2주 내내 안 꺼져야 한다"를 "GitHub 서버가 대신 몇 분마다 한 번씩
깨어나 시도한다"로 바꾼 것뿐이다. PC를 끄든 잠들든 상관없다.

무한 while 루프 대신, 이번 실행에서 AD(가용 도메인) 목록을 한 바퀴만 돈다.
반복은 이 파일이 아니라 .github/workflows/hunt.yml 의 cron 예약이 맡는다
(GitHub Actions 는 "몇 시간씩 도는 하나의 작업"보다 "짧게 끝나는 작업을
반복 예약"하는 쪽에 맞게 만들어져 있다).

성공하면:
  1) 화면(Actions 로그)에 크게 성공 표시
  2) GITHUB_STEP_SUMMARY 에 적어서 GitHub 화면에서 바로 보이게
  3) (선택) 지메일 앱 비밀번호를 넣어 뒀으면 opioo84@gmail.com 으로 메일

민감한 값(API 키, OCID 등)은 이 파일에 절대 적지 않는다 — 전부
GitHub Secrets 에서 환경변수로 받는다. 이 저장소가 나중에 실수로라도
공개되어도 열쇠는 안 새어나간다.
"""
import oci
import datetime
import os
import sys

# 로컬 윈도우 콘솔(cp949)에서 한글·—— 같은 글자가 깨져 죽는 것을 막는다.
# GitHub Actions(Ubuntu, UTF-8 기본)에서는 원래도 문제없지만, 로컬에서
# 먼저 시험해 볼 때도 그대로 동작하게 해 둔다.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}", flush=True)


def env(name, required=True):
    v = os.environ.get(name, "").strip()
    if required and not v:
        log(f"환경변수 {name} 가 없습니다 — GitHub Secrets 설정을 확인하세요.")
        sys.exit(2)
    return v


def write_summary(text):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception:
        pass


DEFAULT_NOTIFY_TO = "opioo84@gmail.com"  # GMAIL_TO 를 안 정해두면 여기로 간다


def send_mail(subject, body):
    user = os.environ.get("GMAIL_USER", "").strip()
    pw = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    to = os.environ.get("GMAIL_TO", "").strip() or user or DEFAULT_NOTIFY_TO
    if not user or not pw:
        log("메일 설정이 없어 알림 메일은 건너뜁니다(선택 사항이라 문제 없음).")
        return
    import smtplib
    from email.mime.text import MIMEText
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to
    try:
        s = smtplib.SMTP("smtp.gmail.com", 587, timeout=15)
        s.starttls()
        s.login(user, pw)
        s.sendmail(user, [to], msg.as_string())
        s.quit()
        log(f"알림 메일 보냄 -> {to}")
    except Exception as e:
        log(f"메일 실패(치명적이지 않음): {e}")


def get_ubuntu_image_id(compute_client, compartment_id, shape):
    images = compute_client.list_images(
        compartment_id=compartment_id,
        operating_system="Canonical Ubuntu",
        operating_system_version="24.04",
        shape=shape,
        sort_by="TIMECREATED",
        sort_order="DESC",
    ).data
    if not images:
        raise Exception("Ubuntu 24.04 이미지를 찾을 수 없습니다.")
    return images[0].id, images[0].display_name


def main():
    region = env("OCI_REGION")
    # 개인 키는 워크플로가 실행 중에만 파일로 잠깐 써 두고(OCI_KEY_FILE 경로),
    # 실행이 끝나면 그 파일도 함께 사라진다(GitHub Actions 러너는 매번 새 컴퓨터).
    key_file = env("OCI_KEY_FILE")
    config = {
        "user": env("OCI_USER_OCID"),
        "fingerprint": env("OCI_FINGERPRINT"),
        "tenancy": env("OCI_TENANCY_OCID"),
        "region": region,
        "key_file": key_file,
    }
    compartment_id = env("OCI_COMPARTMENT_ID")
    subnet_id = env("OCI_SUBNET_ID")
    ssh_public_key = env("SSH_PUBLIC_KEY")

    shape = os.environ.get("SHAPE", "VM.Standard.A1.Flex")
    ocpus = float(os.environ.get("OCPUS", "1"))
    memory_gb = float(os.environ.get("MEMORY_GB", "6"))
    boot_gb = float(os.environ.get("BOOT_VOLUME_GB", "50"))
    display_name = os.environ.get("INSTANCE_DISPLAY_NAME", "my-hermes-server")
    ad_filter = os.environ.get("AVAILABILITY_DOMAIN", "").strip()

    identity_client = oci.identity.IdentityClient(config)
    compute_client = oci.core.ComputeClient(config)

    log(f"리전: {region} / 사양: {ocpus} OCPU, {memory_gb}GB RAM, 부트볼륨 {boot_gb}GB")

    image_id, image_name = get_ubuntu_image_id(compute_client, compartment_id, shape)
    log(f"이미지: {image_name}")

    ads = [ad.name for ad in identity_client.list_availability_domains(compartment_id).data]
    if ad_filter:
        ads = [a for a in ads if a == ad_filter] or ads
    log(f"시도할 AD: {ads}")

    for ad in ads:
        log(f"시도 중 — AD: {ad}")
        try:
            launch_details = oci.core.models.LaunchInstanceDetails(
                compartment_id=compartment_id,
                availability_domain=ad,
                display_name=display_name,
                shape=shape,
                shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
                    ocpus=ocpus,
                    memory_in_gbs=memory_gb,
                ),
                create_vnic_details=oci.core.models.CreateVnicDetails(
                    subnet_id=subnet_id,
                    assign_public_ip=True,
                ),
                source_details=oci.core.models.InstanceSourceViaImageDetails(
                    image_id=image_id,
                    boot_volume_size_in_gbs=boot_gb,
                ),
                metadata={"ssh_authorized_keys": ssh_public_key},
            )
            resp = compute_client.launch_instance(launch_details)
            instance = resp.data

            log("=" * 50)
            log("성공! 인스턴스가 생성되었습니다!")
            log(f"Instance ID: {instance.id}")
            log("=" * 50)

            summary = (
                "## 🎉 오라클 서버 생성 성공!\n\n"
                f"- 시각: {datetime.datetime.now().isoformat(timespec='seconds')}\n"
                f"- 리전: {region}\n"
                f"- AD: {ad}\n"
                f"- 사양: {ocpus} OCPU / {memory_gb}GB RAM / 부트볼륨 {boot_gb}GB\n"
                f"- Instance ID: `{instance.id}`\n\n"
                "**다음 할 일**\n"
                "1. 오라클 콘솔 → Compute → Instances 에서 공인 IP 확인\n"
                "2. `ssh -i ssh-key-....key ubuntu@<공인IP>` 로 접속\n"
                "3. 성공했으니 이 저장소의 Actions 예약(cron)은 꺼도 됩니다 "
                "(계속 두면 두 번째 인스턴스를 또 만들려다 한도 초과 오류만 반복됩니다)\n"
            )
            write_summary(summary)
            send_mail(
                "[오라클 헌터] 서버 생성 성공!",
                f"인스턴스가 생성되었습니다.\n\nInstance ID: {instance.id}\nAD: {ad}\n리전: {region}\n\n"
                "오라클 콘솔에서 공인 IP를 확인해 접속하세요.\n"
                "성공했으니 GitHub 저장소의 Actions 예약을 꺼 두세요(Settings 아님 — "
                "Actions 탭에서 워크플로 비활성화).",
            )
            print("HUNT_RESULT=success")
            return 0

        except oci.exceptions.ServiceError as e:
            msg = str(e.message)
            if "Out of capacity" in msg or e.status == 500:
                log(f"용량 부족 (AD: {ad}) — 다음 AD 또는 다음 예약 때 다시 시도합니다.")
            elif e.status == 429:
                log("요청이 너무 잦습니다(Rate limit). 이번 회차는 여기서 멈춥니다.")
                break
            elif e.status == 400 and "LimitExceeded" in msg:
                log("한도 초과 — 이미 인스턴스가 있을 수 있습니다. 콘솔을 확인하세요.")
                write_summary(
                    "## ⚠️ 한도 초과(LimitExceeded)\n\n"
                    "이미 인스턴스가 하나 있을 수 있습니다. 오라클 콘솔에서 확인해 주세요.\n"
                )
                print("HUNT_RESULT=limit_exceeded")
                return 0
            else:
                log(f"예상치 못한 오류: {e.status} - {msg}")
        except Exception as e:
            log(f"네트워크/기타 오류: {e}")

    log("이번 회차는 자리가 없었습니다. 다음 예약(cron) 때 다시 시도합니다.")
    print("HUNT_RESULT=no_capacity_yet")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
